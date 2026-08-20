from __future__ import annotations

import asyncio
import math
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.network import (
    NetworkLabSession,
    NetworkLink,
    NetworkNode,
    NetworkProject,
    NetworkTopology,
)
from app.repositories.device import DeviceRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.network import (
    NetworkLinkRepository,
    NetworkNodeRepository,
    NetworkProjectRepository,
    NetworkTopologyRepository,
)
from app.repositories.rack import RackRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.network import (
    CanvasLinkInput,
    CanvasNodeInput,
    CanvasSaveRequest,
    FramePort,
    NetworkDeviceBrief,
    NetworkLinkResponse,
    NetworkLinkType,
    NetworkNodeKind,
    NetworkNodeResponse,
    NetworkProjectCreate,
    NetworkProjectResponse,
    NetworkProjectUpdate,
    NetworkTopologyCreate,
    NetworkTopologyDetailResponse,
    NetworkTopologyResponse,
    NetworkTopologyUpdate,
    PortLayout,
    SlotConfig,
    default_slots,
)
from app.services.device import _ip_fields_from_device


def _get_port_layout(node: NetworkNode | CanvasNodeInput) -> PortLayout | None:
    raw = getattr(node, "port_layout", None)
    if not raw:
        return None
    if isinstance(raw, PortLayout):
        return raw
    if isinstance(raw, dict) and raw.get("ports") is not None:
        return PortLayout.model_validate(raw)
    return None


def _sync_legacy_ports(node: CanvasNodeInput) -> None:
    """Derive switch_port_count / slots from visual port_layout when present."""
    layout = node.port_layout
    if not layout:
        return
    if layout.slots_def:
        from app.schemas.network import _slots_from_layout_def

        node.slots = _slots_from_layout_def(layout.slots_def)
        if node.kind == NetworkNodeKind.SWITCH:
            from app.schemas.network import _slot_port_count

            node.switch_port_count = sum(_slot_port_count(item) for item in layout.slots_def)
        return
    if not layout.ports:
        return
    port_ids = [p.id for p in layout.ports]
    if node.kind == NetworkNodeKind.SWITCH:
        max_num = 0
        for pid in port_ids:
            if pid.startswith("p") and pid[1:].isdigit():
                max_num = max(max_num, int(pid[1:]))
            match = re.match(r"slot(\d+)-(?:g[^-]+-)?p(\d+)", pid)
            if match:
                max_num = max(max_num, int(match.group(2)))
        node.switch_port_count = max(max_num, len(port_ids), 1)
        node.slots = None
        return

    slots = default_slots()
    for pid in port_ids:
        match = re.match(r"slot(\d+)-(?:g[^-]+-)?p(\d+)", pid)
        if not match:
            continue
        idx = int(match.group(1)) - 1
        port_num = int(match.group(2))
        if idx < 0 or idx >= 8:
            continue
        slots[idx].enabled = True
        slots[idx].port_count = max(slots[idx].port_count, port_num)
    node.slots = slots


def _node_ports(node: NetworkNode | CanvasNodeInput) -> set[str]:
    layout = _get_port_layout(node)
    if layout and layout.ports:
        return {p.id for p in layout.ports}
    if node.kind == NetworkNodeKind.SWITCH.value or node.kind == NetworkNodeKind.SWITCH:
        count = node.switch_port_count
        return {f"p{i}" for i in range(1, count + 1)}
    slots = node.slots or default_slots()
    ports: set[str] = set()
    for idx, slot in enumerate(slots, start=1):
        slot_cfg = slot if isinstance(slot, SlotConfig) else SlotConfig.model_validate(slot)
        if not slot_cfg.enabled:
            continue
        for port in range(1, slot_cfg.port_count + 1):
            ports.add(f"slot{idx}-p{port}")
    return ports


def _normalize_kind(kind: str | NetworkNodeKind) -> str:
    return kind.value if isinstance(kind, NetworkNodeKind) else kind


DEFAULT_PROJECT_CODE = "DEFAULT"
DEFAULT_PROJECT_NAME = "默认项目"

# SQLite 单写：串行化大画布保存，避免 database is locked
_canvas_save_lock = asyncio.Lock()


class NetworkDesignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = NetworkProjectRepository(session)
        self.topology_repo = NetworkTopologyRepository(session)
        self.node_repo = NetworkNodeRepository(session)
        self.link_repo = NetworkLinkRepository(session)
        self.device_repo = DeviceRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)

    async def ensure_default_project(
        self, user_id: uuid.UUID | None = None
    ) -> NetworkProject:
        """确保系统默认项目存在。"""
        existing = await self.project_repo.get_by_code(DEFAULT_PROJECT_CODE)
        if existing:
            return existing
        project = NetworkProject(
            code=DEFAULT_PROJECT_CODE,
            name=DEFAULT_PROJECT_NAME,
            description="系统默认项目，不可删除",
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.project_repo.create(project)
        topology = NetworkTopology(
            name=DEFAULT_PROJECT_NAME,
            description="默认项目拓扑",
            project_id=created.id,
            created_by=user_id,
            updated_by=user_id,
        )
        await self.topology_repo.create(topology)
        return created

    def _to_project_response(
        self, project: NetworkProject, topology_id: uuid.UUID | None = None
    ) -> NetworkProjectResponse:
        return NetworkProjectResponse(
            id=project.id,
            code=project.code,
            name=project.name,
            description=project.description,
            topology_id=topology_id,
            model_root_folder_id=project.model_root_folder_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    async def _repair_model_root_folder(self, project: NetworkProject) -> bool:
        """Clear a stale model-folder reference left behind by legacy soft deletes."""
        if project.model_root_folder_id is None:
            return False

        from app.models.network_model_design import NetworkModelFolder

        folder = await self.session.get(NetworkModelFolder, project.model_root_folder_id)
        if folder is not None and folder.deleted_at is None:
            return False

        project.model_root_folder_id = None
        await self.session.flush()
        await self.session.refresh(project)
        return True

    async def list_projects(
        self, params: PaginationParams
    ) -> tuple[list[NetworkProjectResponse], PaginationMeta]:
        await self.ensure_default_project()
        items, total = await self.project_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort or "updated_at",
            order=params.order,
            search_fields=["code", "name", "description"],
        )
        # 默认项目始终置顶
        items = sorted(
            items,
            key=lambda p: (0 if (p.code or "").upper() == DEFAULT_PROJECT_CODE else 1, p.name or ""),
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        responses: list[NetworkProjectResponse] = []
        repaired = False
        for item in items:
            repaired = await self._repair_model_root_folder(item) or repaired
            topo = await self.project_repo.get_primary_topology(item.id)
            responses.append(self._to_project_response(item, topo.id if topo else None))
        if repaired:
            await self.session.commit()
        return responses, pagination

    async def get_project(self, project_id: uuid.UUID) -> NetworkProjectResponse:
        entity = await self.project_repo.get_by_id(project_id)
        if not entity:
            raise NotFoundError("Network project not found")
        if await self._repair_model_root_folder(entity):
            await self.session.commit()
        topo = await self.project_repo.get_primary_topology(project_id)
        return self._to_project_response(entity, topo.id if topo else None)

    async def create_project(
        self, payload: NetworkProjectCreate, user_id: uuid.UUID | None = None
    ) -> NetworkProjectResponse:
        code = payload.code.strip().upper()
        name = payload.name.strip()
        if not code or not name:
            raise ValidationError("Project code and name are required")
        if code == DEFAULT_PROJECT_CODE:
            raise ValidationError("DEFAULT 为系统保留编码，请使用其他项目编码")
        existing = await self.project_repo.get_by_code(code)
        if existing:
            raise ValidationError(f"Project code already exists: {code}")

        project = NetworkProject(
            code=code,
            name=name,
            description=payload.description,
            model_root_folder_id=payload.model_root_folder_id,
            created_by=user_id,
            updated_by=user_id,
        )
        if payload.model_root_folder_id:
            await self._ensure_model_folder(payload.model_root_folder_id)
        created = await self.project_repo.create(project)
        topology = NetworkTopology(
            name=name,
            description=payload.description,
            project_id=created.id,
            created_by=user_id,
            updated_by=user_id,
        )
        topo = await self.topology_repo.create(topology)
        await self.session.commit()
        return self._to_project_response(created, topo.id)

    async def update_project(
        self,
        project_id: uuid.UUID,
        payload: NetworkProjectUpdate,
        user_id: uuid.UUID | None = None,
    ) -> NetworkProjectResponse:
        entity = await self.project_repo.get_by_id(project_id)
        if not entity:
            raise NotFoundError("Network project not found")
        if payload.code is not None:
            code = payload.code.strip().upper()
            if not code:
                raise ValidationError("Project code is required")
            if (
                entity.code.upper() == DEFAULT_PROJECT_CODE
                and code != DEFAULT_PROJECT_CODE
            ):
                raise ValidationError("不可修改系统默认项目编码 DEFAULT")
            if (
                entity.code.upper() != DEFAULT_PROJECT_CODE
                and code == DEFAULT_PROJECT_CODE
            ):
                raise ValidationError("DEFAULT 为系统保留编码")
            conflict = await self.project_repo.get_by_code(code)
            if conflict and conflict.id != project_id:
                raise ValidationError(f"Project code already exists: {code}")
            entity.code = code
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ValidationError("Project name is required")
            entity.name = name
        if payload.description is not None:
            entity.description = payload.description
        if "model_root_folder_id" in payload.model_fields_set:
            if payload.model_root_folder_id is not None:
                await self._ensure_model_folder(payload.model_root_folder_id)
            entity.model_root_folder_id = payload.model_root_folder_id
        entity.updated_by = user_id

        topo = await self.project_repo.get_primary_topology(project_id)
        if topo and payload.name is not None:
            topo.name = entity.name
            topo.updated_by = user_id
        if topo and payload.description is not None:
            topo.description = entity.description
            topo.updated_by = user_id

        await self.session.commit()
        await self.session.refresh(entity)
        if topo is not None:
            await self.session.refresh(topo)
        return self._to_project_response(entity, topo.id if topo else None)

    async def _ensure_model_folder(self, folder_id: uuid.UUID) -> None:
        from app.models.network_model_design import NetworkModelFolder
        from app.repositories.network_model_design import NetworkModelFolderRepository

        folder = await NetworkModelFolderRepository(self.session).get_by_id(folder_id)
        if not folder:
            # fallback: raw get (covers edge cases)
            folder = await self.session.get(NetworkModelFolder, folder_id)
        if not folder or folder.deleted_at is not None:
            raise NotFoundError("模型项目/文件夹不存在")

    async def delete_project(
        self, project_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        entity = await self.project_repo.get_by_id(project_id)
        if not entity:
            raise NotFoundError("Network project not found")
        if (entity.code or "").upper() == DEFAULT_PROJECT_CODE:
            raise ValidationError("系统默认项目（DEFAULT）不可删除")
        topologies = await self.topology_repo.list_by_project(project_id)
        for topo in topologies:
            await self.delete_topology(topo.id, user_id=user_id)
        now = datetime.now(timezone.utc)
        entity.deleted_at = now
        entity.deleted_by = user_id
        await self.session.commit()
        # 删除后确保默认项目仍存在
        await self.ensure_default_project(user_id=user_id)

    async def list_topologies(
        self, params: PaginationParams, project_id: uuid.UUID | None = None
    ) -> tuple[list[NetworkTopologyResponse], PaginationMeta]:
        filters = {"project_id": project_id} if project_id else None
        items, total = await self.topology_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort or "updated_at",
            order=params.order,
            filters=filters,
            search_fields=["name", "description"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [NetworkTopologyResponse.model_validate(item) for item in items], pagination

    async def create_topology(
        self, payload: NetworkTopologyCreate, user_id: uuid.UUID | None = None
    ) -> NetworkTopologyResponse:
        if payload.project_id:
            project = await self.project_repo.get_by_id(payload.project_id)
            if not project:
                raise NotFoundError("Network project not found")
        entity = NetworkTopology(
            name=payload.name.strip(),
            description=payload.description,
            project_id=payload.project_id,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.topology_repo.create(entity)
        await self.session.commit()
        await self.session.refresh(created)
        return NetworkTopologyResponse.model_validate(created)

    async def update_topology(
        self,
        topology_id: uuid.UUID,
        payload: NetworkTopologyUpdate,
        user_id: uuid.UUID | None = None,
    ) -> NetworkTopologyResponse:
        entity = await self.topology_repo.get_by_id(topology_id)
        if not entity:
            raise NotFoundError("Network topology not found")
        if payload.name is not None:
            entity.name = payload.name.strip()
        if payload.description is not None:
            entity.description = payload.description
        if payload.project_id is not None:
            project = await self.project_repo.get_by_id(payload.project_id)
            if not project:
                raise NotFoundError("Network project not found")
            entity.project_id = payload.project_id
        entity.updated_by = user_id
        await self.session.commit()
        await self.session.refresh(entity)
        return NetworkTopologyResponse.model_validate(entity)

    async def delete_topology(
        self, topology_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        entity = await self.topology_repo.get_by_id(topology_id)
        if not entity:
            raise NotFoundError("Network topology not found")
        now = datetime.now(timezone.utc)
        entity.deleted_at = now
        entity.deleted_by = user_id
        for node in await self.node_repo.list_by_topology(topology_id):
            node.deleted_at = now
            node.deleted_by = user_id
        for link in await self.link_repo.list_by_topology(topology_id):
            link.deleted_at = now
            link.deleted_by = user_id
        lab_stmt = select(NetworkLabSession).where(
            NetworkLabSession.topology_id == topology_id,
            NetworkLabSession.deleted_at.is_(None),
        )
        for lab in (await self.session.execute(lab_stmt)).scalars():
            lab.deleted_at = now
            lab.deleted_by = user_id
        # 先提交，避免响应未消费完时审计中间件再开连接把 SQLite 锁死
        await self.session.commit()

    async def get_detail(self, topology_id: uuid.UUID) -> NetworkTopologyDetailResponse:
        entity = await self.topology_repo.get_by_id(topology_id)
        if not entity or entity.deleted_at is not None:
            raise NotFoundError("Network topology not found")
        nodes = await self.node_repo.list_by_topology(topology_id)
        links = await self.link_repo.list_by_topology(topology_id)
        device_map = await self._load_device_briefs(
            [node.device_id for node in nodes if node.device_id]
        )
        return NetworkTopologyDetailResponse(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            project_id=entity.project_id,
            nodes=[
                self._to_node_response(node, device_map.get(node.device_id) if node.device_id else None)
                for node in nodes
            ],
            links=[NetworkLinkResponse.model_validate(link) for link in links],
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def save_canvas(
        self,
        topology_id: uuid.UUID,
        payload: CanvasSaveRequest,
        user_id: uuid.UUID | None = None,
    ) -> NetworkTopologyDetailResponse:
        """串行化大画布写入，配合 SQLite WAL/busy_timeout 降低 database is locked。"""
        async with _canvas_save_lock:
            return await self._save_canvas_impl(topology_id, payload, user_id)

    async def _save_canvas_impl(
        self,
        topology_id: uuid.UUID,
        payload: CanvasSaveRequest,
        user_id: uuid.UUID | None = None,
    ) -> NetworkTopologyDetailResponse:
        entity = await self.topology_repo.get_with_canvas(topology_id)
        if not entity:
            raise NotFoundError("Network topology not found")

        self._validate_canvas(payload)
        await self._validate_devices(payload.nodes)

        # 含已软删节点：同 id 再次保存时恢复，避免主键冲突
        nodes_by_id = {node.id: node for node in entity.nodes}
        existing_nodes = {nid: n for nid, n in nodes_by_id.items() if n.deleted_at is None}
        incoming_ids: set[uuid.UUID] = set()
        id_map: dict[uuid.UUID, uuid.UUID] = {}

        for item in payload.nodes:
            _sync_legacy_ports(item)
            slots_payload = None
            port_layout_payload = None
            if item.port_layout:
                port_layout_payload = item.port_layout.model_dump(mode="json")
            if item.kind in (NetworkNodeKind.SERVER, NetworkNodeKind.SECURITY):
                slots_payload = [slot.model_dump(mode="json") for slot in (item.slots or default_slots())]

            if item.id and item.id in nodes_by_id:
                node = nodes_by_id[item.id]
                node.kind = item.kind.value
                node.name = item.name.strip()
                node.device_id = item.device_id
                node.device_model_id = item.device_model_id
                node.design_model_id = item.design_model_id
                node.contract_device_name = item.contract_device_name
                node.network_role = item.network_role
                node.device_group = item.device_group
                node.device_groups = list(item.device_groups) if item.device_groups else None
                node.pos_x = item.pos_x
                node.pos_y = item.pos_y
                node.switch_port_count = item.switch_port_count
                node.slots = slots_payload
                node.port_layout = port_layout_payload
                node.on_canvas = bool(item.on_canvas)
                node.deleted_at = None
                node.deleted_by = None
                node.updated_by = user_id
                incoming_ids.add(node.id)
                id_map[item.id] = node.id
            else:
                # 必须挂到 entity.nodes：关系带 delete-orphan，仅 session.add 会被当成孤儿删掉
                node = NetworkNode(
                    id=item.id or uuid.uuid4(),
                    topology_id=topology_id,
                    kind=item.kind.value,
                    name=item.name.strip(),
                    device_id=item.device_id,
                    device_model_id=item.device_model_id,
                    design_model_id=item.design_model_id,
                    contract_device_name=item.contract_device_name,
                    network_role=item.network_role,
                    device_group=item.device_group,
                    device_groups=list(item.device_groups) if item.device_groups else None,
                    pos_x=item.pos_x,
                    pos_y=item.pos_y,
                    switch_port_count=item.switch_port_count,
                    slots=slots_payload,
                    port_layout=port_layout_payload,
                    on_canvas=bool(item.on_canvas),
                    created_by=user_id,
                    updated_by=user_id,
                )
                entity.nodes.append(node)
                await self.session.flush()
                incoming_ids.add(node.id)
                if item.id:
                    id_map[item.id] = node.id
                else:
                    id_map[node.id] = node.id

        now = datetime.now(timezone.utc)
        for node_id, node in existing_nodes.items():
            if node_id not in incoming_ids:
                node.deleted_at = now
                node.deleted_by = user_id

        # 含已软删链路：同 id 再次保存时恢复，避免主键冲突（与节点 upsert 一致）
        links_by_id = {link.id: link for link in entity.links}
        existing_links = {lid: l for lid, l in links_by_id.items() if l.deleted_at is None}
        incoming_link_ids: set[uuid.UUID] = set()

        node_lookup = {
            node.id: node
            for node in entity.nodes
            if node.deleted_at is None and node.id in incoming_ids
        }

        for link_input in payload.links:
            source_id = id_map.get(link_input.source_node_id, link_input.source_node_id)
            target_id = id_map.get(link_input.target_node_id, link_input.target_node_id)
            source_node = node_lookup.get(source_id)
            target_node = node_lookup.get(target_id)
            if not source_node or not target_node:
                raise ValidationError("Link references missing node")
            self._validate_link_ports(link_input, source_node, target_node)
            link_type = self._infer_link_type(source_node, target_node, link_input.link_type)

            if link_input.id and link_input.id in links_by_id:
                link = links_by_id[link_input.id]
                link.link_type = link_type.value
                link.source_node_id = source_id
                link.source_port = link_input.source_port
                link.target_node_id = target_id
                link.target_port = link_input.target_port
                link.label = link_input.label
                link.source_label = link_input.source_label
                link.target_label = link_input.target_label
                link.cable_type = link_input.cable_type
                link.interface_class = link_input.interface_class
                link.link_role = link_input.link_role
                link.connection_type = link_input.connection_type
                link.speed = link_input.speed
                link.lag_group = link_input.lag_group
                link.redundancy_path = link_input.redundancy_path
                link.media = link_input.media
                link.module = link_input.module
                link.cable_length_m = link_input.cable_length_m
                link.wiring_rule_id = link_input.wiring_rule_id
                link.line_style = link_input.line_style
                link.deleted_at = None
                link.deleted_by = None
                link.updated_by = user_id
                incoming_link_ids.add(link.id)
            else:
                link = NetworkLink(
                    id=link_input.id or uuid.uuid4(),
                    topology_id=topology_id,
                    link_type=link_type.value,
                    source_node_id=source_id,
                    source_port=link_input.source_port,
                    target_node_id=target_id,
                    target_port=link_input.target_port,
                    label=link_input.label,
                    source_label=link_input.source_label,
                    target_label=link_input.target_label,
                    cable_type=link_input.cable_type,
                    interface_class=link_input.interface_class,
                    link_role=link_input.link_role,
                    connection_type=link_input.connection_type,
                    speed=link_input.speed,
                    lag_group=link_input.lag_group,
                    redundancy_path=link_input.redundancy_path,
                    media=link_input.media,
                    module=link_input.module,
                    cable_length_m=link_input.cable_length_m,
                    wiring_rule_id=link_input.wiring_rule_id,
                    line_style=link_input.line_style,
                    created_by=user_id,
                    updated_by=user_id,
                )
                entity.links.append(link)
                incoming_link_ids.add(link.id)

        for link_id, link in existing_links.items():
            if link_id not in incoming_link_ids:
                link.deleted_at = now
                link.deleted_by = user_id

        entity.updated_by = user_id
        await self.session.commit()
        return await self.get_detail(topology_id)

    def _validate_canvas(self, payload: CanvasSaveRequest) -> None:
        # 允许空拓扑（尚无设备时也可维护设备组/规则）；有连线则必须有节点
        if not payload.nodes:
            if payload.links:
                raise ValidationError("Link references unknown node")
            return

        temp_nodes: dict[uuid.UUID, CanvasNodeInput] = {}
        for idx, node in enumerate(payload.nodes):
            key = node.id or uuid.uuid4()
            temp_nodes[key] = node

        for link in payload.links:
            source = temp_nodes.get(link.source_node_id)
            target = temp_nodes.get(link.target_node_id)
            if not source or not target:
                raise ValidationError("Link references unknown node")
            self._validate_link_kind(link, source, target)
            self._validate_link_ports(link, source, target)

    async def _validate_devices(self, nodes: list[CanvasNodeInput]) -> None:
        for node in nodes:
            if not node.device_id:
                continue
            device = await self.device_repo.get_by_id(node.device_id)
            if not device:
                raise ValidationError(f"Associated device not found: {node.name}")

    def _infer_link_type(
        self,
        source: CanvasNodeInput | NetworkNode,
        target: CanvasNodeInput | NetworkNode,
        fallback: NetworkLinkType | None = None,
    ) -> NetworkLinkType:
        kinds = {_normalize_kind(source.kind), _normalize_kind(target.kind)}
        if kinds == {NetworkNodeKind.SWITCH.value, NetworkNodeKind.SERVER.value}:
            return NetworkLinkType.SWITCH_SERVER
        if kinds == {NetworkNodeKind.SWITCH.value, NetworkNodeKind.SECURITY.value}:
            return NetworkLinkType.SWITCH_SECURITY
        if kinds == {NetworkNodeKind.SWITCH.value}:
            return NetworkLinkType.SWITCH_SWITCH
        return fallback or NetworkLinkType.SWITCH_SWITCH

    def _validate_link_kind(
        self, link: CanvasLinkInput, source: CanvasNodeInput, target: CanvasNodeInput
    ) -> None:
        # 按端点 kind 自动纠正 link_type，避免布线残留 switch_switch 接服务器导致保存失败
        expected = self._infer_link_type(source, target, link.link_type)
        if link.link_type != expected:
            link.link_type = expected

    def _validate_link_ports(
        self,
        link: CanvasLinkInput,
        source: CanvasNodeInput | NetworkNode,
        target: CanvasNodeInput | NetworkNode,
    ) -> None:
        source_ports = _node_ports(source)
        target_ports = _node_ports(target)
        if link.source_port not in source_ports:
            raise ValidationError(f"Invalid source port: {link.source_port}")
        if link.target_port not in target_ports:
            raise ValidationError(f"Invalid target port: {link.target_port}")

    async def _load_device_briefs(
        self, device_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, NetworkDeviceBrief]:
        if not device_ids:
            return {}
        devices = await self.device_repo.list_by_ids_with_relations(device_ids)
        rack_ids = [d.rack_id for d in devices if d.rack_id]
        racks = await self.rack_repo.list_by_ids(rack_ids)
        rack_map = {rack.id: rack for rack in racks}
        rooms = await self.room_repo.list_by_ids_with_hierarchy(
            [rack.room_id for rack in racks]
        )
        room_map = {room.id: room for room in rooms}

        result: dict[uuid.UUID, NetworkDeviceBrief] = {}
        for device in devices:
            rack_id = device.rack_id
            room_id = None
            datacenter_id = None
            rack_code = None
            rack_seq_no = None
            room_name = None
            datacenter_name = None
            if device.rack_id and device.rack_id in rack_map:
                rack = rack_map[device.rack_id]
                rack_code = rack.code
                rack_seq_no = getattr(rack, "seq_no", None)
                room_id = rack.room_id
                room = room_map.get(rack.room_id)
                room_name = room.name if room else None
                floor = getattr(room, "floor", None) if room else None
                building = getattr(floor, "building", None) if floor else None
                datacenter = getattr(building, "datacenter", None) if building else None
                if datacenter is not None:
                    datacenter_id = datacenter.id
                    datacenter_name = datacenter.name
            device_type_name = device.device_type.name if device.device_type else None
            device_type_code = device.device_type.code if device.device_type else None
            model_name = device.model.name if getattr(device, "model", None) else None
            system_ip, bmc_ip, vip, *_ = _ip_fields_from_device(device)
            result[device.id] = NetworkDeviceBrief(
                device_id=device.id,
                name=device.name or device.hostname,
                hostname=device.hostname,
                rack_id=rack_id,
                room_id=room_id,
                datacenter_id=datacenter_id,
                rack_code=rack_code,
                rack_seq_no=rack_seq_no,
                room_name=room_name,
                datacenter_name=datacenter_name,
                u_position=device.u_position,
                ip_summary=system_ip,
                bmc_ip=bmc_ip,
                vip=vip,
                device_type_name=device_type_name,
                device_type_code=device_type_code,
                device_model_name=model_name,
                height_u=device.height_u,
            )
        return result

    def _to_node_response(
        self, node: NetworkNode, device: NetworkDeviceBrief | None
    ) -> NetworkNodeResponse:
        slots = None
        if node.slots:
            slots = [SlotConfig.model_validate(item) for item in node.slots]
        port_layout = None
        if node.port_layout:
            port_layout = PortLayout.model_validate(node.port_layout)
        raw_groups = getattr(node, "device_groups", None)
        groups: list[str] | None = None
        if isinstance(raw_groups, list) and raw_groups:
            seen: set[str] = set()
            groups = []
            for item in raw_groups:
                s = str(item or "").strip()
                if s and s not in seen:
                    seen.add(s)
                    groups.append(s)
        elif getattr(node, "device_group", None):
            groups = [str(node.device_group).strip()]
        return NetworkNodeResponse(
            id=node.id,
            topology_id=node.topology_id,
            kind=NetworkNodeKind(node.kind),
            name=node.name,
            device_id=node.device_id,
            device_model_id=getattr(node, "device_model_id", None),
            design_model_id=getattr(node, "design_model_id", None),
            contract_device_name=getattr(node, "contract_device_name", None),
            network_role=getattr(node, "network_role", None),
            device_group=(groups[0] if groups else getattr(node, "device_group", None)),
            device_groups=groups,
            pos_x=node.pos_x,
            pos_y=node.pos_y,
            switch_port_count=node.switch_port_count,
            slots=slots,
            port_layout=port_layout,
            on_canvas=bool(getattr(node, "on_canvas", True)),
            device=device,
        )
