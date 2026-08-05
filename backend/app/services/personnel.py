"""Personnel management service."""

from __future__ import annotations

import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.personnel import (
    PersonnelInternal,
    PersonnelOrgChart,
    PersonnelOrgLink,
    PersonnelOrgNode,
    PersonnelSupplier,
    PersonnelSupplierContract,
    PersonnelSupplierProduct,
)
from app.repositories.device import DeviceModelRepository, ManufacturerRepository
from app.repositories.device_contract import DeviceContractRepository
from app.repositories.personnel import (
    PersonnelInternalRepository,
    PersonnelOrgChartRepository,
    PersonnelOrgLinkRepository,
    PersonnelOrgNodeRepository,
    PersonnelSupplierRepository,
)
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.personnel import (
    InternalCreate,
    InternalResponse,
    InternalUpdate,
    OrgChartBrief,
    OrgChartCreate,
    OrgChartResponse,
    OrgChartUpdate,
    OrgLinkResponse,
    OrgNodeResponse,
    SupplierCreate,
    SupplierProductResponse,
    SupplierResponse,
    SupplierUpdate,
)


def _node_response(n: PersonnelOrgNode) -> OrgNodeResponse:
    return OrgNodeResponse(
        id=str(n.id),
        chart_id=str(n.chart_id),
        parent_id=str(n.parent_id) if n.parent_id else None,
        title=n.title,
        role_title=n.role_title,
        person_name=n.person_name,
        phone=n.phone,
        email=n.email,
        pos_x=n.pos_x,
        pos_y=n.pos_y,
        sort_order=n.sort_order,
    )


def _link_response(link: PersonnelOrgLink) -> OrgLinkResponse:
    return OrgLinkResponse(
        id=str(link.id),
        chart_id=str(link.chart_id),
        source_node_id=str(link.source_node_id),
        target_node_id=str(link.target_node_id),
    )


def _chart_response(chart: PersonnelOrgChart) -> OrgChartResponse:
    nodes = [n for n in (chart.nodes or []) if n.deleted_at is None]
    links = [lk for lk in (chart.links or []) if lk.deleted_at is None]
    return OrgChartResponse(
        id=str(chart.id),
        project_no=chart.project_no,
        name=chart.name,
        canvas_json=chart.canvas_json,
        nodes=[_node_response(n) for n in sorted(nodes, key=lambda x: x.sort_order)],
        links=[_link_response(lk) for lk in links],
        created_at=chart.created_at,
        updated_at=chart.updated_at,
    )


def _internal_response(row: PersonnelInternal) -> InternalResponse:
    return InternalResponse(
        id=str(row.id),
        name=row.name,
        role_title=row.role_title or "",
        phone=row.phone,
        email=row.email,
        company=row.company,
        project_no=row.project_no,
        org_node_id=str(row.org_node_id) if row.org_node_id else None,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PersonnelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chart_repo = PersonnelOrgChartRepository(session)
        self.node_repo = PersonnelOrgNodeRepository(session)
        self.link_repo = PersonnelOrgLinkRepository(session)
        self.internal_repo = PersonnelInternalRepository(session)
        self.supplier_repo = PersonnelSupplierRepository(session)
        self.mfg_repo = ManufacturerRepository(session)
        self.contract_repo = DeviceContractRepository(session)
        self.model_repo = DeviceModelRepository(session)

    # ---- org charts ----

    async def list_org_charts(self, project_no: str | None = None) -> list[OrgChartBrief]:
        charts = await self.chart_repo.list_by_project(project_no)
        result: list[OrgChartBrief] = []
        for c in charts:
            full = await self.chart_repo.get_with_graph(c.id)
            node_count = len([n for n in (full.nodes if full else []) if n.deleted_at is None])
            result.append(
                OrgChartBrief(
                    id=str(c.id),
                    project_no=c.project_no,
                    name=c.name,
                    node_count=node_count,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
            )
        return result

    async def get_org_chart(self, chart_id: uuid.UUID) -> OrgChartResponse:
        chart = await self.chart_repo.get_with_graph(chart_id)
        if not chart:
            raise NotFoundError("组织架构图不存在")
        return _chart_response(chart)

    async def create_org_chart(
        self, payload: OrgChartCreate, *, user_id: uuid.UUID | None = None
    ) -> OrgChartResponse:
        chart = PersonnelOrgChart(
            project_no=payload.project_no.strip(),
            name=payload.name.strip(),
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.chart_repo.create(chart)
        full = await self.chart_repo.get_with_graph(created.id)
        assert full
        return _chart_response(full)

    async def update_org_chart(
        self,
        chart_id: uuid.UUID,
        payload: OrgChartUpdate,
        *,
        user_id: uuid.UUID | None = None,
    ) -> OrgChartResponse:
        chart = await self.chart_repo.get_with_graph(chart_id)
        if not chart:
            raise NotFoundError("组织架构图不存在")

        if payload.name is not None:
            chart.name = payload.name.strip()
        if payload.project_no is not None:
            chart.project_no = payload.project_no.strip()
        if payload.canvas_json is not None:
            chart.canvas_json = payload.canvas_json
        chart.updated_by = user_id
        chart.version += 1

        if payload.nodes is not None or payload.links is not None:
            # 整图替换：硬删除旧节点/连线（避免 soft-delete 后同 UUID 主键冲突）
            for lk in list(chart.links or []):
                await self.session.delete(lk)
            for n in list(chart.nodes or []):
                n.parent_id = None
            await self.session.flush()
            for n in list(chart.nodes or []):
                await self.session.delete(n)
            await self.session.flush()
            chart.nodes = []
            chart.links = []

            id_map: dict[str, uuid.UUID] = {}
            for item in payload.nodes or []:
                client_id = (item.id or "").strip() or str(uuid.uuid4())
                try:
                    node_uuid = uuid.UUID(client_id) if item.id else uuid.uuid4()
                except ValueError:
                    node_uuid = uuid.uuid4()
                id_map[client_id] = node_uuid
                node = PersonnelOrgNode(
                    id=node_uuid,
                    chart_id=chart.id,
                    parent_id=None,
                    title=item.title.strip(),
                    role_title=(item.role_title or "").strip() or None,
                    person_name=(item.person_name or "").strip() or None,
                    phone=(item.phone or "").strip() or None,
                    email=(item.email or "").strip() or None,
                    pos_x=item.pos_x,
                    pos_y=item.pos_y,
                    sort_order=item.sort_order,
                    created_by=user_id,
                    updated_by=user_id,
                )
                await self.node_repo.create(node)

            for item in payload.nodes or []:
                client_id = (item.id or "").strip()
                if not client_id or not item.parent_id:
                    continue
                node_uuid = id_map.get(client_id)
                parent_uuid = id_map.get(item.parent_id)
                if not parent_uuid:
                    try:
                        parent_uuid = uuid.UUID(item.parent_id)
                    except ValueError:
                        parent_uuid = None
                if not node_uuid or not parent_uuid:
                    continue
                entity = await self.node_repo.get_by_id(node_uuid)
                if entity:
                    entity.parent_id = parent_uuid

            for item in payload.links or []:
                src = id_map.get(item.source_node_id)
                tgt = id_map.get(item.target_node_id)
                if not src:
                    try:
                        src = uuid.UUID(item.source_node_id)
                    except ValueError:
                        continue
                if not tgt:
                    try:
                        tgt = uuid.UUID(item.target_node_id)
                    except ValueError:
                        continue
                link = PersonnelOrgLink(
                    chart_id=chart.id,
                    source_node_id=src,
                    target_node_id=tgt,
                    created_by=user_id,
                    updated_by=user_id,
                )
                await self.link_repo.create(link)

        await self.session.flush()
        self.session.expire(chart)
        full = await self.chart_repo.get_with_graph(chart_id)
        assert full
        return _chart_response(full)

    async def delete_org_chart(
        self, chart_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> None:
        chart = await self.chart_repo.get_with_graph(chart_id)
        if not chart:
            raise NotFoundError("组织架构图不存在")
        for n in chart.nodes or []:
            if n.deleted_at is None:
                await self.node_repo.soft_delete(n, deleted_by=user_id)
        for lk in chart.links or []:
            if lk.deleted_at is None:
                await self.link_repo.soft_delete(lk, deleted_by=user_id)
        await self.chart_repo.soft_delete(chart, deleted_by=user_id)

    # ---- internal ----

    async def list_internals(
        self, params: PaginationParams
    ) -> tuple[list[InternalResponse], PaginationMeta]:
        items, total = await self.internal_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["name", "role_title", "phone", "email", "company", "project_no"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [_internal_response(i) for i in items], pagination

    async def create_internal(
        self, payload: InternalCreate, *, user_id: uuid.UUID | None = None
    ) -> InternalResponse:
        org_node_id = None
        if payload.org_node_id:
            try:
                org_node_id = uuid.UUID(payload.org_node_id)
            except ValueError as exc:
                raise ValidationError("无效的组织节点 ID", code=10004) from exc
        row = PersonnelInternal(
            name=payload.name.strip(),
            role_title=(payload.role_title or "").strip(),
            phone=(payload.phone or "").strip() or None,
            email=(payload.email or "").strip() or None,
            company=(payload.company or "").strip() or None,
            project_no=(payload.project_no or "").strip() or None,
            org_node_id=org_node_id,
            notes=(payload.notes or "").strip() or None,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.internal_repo.create(row)
        return _internal_response(created)

    async def update_internal(
        self,
        internal_id: uuid.UUID,
        payload: InternalUpdate,
        *,
        user_id: uuid.UUID | None = None,
    ) -> InternalResponse:
        row = await self.internal_repo.get_by_id(internal_id)
        if not row:
            raise NotFoundError("用户相关方不存在")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            row.name = str(data["name"]).strip()
        if "role_title" in data:
            row.role_title = (data["role_title"] or "").strip()
        for field in ("phone", "email", "company", "project_no", "notes"):
            if field in data:
                val = data[field]
                setattr(row, field, (str(val).strip() if val else None) or None)
        if "org_node_id" in data:
            raw = data["org_node_id"]
            if raw:
                try:
                    row.org_node_id = uuid.UUID(str(raw))
                except ValueError as exc:
                    raise ValidationError("无效的组织节点 ID", code=10004) from exc
            else:
                row.org_node_id = None
        row.updated_by = user_id
        row.version += 1
        await self.session.flush()
        return _internal_response(row)

    async def delete_internal(
        self, internal_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> None:
        row = await self.internal_repo.get_by_id(internal_id)
        if not row:
            raise NotFoundError("用户相关方不存在")
        await self.internal_repo.soft_delete(row, deleted_by=user_id)

    # ---- suppliers ----

    async def _supplier_response(self, row: PersonnelSupplier) -> SupplierResponse:
        mfg = await self.mfg_repo.get_by_id(row.manufacturer_id)
        contract_ids: list[str] = []
        contract_nos: list[str] = []
        for rel in row.contracts or []:
            if rel.deleted_at is not None:
                continue
            contract_ids.append(str(rel.contract_id))
            contract = await self.contract_repo.get_by_id(rel.contract_id)
            if contract:
                contract_nos.append(contract.contract_no)
        products: list[SupplierProductResponse] = []
        for p in row.products or []:
            if p.deleted_at is not None:
                continue
            products.append(
                SupplierProductResponse(
                    id=str(p.id),
                    device_model_id=str(p.device_model_id) if p.device_model_id else None,
                    device_name=p.device_name,
                    device_model_name=p.device_model_name,
                )
            )
        return SupplierResponse(
            id=str(row.id),
            name=row.name,
            role_title=row.role_title or "",
            phone=row.phone,
            email=row.email,
            wechat=row.wechat,
            manufacturer_id=str(row.manufacturer_id),
            manufacturer_name=mfg.name if mfg else None,
            notes=row.notes,
            contract_ids=contract_ids,
            contract_nos=contract_nos,
            products=products,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _replace_supplier_relations(
        self,
        supplier: PersonnelSupplier,
        *,
        contract_ids: list[str] | None,
        products: list | None,
        user_id: uuid.UUID | None,
    ) -> None:
        if contract_ids is not None:
            for rel in list(supplier.contracts or []):
                await self.session.delete(rel)
            await self.session.flush()
            seen: set[uuid.UUID] = set()
            for raw in contract_ids:
                try:
                    cid = uuid.UUID(raw)
                except ValueError as exc:
                    raise ValidationError(f"无效合同 ID: {raw}", code=10004) from exc
                if cid in seen:
                    continue
                seen.add(cid)
                contract = await self.contract_repo.get_by_id(cid)
                if not contract:
                    raise ValidationError(f"合同不存在: {raw}", code=10004)
                self.session.add(
                    PersonnelSupplierContract(
                        supplier_id=supplier.id,
                        contract_id=cid,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )

        if products is not None:
            for p in list(supplier.products or []):
                await self.session.delete(p)
            await self.session.flush()
            for item in products:
                model_id = None
                if getattr(item, "device_model_id", None):
                    try:
                        model_id = uuid.UUID(str(item.device_model_id))
                    except ValueError as exc:
                        raise ValidationError("无效设备型号 ID", code=10004) from exc
                    model = await self.model_repo.get_by_id(model_id)
                    if not model:
                        raise ValidationError("设备型号不存在", code=10004)
                self.session.add(
                    PersonnelSupplierProduct(
                        supplier_id=supplier.id,
                        device_model_id=model_id,
                        device_name=(getattr(item, "device_name", None) or None),
                        device_model_name=(getattr(item, "device_model_name", None) or None),
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )

    async def list_suppliers(
        self,
        params: PaginationParams,
        *,
        manufacturer_id: uuid.UUID | None = None,
    ) -> tuple[list[SupplierResponse], PaginationMeta]:
        items, total = await self.supplier_repo.list_with_relations(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            manufacturer_id=manufacturer_id,
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [await self._supplier_response(i) for i in items], pagination

    async def create_supplier(
        self, payload: SupplierCreate, *, user_id: uuid.UUID | None = None
    ) -> SupplierResponse:
        try:
            mfg_id = uuid.UUID(payload.manufacturer_id)
        except ValueError as exc:
            raise ValidationError("无效厂商 ID", code=10004) from exc
        mfg = await self.mfg_repo.get_by_id(mfg_id)
        if not mfg:
            raise ValidationError("厂商不存在", code=10004)

        row = PersonnelSupplier(
            name=payload.name.strip(),
            role_title=(payload.role_title or "").strip(),
            phone=(payload.phone or "").strip() or None,
            email=(payload.email or "").strip() or None,
            wechat=(payload.wechat or "").strip() or None,
            manufacturer_id=mfg_id,
            notes=(payload.notes or "").strip() or None,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.supplier_repo.create(row)
        await self._replace_supplier_relations(
            created,
            contract_ids=payload.contract_ids,
            products=payload.products,
            user_id=user_id,
        )
        await self.session.flush()
        supplier_id = created.id
        self.session.expire(created)
        full = await self.supplier_repo.get_with_relations(supplier_id)
        assert full
        return await self._supplier_response(full)

    async def update_supplier(
        self,
        supplier_id: uuid.UUID,
        payload: SupplierUpdate,
        *,
        user_id: uuid.UUID | None = None,
    ) -> SupplierResponse:
        row = await self.supplier_repo.get_with_relations(supplier_id)
        if not row:
            raise NotFoundError("供应商相关方不存在")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            row.name = str(data["name"]).strip()
        if "role_title" in data:
            row.role_title = (data["role_title"] or "").strip()
        for field in ("phone", "email", "wechat", "notes"):
            if field in data:
                val = data[field]
                setattr(row, field, (str(val).strip() if val else None) or None)
        if "manufacturer_id" in data and data["manufacturer_id"]:
            try:
                mfg_id = uuid.UUID(str(data["manufacturer_id"]))
            except ValueError as exc:
                raise ValidationError("无效厂商 ID", code=10004) from exc
            mfg = await self.mfg_repo.get_by_id(mfg_id)
            if not mfg:
                raise ValidationError("厂商不存在", code=10004)
            row.manufacturer_id = mfg_id
        row.updated_by = user_id
        row.version += 1

        await self._replace_supplier_relations(
            row,
            contract_ids=data.get("contract_ids") if "contract_ids" in data else None,
            products=payload.products if "products" in data else None,
            user_id=user_id,
        )
        await self.session.flush()
        self.session.expire(row)
        full = await self.supplier_repo.get_with_relations(supplier_id)
        assert full
        return await self._supplier_response(full)

    async def delete_supplier(
        self, supplier_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> None:
        row = await self.supplier_repo.get_with_relations(supplier_id)
        if not row:
            raise NotFoundError("供应商相关方不存在")
        for rel in row.contracts or []:
            await self.session.delete(rel)
        for p in row.products or []:
            await self.session.delete(p)
        await self.supplier_repo.soft_delete(row, deleted_by=user_id)
