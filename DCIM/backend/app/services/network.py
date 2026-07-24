from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.network import NetworkLink, NetworkNode, NetworkTopology
from app.repositories.device import DeviceRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.network import (
    NetworkLinkRepository,
    NetworkNodeRepository,
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


class NetworkDesignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.topology_repo = NetworkTopologyRepository(session)
        self.node_repo = NetworkNodeRepository(session)
        self.link_repo = NetworkLinkRepository(session)
        self.device_repo = DeviceRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)

    async def list_topologies(
        self, params: PaginationParams
    ) -> tuple[list[NetworkTopologyResponse], PaginationMeta]:
        items, total = await self.topology_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort or "updated_at",
            order=params.order,
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
        entity = NetworkTopology(
            name=payload.name.strip(),
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.topology_repo.create(entity)
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
        entity.updated_by = user_id
        await self.session.flush()
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
        await self.session.flush()

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
                port_layout_payload = item.port_layout.model_dump()
            if item.kind in (NetworkNodeKind.SERVER, NetworkNodeKind.SECURITY):
                slots_payload = [slot.model_dump() for slot in (item.slots or default_slots())]

            if item.id and item.id in nodes_by_id:
                node = nodes_by_id[item.id]
                node.kind = item.kind.value
                node.name = item.name.strip()
                node.device_id = item.device_id
                node.pos_x = item.pos_x
                node.pos_y = item.pos_y
                node.switch_port_count = item.switch_port_count
                node.slots = slots_payload
                node.port_layout = port_layout_payload
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
                    pos_x=item.pos_x,
                    pos_y=item.pos_y,
                    switch_port_count=item.switch_port_count,
                    slots=slots_payload,
                    port_layout=port_layout_payload,
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

        for link in entity.links:
            if link.deleted_at is None:
                link.deleted_at = now
                link.deleted_by = user_id

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
            entity.links.append(
                NetworkLink(
                    id=link_input.id or uuid.uuid4(),
                    topology_id=topology_id,
                    link_type=link_input.link_type.value,
                    source_node_id=source_id,
                    source_port=link_input.source_port,
                    target_node_id=target_id,
                    target_port=link_input.target_port,
                    label=link_input.label,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )

        entity.updated_by = user_id
        await self.session.flush()
        return await self.get_detail(topology_id)

    def _validate_canvas(self, payload: CanvasSaveRequest) -> None:
        if not payload.nodes:
            raise ValidationError("Topology must contain at least one node")

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

    def _validate_link_kind(
        self, link: CanvasLinkInput, source: CanvasNodeInput, target: CanvasNodeInput
    ) -> None:
        kinds = {_normalize_kind(source.kind), _normalize_kind(target.kind)}
        if link.link_type == NetworkLinkType.SWITCH_SERVER:
            if kinds != {NetworkNodeKind.SWITCH.value, NetworkNodeKind.SERVER.value}:
                raise ValidationError("switch_server link requires one switch and one server")
        elif link.link_type == NetworkLinkType.SWITCH_SWITCH:
            if kinds != {NetworkNodeKind.SWITCH.value}:
                raise ValidationError("switch_switch link requires two switches")
        elif link.link_type == NetworkLinkType.SWITCH_SECURITY:
            if kinds != {NetworkNodeKind.SWITCH.value, NetworkNodeKind.SECURITY.value}:
                raise ValidationError("switch_security link requires one switch and one security device")

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
        rooms = await self.room_repo.list_by_ids([rack.room_id for rack in racks])
        room_map = {room.id: room for room in rooms}

        result: dict[uuid.UUID, NetworkDeviceBrief] = {}
        for device in devices:
            rack_code = None
            room_name = None
            if device.rack_id and device.rack_id in rack_map:
                rack = rack_map[device.rack_id]
                rack_code = rack.code
                room = room_map.get(rack.room_id)
                room_name = room.name if room else None
            device_type_name = device.device_type.name if device.device_type else None
            system_ip, bmc_ip, vip = _ip_fields_from_device(device)
            result[device.id] = NetworkDeviceBrief(
                device_id=device.id,
                name=device.name,
                hostname=device.hostname,
                rack_code=rack_code,
                room_name=room_name,
                u_position=device.u_position,
                ip_summary=system_ip,
                bmc_ip=bmc_ip,
                vip=vip,
                device_type_name=device_type_name,
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
        return NetworkNodeResponse(
            id=node.id,
            topology_id=node.topology_id,
            kind=NetworkNodeKind(node.kind),
            name=node.name,
            device_id=node.device_id,
            pos_x=node.pos_x,
            pos_y=node.pos_y,
            switch_port_count=node.switch_port_count,
            slots=slots,
            port_layout=port_layout,
            device=device,
        )
