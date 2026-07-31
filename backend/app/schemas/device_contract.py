from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QUANTITY_UNITS = frozenset({"台", "个", "件", "套"})


class DeviceContractItem(BaseModel):
    """合同内一条设备明细：名称、型号、厂商、数量、单价成对对应。"""

    device_name: str = Field(min_length=1, max_length=100)
    device_model_name: str = Field(min_length=1, max_length=100)
    manufacturer_name: str | None = Field(default=None, max_length=100)
    quantity: int = Field(default=0, ge=0, le=100000)
    quantity_unit: str = Field(default="台", max_length=10)
    unit_price: Decimal | None = Field(default=None, ge=0)
    price_unit: str = Field(default="yuan", pattern="^(yuan|wan)$")
    line_amount: Decimal | None = None

    @field_validator("device_name", "device_model_name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text[:100]

    @field_validator("manufacturer_name")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text[:100] if text else None

    @field_validator("quantity_unit")
    @classmethod
    def normalize_quantity_unit(cls, value: str | None) -> str:
        text = (value or "台").strip()
        return text if text in QUANTITY_UNITS else "台"


def _line_amount(quantity: int, unit_price: Decimal | None) -> Decimal | None:
    if unit_price is None or not quantity:
        return None
    return (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))


def _amount_in_yuan(amount: Decimal, price_unit: str) -> Decimal:
    if price_unit == "wan":
        return amount * Decimal("10000")
    return amount


def _line_amount_yuan(
    quantity: int, unit_price: Decimal | None, price_unit: str = "yuan"
) -> Decimal | None:
    raw = _line_amount(quantity, unit_price)
    if raw is None:
        return None
    return _amount_in_yuan(raw, price_unit).quantize(Decimal("0.01"))


def _normalize_items(items: list[DeviceContractItem] | None) -> list[DeviceContractItem]:
    if not items:
        return []
    result: list[DeviceContractItem] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.device_name, item.device_model_name, item.manufacturer_name or "")
        if key in seen:
            continue
        seen.add(key)
        unit = item.price_unit if item.price_unit in ("yuan", "wan") else "yuan"
        result.append(
            item.model_copy(
                update={
                    "price_unit": unit,
                    "line_amount": _line_amount(item.quantity, item.unit_price),
                }
            )
        )
    return result


def _normalize_name_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = (raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:100])
    return result


def _items_subtotal(items: list[DeviceContractItem]) -> Decimal | None:
    total = Decimal("0")
    has_any = False
    for item in items:
        unit = item.price_unit if item.price_unit in ("yuan", "wan") else "yuan"
        amount = _line_amount_yuan(item.quantity, item.unit_price, unit)
        if amount is not None:
            total += amount
            has_any = True
    return total.quantize(Decimal("0.01")) if has_any else None


def _pair_from_lists(
    names: list,
    models: list,
    manufacturers: list | None = None,
    fallback_manufacturer: str | None = None,
    fallback_quantity: int = 0,
    fallback_unit_price: Decimal | None = None,
) -> list[dict]:
    mfgs = manufacturers or []
    paired: list[dict] = []
    for i in range(max(len(names), len(models), len(mfgs) or 0)):
        name = (names[i] if i < len(names) else "") or ""
        model = (models[i] if i < len(models) else "") or ""
        mfg = (mfgs[i] if i < len(mfgs) else "") or ""
        if not str(name).strip() and not str(model).strip():
            continue
        mfg_text = str(mfg).strip() or (fallback_manufacturer or None)
        paired.append(
            {
                "device_name": str(name).strip() or str(model).strip(),
                "device_model_name": str(model).strip() or str(name).strip(),
                "manufacturer_name": mfg_text,
                "quantity": fallback_quantity if i == 0 else 0,
                "quantity_unit": "台",
                "unit_price": fallback_unit_price if i == 0 else None,
                "price_unit": "yuan",
            }
        )
    return paired


class DeviceContractCreate(BaseModel):
    contract_no: str = Field(min_length=1, max_length=100)
    project_no: str | None = Field(default=None, max_length=100)
    device_items: list[DeviceContractItem] = Field(min_length=1)
    # 兼容旧客户端
    device_names: list[str] | None = None
    device_model_names: list[str] | None = None
    manufacturer_names: list[str] | None = None
    manufacturer_name: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, ge=0, le=100000)
    unit_price: Decimal | None = Field(default=None, ge=0)
    contract_total: Decimal | None = Field(default=None, ge=0)
    price_unit: str = Field(default="yuan", pattern="^(yuan|wan)$")
    purchase_date: date | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_items_from_lists(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        items = data.get("device_items")
        fallback_mfg = (data.get("manufacturer_name") or "").strip() or None
        fallback_qty = int(data.get("quantity") or 0)
        fallback_price = data.get("unit_price")
        if items:
            filled = []
            for idx, raw in enumerate(items):
                if not isinstance(raw, dict):
                    filled.append(raw)
                    continue
                row = dict(raw)
                if fallback_mfg and not (row.get("manufacturer_name") or "").strip():
                    row["manufacturer_name"] = fallback_mfg
                if row.get("quantity") is None and idx == 0 and fallback_qty:
                    row["quantity"] = fallback_qty
                if row.get("unit_price") is None and idx == 0 and fallback_price is not None:
                    row["unit_price"] = fallback_price
                if not row.get("price_unit"):
                    row["price_unit"] = "yuan"
                if not row.get("quantity_unit"):
                    row["quantity_unit"] = "台"
                filled.append(row)
            data["device_items"] = filled
            return data
        names = data.get("device_names") or []
        models = data.get("device_model_names") or []
        mfgs = data.get("manufacturer_names") or []
        if names or models or mfgs:
            data["device_items"] = _pair_from_lists(
                names,
                models,
                mfgs,
                fallback_mfg,
                fallback_qty,
                fallback_price,
            )
        return data

    @field_validator("device_items")
    @classmethod
    def validate_items(cls, value: list[DeviceContractItem]) -> list[DeviceContractItem]:
        cleaned = _normalize_items(value)
        if not cleaned:
            raise ValueError("至少填写一条设备名称与型号")
        return cleaned


class DeviceContractUpdate(BaseModel):
    contract_no: str | None = Field(default=None, min_length=1, max_length=100)
    project_no: str | None = Field(default=None, max_length=100)
    device_items: list[DeviceContractItem] | None = None
    device_names: list[str] | None = None
    device_model_names: list[str] | None = None
    manufacturer_names: list[str] | None = None
    manufacturer_name: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, ge=0, le=100000)
    unit_price: Decimal | None = Field(default=None, ge=0)
    contract_total: Decimal | None = Field(default=None, ge=0)
    price_unit: str | None = Field(default=None, pattern="^(yuan|wan)$")
    purchase_date: date | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_items_from_lists(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if data.get("device_items") is not None:
            fallback_mfg = (data.get("manufacturer_name") or "").strip() or None
            filled = []
            for raw in data["device_items"] or []:
                if isinstance(raw, dict):
                    row = dict(raw)
                    if fallback_mfg and not (row.get("manufacturer_name") or "").strip():
                        row["manufacturer_name"] = fallback_mfg
                    if not row.get("price_unit"):
                        row["price_unit"] = "yuan"
                    if not row.get("quantity_unit"):
                        row["quantity_unit"] = "台"
                    filled.append(row)
                else:
                    filled.append(raw)
            data["device_items"] = filled
            return data
        names = data.get("device_names")
        models = data.get("device_model_names")
        mfgs = data.get("manufacturer_names")
        if names is None and models is None and mfgs is None:
            return data
        fallback = (data.get("manufacturer_name") or "").strip() or None
        data["device_items"] = _pair_from_lists(
            names or [],
            models or [],
            mfgs or [],
            fallback,
            int(data.get("quantity") or 0),
            data.get("unit_price"),
        )
        return data

    @field_validator("device_items")
    @classmethod
    def validate_items(
        cls, value: list[DeviceContractItem] | None
    ) -> list[DeviceContractItem] | None:
        if value is None:
            return None
        cleaned = _normalize_items(value)
        if not cleaned:
            raise ValueError("至少填写一条设备名称与型号")
        return cleaned


class DeviceContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_no: str
    project_no: str | None = None
    device_items: list[DeviceContractItem] = Field(default_factory=list)
    device_names: list[str] = Field(default_factory=list)
    device_model_names: list[str] = Field(default_factory=list)
    manufacturer_names: list[str] = Field(default_factory=list)
    device_name: str = ""
    device_model_name: str = ""
    manufacturer_name: str | None = None
    device_model_id: str | None = None
    quantity: int
    linked_count: int = 0
    # 兼容旧字段：不再作为合同级标准单价使用
    unit_price: Decimal | None = None
    contract_total: Decimal | None = None
    items_amount: Decimal | None = None
    price_unit: str = "yuan"
    total_amount: Decimal | None = None
    purchase_date: date | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class DeviceContractSummaryItem(BaseModel):
    manufacturer_name: str | None = None
    device_name: str | None = None
    device_model_name: str
    purchase_quantity: int
    linked_count: int
    contract_count: int
    avg_unit_price: Decimal | None = None


class DeviceContractBindRequest(BaseModel):
    device_ids: list[str] = Field(min_length=1)


class DeviceContractBindResult(BaseModel):
    bound: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class DeviceContractItemsImportResult(BaseModel):
    items: list[DeviceContractItem] = Field(default_factory=list)
    imported: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
