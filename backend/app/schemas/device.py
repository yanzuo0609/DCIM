from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ManufacturerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class ManufacturerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str | None
    created_at: datetime


class DeviceCategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class DeviceCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str | None
    created_at: datetime


class DeviceTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class DeviceTypeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class DeviceTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    is_system: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class ProfileCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] | list[Any] | None = None
    description: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    payload: dict[str, Any] | list[Any] | None = None
    description: str | None = None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    payload: dict[str, Any] | list[Any] | None = None
    description: str | None
    created_at: datetime
    updated_at: datetime


class ParamCpuSpec(BaseModel):
    cores: int | None = Field(default=None, ge=1, description="CPU 核心数量")
    architecture: Literal["c86", "arm"] | None = Field(
        default=None, description="CPU 架构：c86 / arm"
    )
    model: str | None = Field(default=None, max_length=100)


class ParamMemorySpec(BaseModel):
    size_gb: float | None = Field(default=None, ge=0, description="内存总大小(GB)")
    ddr_type: str | None = Field(default=None, max_length=40, description="DDR 类型")
    modules: int | None = Field(default=None, ge=0, description="内存条数")


class ParamDiskSpec(BaseModel):
    size_gb: float | None = Field(default=None, ge=0, description="单盘大小(GB)")
    count: int | None = Field(default=None, ge=0, le=100, description="该规格磁盘块数")
    interface: str | None = Field(
        default=None, max_length=40, description="接口类型：SATA/SAS/NVMe 等"
    )
    media_type: Literal["ssd", "hdd", "nvme"] | None = Field(
        default=None, description="盘类型：ssd / hdd(机械) / nvme"
    )
    role: Literal["system", "data"] | None = Field(
        default=None,
        description="磁盘用途：system=系统盘 / data=数据盘，便于资源统计",
    )


# 前端默认：1 行系统盘 + 2 行数据盘；最多 20
PARAM_DISK_SPEC_DEFAULT_COUNT = 3
PARAM_DISK_SPEC_MAX_COUNT = 20
PARAM_DATA_DISK_EXPORT_SLOTS = 3


class ParamRaidSpec(BaseModel):
    model: str | None = Field(default=None, max_length=100, description="RAID 卡型号")
    params: str | None = Field(default=None, max_length=500, description="RAID 参数说明")


class ParamCustomField(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(default="", max_length=500)


class ParamProfilePayload(BaseModel):
    """参数档案结构化内容，存于 device_param_profile.payload。"""

    model_config = ConfigDict(extra="ignore")

    # 来自采购汇总的溯源信息（按设备名称同步时写入）
    source_device_name: str | None = Field(default=None, max_length=100)
    source_device_model: str | None = Field(default=None, max_length=100)
    source_manufacturer: str | None = Field(default=None, max_length=100)
    # 关联档案中的设备类型
    device_type_id: str | None = Field(default=None, max_length=64)
    # 详细参数（原参考型号/参数型号，可自由填写）
    detail_params: str | None = Field(default=None, max_length=1000)
    # 其他参数：风扇/电源/RAID/操作系统等合并文本
    other_params: str | None = Field(default=None, max_length=3000)

    cpu: ParamCpuSpec | None = None
    memory: ParamMemorySpec | None = None
    disks: list[ParamDiskSpec] = Field(
        default_factory=list,
        max_length=PARAM_DISK_SPEC_MAX_COUNT,
        description=(
            f"磁盘规格列表；建议区分系统盘/数据盘（role）；"
            f"前端默认 {PARAM_DISK_SPEC_DEFAULT_COUNT} 行"
        ),
    )
    fan_count: int | None = Field(default=None, ge=0, description="风扇数量（兼容旧数据）")
    fan_model: str | None = Field(default=None, max_length=100, description="风扇型号（兼容旧数据）")
    psu_power_w: float | None = Field(default=None, ge=0, description="电源功率(W)（兼容旧数据）")
    raid: ParamRaidSpec | None = None
    supported_os: list[str] = Field(default_factory=list, description="支持的操作系统（兼容旧数据）")
    custom: list[ParamCustomField] = Field(
        default_factory=list, description="手动添加的自定义参数"
    )

    @field_validator("device_type_id", mode="before")
    @classmethod
    def empty_type_to_none(cls, value: object) -> str | None:
        text = str(value or "").strip()
        return text or None

    @field_validator("detail_params", "other_params", "source_device_model", "source_manufacturer", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ParamProfileCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    payload: ParamProfilePayload | None = None
    description: str | None = None


class ParamProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    payload: ParamProfilePayload | None = None
    description: str | None = None


class ParamProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    payload: ParamProfilePayload | None = None
    description: str | None
    summary: str | None = None
    is_complete: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    source_device_name: str | None = None
    source_device_model: str | None = None
    source_manufacturer: str | None = None
    device_type_id: str | None = None
    detail_params: str | None = None
    other_params: str | None = None
    created_at: datetime
    updated_at: datetime


class ParamProfileSyncResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    total_summary: int = 0
    messages: list[str] = Field(default_factory=list)


class ParamProfileImportResult(BaseModel):
    updated: int = 0
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


def normalize_param_payload(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, ParamProfilePayload):
        return raw.model_dump(mode="json")
    if isinstance(raw, dict):
        return ParamProfilePayload.model_validate(raw).model_dump(mode="json")
    raise ValueError("参数档案 payload 须为对象")


def param_payload_summary(payload: ParamProfilePayload | dict | None) -> str | None:
    if not payload:
        return None
    data = (
        payload
        if isinstance(payload, ParamProfilePayload)
        else ParamProfilePayload.model_validate(payload)
    )
    parts: list[str] = []
    if data.cpu:
        cpu_bits = []
        if data.cpu.architecture:
            cpu_bits.append(data.cpu.architecture.upper())
        if data.cpu.cores:
            cpu_bits.append(f"{data.cpu.cores}核")
        if cpu_bits:
            parts.append("CPU " + "/".join(cpu_bits))
    if data.memory and data.memory.size_gb is not None:
        mem = f"{data.memory.size_gb:g}GB"
        if data.memory.ddr_type:
            mem += f" {data.memory.ddr_type}"
        if data.memory.modules:
            mem += f"×{data.memory.modules}"
        parts.append(f"内存 {mem}")
    if data.disks:
        system_parts: list[str] = []
        data_parts: list[str] = []
        other_parts: list[str] = []
        for d in data.disks:
            bit: list[str] = []
            if d.count and d.size_gb is not None:
                bit.append(f"{d.count}×{d.size_gb:g}GB")
            elif d.size_gb is not None:
                bit.append(f"{d.size_gb:g}GB")
            elif d.count:
                bit.append(f"{d.count}块")
            if d.media_type:
                bit.append(d.media_type.upper())
            if d.interface:
                bit.append(d.interface)
            if not bit:
                continue
            text = " ".join(bit)
            if d.role == "system":
                system_parts.append(text)
            elif d.role == "data":
                data_parts.append(text)
            else:
                other_parts.append(text)
        if system_parts:
            parts.append("系统盘 " + " + ".join(system_parts))
        if data_parts:
            parts.append("数据盘 " + " + ".join(data_parts))
        if other_parts and not system_parts and not data_parts:
            parts.append("磁盘 " + " + ".join(other_parts))
        elif other_parts:
            parts.append("其他盘 " + " + ".join(other_parts))
    if data.detail_params:
        parts.append(f"详细 {data.detail_params[:40]}")
    if data.other_params:
        parts.append(f"其他 {data.other_params[:40]}")
    elif data.psu_power_w is not None or (data.raid and data.raid.model) or data.supported_os:
        # 兼容旧结构化字段摘要
        if data.psu_power_w is not None:
            parts.append(f"电源 {data.psu_power_w:g}W")
        if data.raid and data.raid.model:
            parts.append(f"RAID {data.raid.model}")
        if data.supported_os:
            parts.append("OS " + "/".join(data.supported_os[:3]))
    return " · ".join(parts) if parts else None


def _disk_filled(disk: ParamDiskSpec | None) -> bool:
    if disk is None:
        return False
    return disk.size_gb is not None


def param_missing_fields(payload: ParamProfilePayload | dict | None) -> list[str]:
    """待完善判定：系统盘、数据盘。"""
    if not payload:
        return ["系统盘", "数据盘"]
    data = (
        payload
        if isinstance(payload, ParamProfilePayload)
        else ParamProfilePayload.model_validate(payload)
    )
    missing: list[str] = []
    disks = list(data.disks or [])
    has_system = any(d.role == "system" and _disk_filled(d) for d in disks)
    has_data = any(d.role == "data" and _disk_filled(d) for d in disks)
    if not has_system and not has_data:
        filled = [d for d in disks if _disk_filled(d)]
        if filled:
            has_system = True
            has_data = len(filled) >= 2
    if not has_system:
        missing.append("系统盘")
    if not has_data:
        missing.append("数据盘")
    return missing


def param_is_complete(payload: ParamProfilePayload | dict | None) -> bool:
    return not param_missing_fields(payload)


CredentialRole = Literal["admin", "readonly", "operator", "custom"]
OsType = Literal["linux", "windows", "unix", "esxi", "other"]


class CredentialAccount(BaseModel):
    """用户凭据；写入可为明文，落库加密，读取返回掩码。"""

    username: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, max_length=500)
    role: CredentialRole = "admin"
    note: str | None = Field(default=None, max_length=200)
    password_set: bool | None = Field(default=None, description="响应字段：是否已设置密码")


class BmcProfilePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    users: list[CredentialAccount] = Field(
        default_factory=list, description="BMC 用户列表（含自定义）"
    )


class SystemProfilePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    os_type: OsType | None = Field(default=None, description="操作系统类型")
    os_name: str | None = Field(default=None, max_length=100, description="系统名称/版本")
    users: list[CredentialAccount] = Field(
        default_factory=list, description="系统用户（管理员/只读等）"
    )
    custom_users: list[CredentialAccount] = Field(
        default_factory=list, description="自定义系统用户"
    )


class BmcProfileCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    payload: BmcProfilePayload | None = None
    description: str | None = None


class BmcProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    payload: BmcProfilePayload | None = None
    description: str | None = None


class BmcProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    payload: BmcProfilePayload | None = None
    description: str | None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


class SystemProfileCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    payload: SystemProfilePayload | None = None
    description: str | None = None


class SystemProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    payload: SystemProfilePayload | None = None
    description: str | None = None


class SystemProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    payload: SystemProfilePayload | None = None
    description: str | None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


def _encrypt_account_list(
    accounts: list[CredentialAccount] | list[dict] | None,
    previous: list[dict] | None = None,
) -> list[dict]:
    from app.core.credential_crypto import store_password

    prev_by_user: dict[str, str | None] = {}
    prev_by_idx: dict[int, str | None] = {}
    for idx, item in enumerate(previous or []):
        if isinstance(item, dict):
            prev_by_idx[idx] = item.get("password")
            user = item.get("username")
            if user:
                prev_by_user[str(user)] = item.get("password")

    result: list[dict] = []
    for idx, acc in enumerate(accounts or []):
        data = acc.model_dump() if isinstance(acc, CredentialAccount) else dict(acc)
        username = str(data.get("username") or "").strip()
        if not username:
            continue
        prev_pw = prev_by_user.get(username, prev_by_idx.get(idx))
        data["password"] = store_password(data.get("password"), prev_pw)
        data.pop("password_set", None)
        data["username"] = username
        result.append(data)
    return result


def _mask_account_list(accounts: list[dict] | None) -> list[dict]:
    from app.core.credential_crypto import mask_password_field

    masked: list[dict] = []
    for item in accounts or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        display, password_set = mask_password_field(row.get("password"))
        row["password"] = display
        row["password_set"] = password_set
        masked.append(row)
    return masked


def normalize_bmc_payload(raw: Any, previous: dict | None = None) -> dict[str, Any] | None:
    if raw is None:
        return None
    data = raw if isinstance(raw, BmcProfilePayload) else BmcProfilePayload.model_validate(raw)
    prev_users = (previous or {}).get("users") if isinstance(previous, dict) else None
    return {"users": _encrypt_account_list(data.users, prev_users)}


def normalize_system_payload(raw: Any, previous: dict | None = None) -> dict[str, Any] | None:
    if raw is None:
        return None
    data = (
        raw if isinstance(raw, SystemProfilePayload) else SystemProfilePayload.model_validate(raw)
    )
    prev = previous if isinstance(previous, dict) else {}
    return {
        "os_type": data.os_type,
        "os_name": data.os_name,
        "users": _encrypt_account_list(data.users, prev.get("users")),
        "custom_users": _encrypt_account_list(data.custom_users, prev.get("custom_users")),
    }


def mask_bmc_payload(raw: dict | None) -> BmcProfilePayload | None:
    if not raw or not isinstance(raw, dict):
        return None
    return BmcProfilePayload(users=_mask_account_list(raw.get("users")))


def mask_system_payload(raw: dict | None) -> SystemProfilePayload | None:
    if not raw or not isinstance(raw, dict):
        return None
    return SystemProfilePayload(
        os_type=raw.get("os_type"),
        os_name=raw.get("os_name"),
        users=_mask_account_list(raw.get("users")),
        custom_users=_mask_account_list(raw.get("custom_users")),
    )


def bmc_payload_summary(payload: BmcProfilePayload | dict | None) -> str | None:
    if not payload:
        return None
    users = (
        payload.users
        if isinstance(payload, BmcProfilePayload)
        else (payload.get("users") if isinstance(payload, dict) else [])
    ) or []
    if not users:
        return None
    labels: list[str] = []
    for u in users[:3]:
        if isinstance(u, CredentialAccount):
            labels.append(f"{u.username}({u.role})")
        elif isinstance(u, dict) and u.get("username"):
            labels.append(f"{u.get('username')}({u.get('role') or 'admin'})")
    text = f"BMC {len(users)}用户"
    if labels:
        text += " · " + ", ".join(labels)
    return text


def system_payload_summary(payload: SystemProfilePayload | dict | None) -> str | None:
    if not payload:
        return None
    if isinstance(payload, SystemProfilePayload):
        os_type = payload.os_type
        os_name = payload.os_name
        user_count = len(payload.users) + len(payload.custom_users)
    else:
        os_type = payload.get("os_type")
        os_name = payload.get("os_name")
        user_count = len(payload.get("users") or []) + len(payload.get("custom_users") or [])
    parts: list[str] = []
    if os_type:
        os_label = "其他" if os_type == "other" else str(os_type).upper()
        parts.append(f"{os_label}/{os_name}" if os_name else os_label)
    if user_count:
        parts.append(f"{user_count}用户")
    return " · ".join(parts) if parts else None


class DeviceModelCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    manufacturer_id: str | None = Field(
        default=None, description="可选；为空时自动归入「自定义」厂商"
    )
    category_id: str | None = None
    height_u: int = Field(default=1, ge=1, le=10)
    weight: Decimal | None = None
    power: Decimal | None = None
    depth: int | None = Field(default=None, ge=1)
    description: str | None = None


class DeviceModelUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    height_u: int | None = Field(default=None, ge=1, le=10)
    power: Decimal | None = None
    description: str | None = None
    port_layout: dict | None = None
    apply_device_name: str | None = Field(default=None, max_length=100)
    network_kind: str | None = Field(default=None, max_length=20)


class DeviceModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    manufacturer_id: str
    manufacturer_name: str | None = None
    category_id: str | None
    height_u: int
    weight: Decimal | None
    power: Decimal | None
    depth: int | None
    description: str | None
    port_layout: dict | None = None
    apply_device_name: str | None = None
    network_kind: str | None = None
    created_at: datetime


class DeviceModelPanelApply(BaseModel):
    """将网络设备定义面板应用到设备清单。

    mode=apply：仅可绑定尚未应用面板的设备（可指定 device_ids，空则全部未绑定）。
    mode=modify：仅可更新已应用面板的设备对应布局（可指定 device_ids，空则全部已绑定）。
    """

    port_layout: dict
    apply_device_name: str = Field(min_length=1, max_length=100)
    network_kind: str | None = Field(default=None, max_length=20)
    mode: Literal["apply", "modify"] = "apply"
    device_ids: list[str] = Field(default_factory=list)


class DeviceModelPanelApplyResult(BaseModel):
    device_model_id: str
    apply_device_name: str
    mode: str
    matched_device_count: int
    matched_device_ids: list[str] = Field(default_factory=list)
    applied_count: int = 0
    modified_count: int = 0
    skipped_count: int = 0
    skipped_device_ids: list[str] = Field(default_factory=list)
    message: str | None = None


class DevicePanelCandidate(BaseModel):
    id: str
    name: str | None = None
    hostname: str
    serial_number: str
    device_model_id: str
    device_model_name: str | None = None
    network_panel_bound: bool = False
    rack_code: str | None = None
    room_name: str | None = None
    u_position: int | None = None
    status: str


class DevicePanelCandidateList(BaseModel):
    apply_device_name: str
    items: list[DevicePanelCandidate]
    unbound_count: int = 0
    bound_count: int = 0


class DeviceCreate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    hostname: str | None = Field(default=None, min_length=1, max_length=100)
    serial_number: str = Field(min_length=1, max_length=100)
    device_model_id: str
    device_type_id: str | None = None
    param_profile_id: str | None = None
    system_profile_id: str | None = None
    bmc_profile_id: str | None = None
    contract_id: str | None = None
    height_u: int | None = Field(default=None, ge=1, le=10)
    weight: Decimal | None = None
    power: Decimal | None = None
    description: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    hostname: str | None = Field(default=None, min_length=1, max_length=100)
    serial_number: str | None = Field(default=None, min_length=1, max_length=100)
    device_model_id: str | None = None
    device_type_id: str | None = None
    param_profile_id: str | None = None
    system_profile_id: str | None = None
    bmc_profile_id: str | None = None
    contract_id: str | None = None
    height_u: int | None = Field(default=None, ge=1, le=10)
    weight: Decimal | None = None
    power: Decimal | None = None
    status: str | None = None
    description: str | None = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str | None = None
    hostname: str
    serial_number: str
    device_model_id: str
    device_model_name: str | None = None
    manufacturer_id: str | None = None
    manufacturer_name: str | None = None
    device_type_id: str | None = None
    device_type_name: str | None = None
    device_type_code: str | None = None
    param_profile_id: str | None = None
    system_profile_id: str | None = None
    bmc_profile_id: str | None = None
    contract_id: str | None = None
    contract_no: str | None = None
    project_no: str | None = None
    ip_summary: str | None = None
    bmc_ip: str | None = None
    vip: str | None = None
    rack_id: str | None
    rack_code: str | None = None
    room_id: str | None = None
    room_name: str | None = None
    u_position: int | None
    height_u: int
    weight: Decimal | None
    power: Decimal | None
    status: str
    description: str | None
    port_layout: dict | None = None
    network_kind: str | None = None
    panel_apply_device_name: str | None = None
    network_panel_bound: bool = False
    created_at: datetime
    updated_at: datetime


class DeviceBatchDeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1)


class DeviceBatchDeleteResult(BaseModel):
    deleted: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class BatchMountNewDevice(BaseModel):
    name: str | None = None
    hostname: str | None = None
    serial_number: str = Field(min_length=1, max_length=100)
    device_model_id: str
    device_type_id: str | None = None
    height_u: int | None = Field(default=None, ge=1, le=10)
    power: Decimal | None = None
    description: str | None = None


class BatchMountRequest(BaseModel):
    room_id: str
    device_ids: list[str] = Field(default_factory=list)
    new_devices: list[BatchMountNewDevice] = Field(default_factory=list)
    rack_ids: list[str] = Field(default_factory=list)
    row_nos: list[int] = Field(default_factory=list, description="可选：限定排号")
    column_nos: list[int] = Field(default_factory=list, description="可选：限定列号")
    per_rack_count: int = Field(default=1, ge=1, le=60)
    start_u: int = Field(default=1, ge=1, le=100, description="每柜上架起始 U 位")
    gap_u: int = Field(default=1, ge=0, le=10, description="设备间空闲 U 间隔，默认 1U")
    ip_ids: list[str] = Field(
        default_factory=list,
        description="可选：按顺序与上架设备 1:1 关联的已有 IP 记录",
    )


class BatchMountResult(BaseModel):
    mounted: int = 0
    created: int = 0
    ip_bound: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    assignments: list[dict[str, Any]] = Field(default_factory=list)


class BatchUnmountRequest(BaseModel):
    device_ids: list[str] = Field(min_length=1)


class BatchUnmountResult(BaseModel):
    unmounted: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
