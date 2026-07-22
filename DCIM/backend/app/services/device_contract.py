from __future__ import annotations

import math
import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.device import Device, DeviceContract
from app.repositories.device import DeviceRepository
from app.repositories.device_contract import DeviceContractRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.device_contract import (
    DeviceContractBindRequest,
    DeviceContractBindResult,
    DeviceContractCreate,
    DeviceContractItem,
    DeviceContractResponse,
    DeviceContractSummaryItem,
    DeviceContractUpdate,
    _items_subtotal,
    _normalize_items,
    _normalize_name_list,
)


def _join_names(names: list[str]) -> str:
    return "、".join(names)


def _split_legacy(text: str) -> list[str]:
    if not text.strip():
        return []
    parts = [
        p.strip()
        for p in text.replace("，", "、").replace(",", "、").replace(";", "、").split("、")
        if p.strip()
    ]
    return _normalize_name_list(parts) or [text.strip()]


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _items_from_entity(entity: DeviceContract) -> list[DeviceContractItem]:
    """优先读 device_items JSON；否则按平行数组 + 合同级数量/单价回填。"""
    raw_items = getattr(entity, "device_items", None)
    if isinstance(raw_items, list) and raw_items:
        parsed: list[DeviceContractItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("device_name") or "").strip()
            model = str(raw.get("device_model_name") or "").strip()
            if not name and not model:
                continue
            mfg = str(raw.get("manufacturer_name") or "").strip() or None
            qty = int(raw.get("quantity") or 0)
            price = _to_decimal(raw.get("unit_price"))
            unit = str(raw.get("price_unit") or "yuan").strip().lower()
            if unit not in ("yuan", "wan"):
                unit = "yuan"
            qty_unit = str(raw.get("quantity_unit") or "台").strip()
            if qty_unit not in ("台", "个", "件", "套"):
                qty_unit = "台"
            parsed.append(
                DeviceContractItem(
                    device_name=name or model,
                    device_model_name=model or name,
                    manufacturer_name=mfg,
                    quantity=max(qty, 0),
                    quantity_unit=qty_unit,
                    unit_price=price,
                    price_unit=unit,
                )
            )
        return _normalize_items(parsed)

    raw_names = getattr(entity, "device_names", None)
    raw_models = getattr(entity, "device_model_names", None)
    raw_mfgs = getattr(entity, "manufacturer_names", None)
    names = (
        _normalize_name_list([str(x) for x in raw_names])
        if isinstance(raw_names, list) and raw_names
        else _split_legacy(entity.device_name or "")
    )
    models = (
        _normalize_name_list([str(x) for x in raw_models])
        if isinstance(raw_models, list) and raw_models
        else _split_legacy(entity.device_model_name or "")
    )
    if isinstance(raw_mfgs, list) and raw_mfgs:
        mfgs = [(str(x).strip()[:100] if x is not None else "") for x in raw_mfgs]
    else:
        legacy_mfg = (entity.manufacturer_name or "").strip()
        mfgs = [legacy_mfg] if legacy_mfg else []
    if not names and not models:
        return []
    count = max(len(names), len(models), len(mfgs) or 0)
    fallback_mfg = (entity.manufacturer_name or "").strip() or None
    fallback_qty = int(entity.quantity or 0)
    fallback_price = entity.unit_price
    items: list[DeviceContractItem] = []
    for i in range(count):
        name = names[i] if i < len(names) else ""
        model = models[i] if i < len(models) else ""
        mfg = mfgs[i] if i < len(mfgs) else ""
        if not name and not model:
            continue
        items.append(
            DeviceContractItem(
                device_name=name or model,
                device_model_name=model or name,
                manufacturer_name=(mfg or fallback_mfg) or None,
                quantity=fallback_qty if i == 0 else 0,
                quantity_unit="台",
                unit_price=fallback_price if i == 0 else None,
            )
        )
    return _normalize_items(items)


def _persist_items(
    items: list[DeviceContractItem],
) -> tuple[list[dict], list[str], list[str], list[str], str, str, str | None, int]:
    payload = [
        {
            "device_name": i.device_name,
            "device_model_name": i.device_model_name,
            "manufacturer_name": i.manufacturer_name,
            "quantity": int(i.quantity or 0),
            "quantity_unit": i.quantity_unit if i.quantity_unit in ("台", "个", "件", "套") else "台",
            "unit_price": str(i.unit_price) if i.unit_price is not None else None,
            "price_unit": i.price_unit if i.price_unit in ("yuan", "wan") else "yuan",
        }
        for i in items
    ]
    names = [i.device_name for i in items]
    models = [i.device_model_name for i in items]
    mfgs = [i.manufacturer_name or "" for i in items]
    joined_mfg_parts = _normalize_name_list([m for m in mfgs if m])
    joined_mfg = _join_names(joined_mfg_parts) or None
    total_qty = sum(int(i.quantity or 0) for i in items)
    return (
        payload,
        names,
        models,
        mfgs,
        _join_names(names),
        _join_names(models),
        joined_mfg,
        total_qty,
    )


def _resolve_contract_total(
    *,
    explicit: Decimal | None,
    items: list[DeviceContractItem],
    legacy_unit_price: Decimal | None = None,
    legacy_quantity: int = 0,
) -> Decimal | None:
    if explicit is not None:
        return explicit.quantize(Decimal("0.01"))
    subtotal = _items_subtotal(items)
    if subtotal is not None:
        return subtotal
    if legacy_unit_price is not None and legacy_quantity:
        return (legacy_unit_price * Decimal(legacy_quantity)).quantize(Decimal("0.01"))
    return None


class DeviceContractService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DeviceContractRepository(session)
        self.device_repo = DeviceRepository(session)

    def _to_response(
        self, entity: DeviceContract, *, linked_count: int = 0
    ) -> DeviceContractResponse:
        items = _items_from_entity(entity)
        names = [i.device_name for i in items]
        models = [i.device_model_name for i in items]
        mfgs = [i.manufacturer_name or "" for i in items]
        joined_mfg = _join_names(_normalize_name_list([m for m in mfgs if m])) or None
        items_amount = _items_subtotal(items)
        quantity = sum(int(i.quantity or 0) for i in items) or int(entity.quantity or 0)
        price_unit = getattr(entity, "price_unit", None) or "yuan"
        contract_total = getattr(entity, "contract_total", None)
        if contract_total is None:
            contract_total = _resolve_contract_total(
                explicit=None,
                items=items,
                legacy_unit_price=entity.unit_price,
                legacy_quantity=int(entity.quantity or 0),
            )
        return DeviceContractResponse(
            id=str(entity.id),
            contract_no=entity.contract_no,
            project_no=entity.project_no,
            device_items=items,
            device_names=names,
            device_model_names=models,
            manufacturer_names=mfgs,
            device_name=_join_names(names),
            device_model_name=_join_names(models),
            manufacturer_name=joined_mfg or entity.manufacturer_name,
            device_model_id=str(entity.device_model_id) if entity.device_model_id else None,
            quantity=quantity,
            linked_count=linked_count,
            unit_price=None,
            contract_total=contract_total,
            items_amount=items_amount,
            price_unit=price_unit,
            total_amount=contract_total,
            purchase_date=entity.purchase_date,
            description=entity.description,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list(
        self,
        params: PaginationParams,
    ) -> tuple[list[DeviceContractResponse], PaginationMeta]:
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort or "purchase_date",
            order=params.order or "desc",
            search_fields=[
                "contract_no",
                "project_no",
                "device_name",
                "device_model_name",
                "manufacturer_name",
            ],
        )
        counts = await self.repo.linked_counts([i.id for i in items])
        enriched = [
            self._to_response(item, linked_count=counts.get(item.id, 0)) for item in items
        ]
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return enriched, pagination

    async def get(self, entity_id: uuid.UUID) -> DeviceContractResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("合同信息不存在", code=10003)
        linked = await self.repo.count_linked_devices(entity_id)
        return self._to_response(entity, linked_count=linked)

    async def create(
        self, payload: DeviceContractCreate, user_id: uuid.UUID | None = None
    ) -> DeviceContractResponse:
        if await self.repo.get_by_contract_no(payload.contract_no.strip()):
            raise ConflictError("采购合同编号已存在")
        items = list(payload.device_items)
        (
            items_payload,
            names,
            models,
            mfgs,
            joined_names,
            joined_models,
            joined_mfg,
            total_qty,
        ) = _persist_items(items)
        contract_total = _resolve_contract_total(
            explicit=payload.contract_total,
            items=items,
            legacy_unit_price=payload.unit_price,
            legacy_quantity=int(payload.quantity or 0),
        )
        entity = DeviceContract(
            contract_no=payload.contract_no.strip(),
            project_no=payload.project_no.strip() if payload.project_no else None,
            device_items=items_payload,
            device_names=names,
            device_model_names=models,
            manufacturer_names=mfgs,
            device_name=joined_names,
            device_model_name=joined_models,
            manufacturer_name=joined_mfg
            or (payload.manufacturer_name.strip() if payload.manufacturer_name else None),
            device_model_id=None,
            quantity=total_qty,
            unit_price=None,
            contract_total=contract_total,
            price_unit=payload.price_unit or "yuan",
            purchase_date=payload.purchase_date,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        return self._to_response(created, linked_count=0)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: DeviceContractUpdate,
        user_id: uuid.UUID | None = None,
    ) -> DeviceContractResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("合同信息不存在", code=10003)

        if payload.contract_no is not None:
            new_no = payload.contract_no.strip()
            if new_no != entity.contract_no:
                existing = await self.repo.get_by_contract_no(new_no)
                if existing and existing.id != entity.id:
                    raise ConflictError("采购合同编号已存在")
                entity.contract_no = new_no
        if payload.project_no is not None:
            entity.project_no = payload.project_no.strip() or None
        if payload.device_items is not None:
            items = list(payload.device_items)
            (
                items_payload,
                names,
                models,
                mfgs,
                joined_names,
                joined_models,
                joined_mfg,
                total_qty,
            ) = _persist_items(items)
            entity.device_items = items_payload
            entity.device_names = names
            entity.device_model_names = models
            entity.manufacturer_names = mfgs
            entity.device_name = joined_names
            entity.device_model_name = joined_models
            entity.manufacturer_name = joined_mfg
            entity.quantity = total_qty
            entity.unit_price = None
            if payload.contract_total is None:
                entity.contract_total = _resolve_contract_total(explicit=None, items=items)
        elif payload.manufacturer_name is not None:
            entity.manufacturer_name = payload.manufacturer_name.strip() or None
        if payload.contract_total is not None:
            entity.contract_total = payload.contract_total.quantize(Decimal("0.01"))
        if payload.price_unit is not None:
            entity.price_unit = payload.price_unit
        if payload.purchase_date is not None:
            entity.purchase_date = payload.purchase_date
        if payload.description is not None:
            entity.description = payload.description

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        await self.session.refresh(entity)
        linked = await self.repo.count_linked_devices(entity_id)
        return self._to_response(entity, linked_count=linked)

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("合同信息不存在", code=10003)
        stmt = select(Device).where(
            Device.contract_id == entity_id, Device.deleted_at.is_(None)
        )
        devices = list((await self.session.execute(stmt)).scalars().all())
        for device in devices:
            device.contract_id = None
            device.updated_by = user_id
            device.version += 1
        await self.repo.soft_delete(entity, deleted_by=user_id)

    async def bind_devices(
        self,
        entity_id: uuid.UUID,
        payload: DeviceContractBindRequest,
        user_id: uuid.UUID | None = None,
    ) -> DeviceContractBindResult:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("合同信息不存在", code=10003)
        bound = 0
        skipped = 0
        errors: list[str] = []
        for raw_id in payload.device_ids:
            try:
                device_id = uuid.UUID(raw_id)
            except ValueError:
                skipped += 1
                continue
            device = await self.device_repo.get_by_id(device_id)
            if not device:
                skipped += 1
                continue
            if device.contract_id == entity.id:
                skipped += 1
                continue
            device.contract_id = entity.id
            device.updated_by = user_id
            device.version += 1
            bound += 1
        await self.session.flush()
        return DeviceContractBindResult(bound=bound, skipped=skipped, errors=errors)

    async def unbind_devices(
        self,
        entity_id: uuid.UUID,
        payload: DeviceContractBindRequest,
        user_id: uuid.UUID | None = None,
    ) -> DeviceContractBindResult:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("合同信息不存在", code=10003)
        bound = 0
        skipped = 0
        errors: list[str] = []
        for raw_id in payload.device_ids:
            try:
                device_id = uuid.UUID(raw_id)
            except ValueError:
                skipped += 1
                continue
            device = await self.device_repo.get_by_id(device_id)
            if not device or device.contract_id != entity.id:
                skipped += 1
                continue
            device.contract_id = None
            device.updated_by = user_id
            device.version += 1
            bound += 1
        await self.session.flush()
        return DeviceContractBindResult(bound=bound, skipped=skipped, errors=errors)

    async def summary(self) -> list[DeviceContractSummaryItem]:
        """按厂商 + 设备名称/型号成对展开汇总（数量取明细数量）。"""
        stmt = select(DeviceContract).where(DeviceContract.deleted_at.is_(None))
        contracts = list((await self.session.execute(stmt)).scalars().all())

        buckets: dict[tuple[str | None, str, str], dict] = {}
        for entity in contracts:
            items = _items_from_entity(entity) or [
                DeviceContractItem(device_name="—", device_model_name="—")
            ]
            for item in items:
                key = (item.manufacturer_name, item.device_name, item.device_model_name)
                bucket = buckets.setdefault(
                    key, {"qty": 0, "contract_ids": set(), "linked": 0}
                )
                bucket["qty"] += int(item.quantity or 0)
                bucket["contract_ids"].add(entity.id)

        linked_stmt = (
            select(Device.contract_id, func.count(Device.id))
            .where(Device.contract_id.is_not(None), Device.deleted_at.is_(None))
            .group_by(Device.contract_id)
        )
        linked_by_contract = {
            cid: int(cnt) for cid, cnt in (await self.session.execute(linked_stmt)).all() if cid
        }

        result: list[DeviceContractSummaryItem] = []
        for (mfg, name, model), bucket in sorted(
            buckets.items(), key=lambda x: ((x[0][0] or ""), x[0][1], x[0][2])
        ):
            linked = sum(linked_by_contract.get(cid, 0) for cid in bucket["contract_ids"])
            result.append(
                DeviceContractSummaryItem(
                    manufacturer_name=mfg,
                    device_name=name,
                    device_model_name=model,
                    purchase_quantity=bucket["qty"],
                    linked_count=linked,
                    contract_count=len(bucket["contract_ids"]),
                    avg_unit_price=None,
                )
            )
        return result
