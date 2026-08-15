"""IT infrastructure model taxonomy and default attribute schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.network_model_design import (
    AttributeFieldDef,
    CategoryAttributeSchema,
    TaxonomyCategory,
    TaxonomyOption,
)

TAXONOMY: list[TaxonomyCategory] = [
    TaxonomyCategory(
        value="server",
        label="服务器",
        subtypes=[
            TaxonomyOption(value="compute", label="计算服务器"),
            TaxonomyOption(value="storage", label="存储服务器"),
            TaxonomyOption(value="hpc", label="高性能服务器"),
        ],
    ),
    TaxonomyCategory(
        value="network",
        label="网络设备",
        subtypes=[
            TaxonomyOption(value="switch", label="交换机"),
            TaxonomyOption(value="router", label="路由器"),
            TaxonomyOption(value="load_balancer", label="负载均衡"),
            TaxonomyOption(value="optical_gate", label="光闸"),
        ],
    ),
    TaxonomyCategory(
        value="security",
        label="安全设备",
        subtypes=[
            TaxonomyOption(value="firewall", label="防火墙"),
            TaxonomyOption(value="vpn", label="VPN"),
            TaxonomyOption(value="ddos", label="DDoS 防护"),
            TaxonomyOption(value="ips", label="IPS"),
            TaxonomyOption(value="ids", label="IDS"),
            TaxonomyOption(value="net_audit", label="网络审计"),
            TaxonomyOption(value="crypto", label="密码机"),
        ],
    ),
    TaxonomyCategory(
        value="software",
        label="软件",
        subtypes=[
            TaxonomyOption(value="cloud", label="云平台"),
            TaxonomyOption(value="bigdata", label="大数据平台"),
            TaxonomyOption(value="mysql", label="MySQL"),
        ],
    ),
]

SIM_ENGINE_OPTIONS = [
    TaxonomyOption(value="eve-ng", label="Eve-NG"),
    TaxonomyOption(value="gns3", label="GNS3（预留）"),
    TaxonomyOption(value="none", label="不仿真"),
]

SIM_ATTRIBUTE_FIELDS = [
    AttributeFieldDef(
        key="sim_engine",
        label="仿真引擎",
        type="select",
        options=SIM_ENGINE_OPTIONS,
        description="拓扑实验室同步时使用的引擎",
    ),
    AttributeFieldDef(
        key="sim_image",
        label="仿真镜像/模板",
        type="string",
        description="Eve-NG template 名，如 viosl2 / asav / linux",
    ),
    AttributeFieldDef(key="sim_icon", label="仿真图标", type="string", description="Eve-NG 图标文件名，可选"),
    AttributeFieldDef(key="sim_ram", label="仿真内存(MB)", type="int", min=128, max=65536),
    AttributeFieldDef(key="sim_cpu", label="仿真 CPU 数", type="int", min=1, max=16),
]


SLOT_TYPE_OPTIONS = [
    TaxonomyOption(value="nic_1g", label="千兆接口"),
    TaxonomyOption(value="nic_10g", label="万兆接口"),
    TaxonomyOption(value="raid", label="RAID卡"),
    TaxonomyOption(value="disk_bay", label="磁盘插槽"),
    TaxonomyOption(value="blank", label="空白卡槽"),
]

RAID_LEVEL_OPTIONS = [
    TaxonomyOption(value="raid0", label="RAID 0"),
    TaxonomyOption(value="raid1", label="RAID 1"),
    TaxonomyOption(value="raid5", label="RAID 5"),
    TaxonomyOption(value="raid10", label="RAID 10"),
    TaxonomyOption(value="raid6", label="RAID 6"),
    TaxonomyOption(value="jbod", label="JBOD"),
]

UPLINK_POS_OPTIONS = [
    TaxonomyOption(value="middle", label="中间"),
    TaxonomyOption(value="right", label="右侧"),
]

SWITCH_ROLE_OPTIONS = [
    TaxonomyOption(value="gigabit", label="千兆交换机"),
    TaxonomyOption(value="ten_gigabit", label="万兆交换机"),
    TaxonomyOption(value="core", label="核心交换机"),
    TaxonomyOption(value="aggregation", label="汇聚交换机"),
]

PORT_SPEED_OPTIONS = [
    TaxonomyOption(value="1g", label="1G"),
    TaxonomyOption(value="10g", label="10G"),
    TaxonomyOption(value="25g", label="25G"),
    TaxonomyOption(value="40_100g", label="40/100G"),
]

CORE_CARD_TYPE_OPTIONS = [
    TaxonomyOption(value="gigabit", label="千兆板卡"),
    TaxonomyOption(value="ten_gigabit", label="万兆板卡"),
    TaxonomyOption(value="100g", label="100G板卡"),
    TaxonomyOption(value="blank", label="空白板卡"),
]

IFACE_BOARD_OPTIONS = [
    TaxonomyOption(value="10ge", label="万兆以太网光接口板"),
    TaxonomyOption(value="25ge", label="25GE 以太网光接口板"),
    TaxonomyOption(value="40ge", label="40GE 光接口板"),
    TaxonomyOption(value="100ge", label="100GE 光接口板"),
    TaxonomyOption(value="400ge", label="400GE 光接口板"),
]

AIRFLOW_OPTIONS = [
    TaxonomyOption(value="front_to_rear", label="标准前后风道"),
    TaxonomyOption(value="custom", label="自定义"),
]

MEMORY_TYPE_OPTIONS = [
    TaxonomyOption(value="ddr4", label="DDR4"),
    TaxonomyOption(value="ddr5", label="DDR5"),
    TaxonomyOption(value="other", label="其他"),
]
DISK_SIZE_OPTIONS = [
    TaxonomyOption(value="2.5", label="2.5 寸"),
    TaxonomyOption(value="3.5", label="3.5 寸"),
]
DISK_PROTO_OPTIONS = [
    TaxonomyOption(value="sas_sata", label="SAS/SATA"),
    TaxonomyOption(value="sas", label="SAS"),
    TaxonomyOption(value="sata", label="SATA"),
    TaxonomyOption(value="nvme", label="NVMe"),
]
SSD_IFACE_OPTIONS = [
    TaxonomyOption(value="sata", label="SATA"),
    TaxonomyOption(value="nvme", label="NVMe"),
    TaxonomyOption(value="m.2", label="M.2"),
    TaxonomyOption(value="u.2", label="U.2"),
    TaxonomyOption(value="sas", label="SAS"),
    TaxonomyOption(value="other", label="其他"),
]
SSD_TYPE_OPTIONS = [
    TaxonomyOption(value="sata", label="SATA SSD"),
    TaxonomyOption(value="nvme", label="NVMe SSD"),
    TaxonomyOption(value="sas", label="SAS SSD"),
    TaxonomyOption(value="mixed", label="混合"),
    TaxonomyOption(value="other", label="其他"),
]
PSU_REDUNDANCY_OPTIONS = [
    TaxonomyOption(value="1+1", label="1+1 冗余"),
    TaxonomyOption(value="1+n", label="1+N 冗余"),
    TaxonomyOption(value="other", label="其他"),
]
FLEX_SPEED_OPTIONS = [
    TaxonomyOption(value="10ge", label="10GE 光口"),
    TaxonomyOption(value="25ge", label="25GE 光口"),
]


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _map_core_card_type(raw: str) -> str:
    if raw in ("25g", "ten_gigabit"):
        return "ten_gigabit"
    if raw in ("40g", "100g", "400g"):
        return "100g"
    if raw in ("gigabit", "blank"):
        return raw
    return "ten_gigabit"


def _normalize_blank_panel_rows(raw: Any, height: int, expansion: int) -> list[int]:
    """空白面板行号（1-based），数量 = 整机 U − 扩展插槽。"""
    want = max(0, height - expansion)
    used: set[int] = set()
    kept: list[int] = []
    if isinstance(raw, list):
        for item in raw:
            try:
                row = int(item)
            except (TypeError, ValueError):
                continue
            if row < 1 or row > height or row in used:
                continue
            used.add(row)
            kept.append(row)
    kept.sort()
    while len(kept) > want:
        kept.pop()
    row = height
    while len(kept) < want and row >= 1:
        if row not in used:
            used.add(row)
            kept.append(row)
        row -= 1
    kept.sort()
    return kept


_SYSTEM_PORT_NS = {
    "eth_mgmt": "eth-mgmt",
    "console": "console",
    "usb": "usb",
    "stack": "stack",
}
_SYSTEM_PORT_CODE = {
    "eth_mgmt": "MGT",
    "console": "CON",
    "usb": "USB",
    "stack": "STACK",
}
_SYSTEM_PORT_DEFAULTS = {
    "eth_mgmt": {"iface_type": "copper", "speed": "1GE", "module": "RJ45", "connector": "RJ45", "fiber_mode": "na"},
    "console": {"iface_type": "copper", "speed": "1GE", "module": "RJ45", "connector": "RJ45", "fiber_mode": "na"},
    "usb": {"iface_type": "copper", "speed": "USB", "module": "USB", "connector": "USB", "fiber_mode": "na"},
    "stack": {"iface_type": "optical", "speed": "10GE", "module": "SFP+", "connector": "LC", "fiber_mode": "mm"},
}


def _normalize_system_ports(attrs: dict[str, Any], core: bool) -> None:
    """为管理口 / Console / USB / 堆叠口写入稳定唯一 ID 与编号。"""
    if core:
        counts = {
            "console": _clamp_int(attrs.get("console_ports"), 1, 0, 8),
            "eth_mgmt": _clamp_int(attrs.get("eth_mgmt_ports"), 1, 0, 8),
            "usb": _clamp_int(attrs.get("usb_ports"), 1, 0, 8),
            "stack": _clamp_int(attrs.get("stack_cluster_ports"), 2, 0, 16),
        }
    else:
        counts = {
            "console": 0,
            "eth_mgmt": _clamp_int(attrs.get("mgmt_ports"), 1, 0, 8),
            "usb": 0,
            "stack": _clamp_int(attrs.get("stack_cluster_ports"), 0, 0, 16),
        }
    prev: dict[tuple[str, int], dict[str, Any]] = {}
    raw = attrs.get("system_ports")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "")
            if kind not in _SYSTEM_PORT_NS:
                continue
            try:
                index = max(0, int(item.get("index") or 0))
            except (TypeError, ValueError):
                continue
            prev[(kind, index)] = item
    next_ports: list[dict[str, Any]] = []
    for kind in ("console", "eth_mgmt", "usb", "stack"):
        count = counts[kind]
        defaults = _SYSTEM_PORT_DEFAULTS[kind]
        for i in range(count):
            old = prev.get((kind, i)) or {}
            iface = str(old.get("iface_type") or defaults["iface_type"])
            if iface not in ("optical", "copper"):
                iface = defaults["iface_type"]
            next_ports.append(
                {
                    "kind": kind,
                    "index": i,
                    "id": f"{_SYSTEM_PORT_NS[kind]}-p{i}",
                    "code": f"{_SYSTEM_PORT_CODE[kind]}{i + 1}",
                    "iface_type": iface,
                    "speed": str(old.get("speed") or defaults["speed"]),
                    "module": str(old.get("module") or defaults["module"]),
                    "connector": str(old.get("connector") or defaults["connector"]),
                    "fiber_mode": str(old.get("fiber_mode") or defaults["fiber_mode"]),
                }
            )
    attrs["system_ports"] = next_ports


def _normalize_switch_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """交换机角色驱动上下联类型/数量；核心/汇聚按模块化扩展槽与接口板布局。"""
    role = str(attrs.get("switch_role") or "").strip()
    if role not in ("gigabit", "ten_gigabit", "core", "aggregation"):
        dt = str(attrs.get("downlink_type") or "1g")
        role = "ten_gigabit" if dt in ("10g", "25g", "40_100g") else "gigabit"
    attrs["switch_role"] = role
    core = role in ("core", "aggregation")

    if role in ("gigabit", "ten_gigabit"):
        if role == "gigabit":
            attrs["downlink_type"] = "1g"
            attrs["uplink_type"] = "10g"
            media = str(attrs.get("downlink_media") or "copper").lower()
            attrs["downlink_media"] = "optical" if media in ("optical", "fiber") else "copper"
            attrs["uplink_position"] = "right"
            down = _clamp_int(attrs.get("downlink_count"), 48, 1, 128)
            attrs["downlink_count"] = down
            attrs["optical_card_count"] = 1
            attrs["optical_ports_per_card"] = down
            up = _clamp_int(attrs.get("uplink_count"), 8, 0, 8)
            if up > 4 and up % 2 != 0:
                up -= 1
            attrs["uplink_count"] = up
        else:
            attrs["downlink_type"] = "10g"
            ut = str(attrs.get("uplink_type") or "40g").lower()
            attrs["uplink_type"] = "100g" if ut in ("100g", "100ge") else "40g"
            down = _clamp_int(attrs.get("downlink_count"), 48, 1, 128)
            attrs["downlink_count"] = down
            attrs["optical_card_count"] = 1
            attrs["optical_ports_per_card"] = down
            up = _clamp_int(attrs.get("uplink_count"), 6, 0, 8)
            if up > 0 and up % 2 != 0:
                up -= 1
            attrs["uplink_count"] = up
            pos = str(attrs.get("uplink_position") or "right")
            attrs["uplink_position"] = pos if pos in ("middle", "right") else "right"
    else:
        # 核心/汇聚：板卡数由模块化扩展插槽决定，不再用整机高度补齐 line_cards
        expansion = _clamp_int(attrs.get("modular_expansion_slots"), 6, 1, 48)
        height = _clamp_int(attrs.get("chassis_height_u"), 10, 1, 48)
        if expansion > height:
            expansion = height
        filled = _clamp_int(attrs.get("service_board_count"), 4, 0, expansion)
        attrs["modular_expansion_slots"] = expansion
        attrs["service_board_count"] = filled
        attrs["blank_panel_rows"] = _normalize_blank_panel_rows(
            attrs.get("blank_panel_rows"), height, expansion
        )
        attrs["uplink_count"] = _clamp_int(attrs.get("uplink_count"), 0, 0, 256)
        attrs["downlink_count"] = _clamp_int(attrs.get("downlink_count"), 0, 0, 1024)
        raw_cards = attrs.get("line_cards")
        cards: list[dict[str, Any]] = []
        if isinstance(raw_cards, list):
            for i, item in enumerate(raw_cards[:48]):
                if not isinstance(item, dict):
                    continue
                ct = _map_core_card_type(str(item.get("card_type") or "ten_gigabit"))
                try:
                    pc = 0 if ct == "blank" else max(1, min(128, int(item.get("port_count") or 48)))
                except (TypeError, ValueError):
                    pc = 0 if ct == "blank" else 48
                cid = str(item.get("id") or f"card{i + 1}")
                cards.append({"id": cid, "card_type": ct, "port_count": pc})
        if cards:
            attrs["line_cards"] = cards

    attrs["chassis_height_u"] = _clamp_int(attrs.get("chassis_height_u"), 10 if core else 1, 1, 48)
    attrs["fabric_slot_count"] = _clamp_int(attrs.get("fabric_slot_count"), 2 if core else 0, 0, 16)
    attrs["max_power_watt"] = _clamp_int(attrs.get("max_power_watt"), 3000 if core else 150, 0, 100000)
    attrs["chassis_dim_a"] = _clamp_int(attrs.get("chassis_dim_a"), 442, 1, 10000)
    attrs["chassis_dim_b"] = _clamp_int(attrs.get("chassis_dim_b"), 660 if core else 420, 1, 10000)
    attrs["chassis_dim_c"] = _clamp_int(attrs.get("chassis_dim_c"), 175 if core else 44, 1, 10000)
    airflow = str(attrs.get("airflow_type") or "front_to_rear")
    attrs["airflow_type"] = airflow if airflow in ("front_to_rear", "custom") else "front_to_rear"
    if attrs.get("airflow_custom") is None:
        attrs["airflow_custom"] = ""
    board = str(attrs.get("iface_board_type") or "10ge")
    attrs["iface_board_type"] = board if board in ("10ge", "25ge", "40ge", "100ge", "400ge") else "10ge"
    attrs["iface_board_port_count"] = _clamp_int(attrs.get("iface_board_port_count"), 48, 1, 128)
    attrs["console_ports"] = _clamp_int(attrs.get("console_ports"), 1, 0, 8)
    eth_src = attrs.get("eth_mgmt_ports")
    if eth_src is None:
        eth_src = attrs.get("mgmt_ports")
    attrs["eth_mgmt_ports"] = _clamp_int(eth_src, 1, 0, 8)
    attrs["usb_ports"] = _clamp_int(attrs.get("usb_ports"), 1, 0, 8)
    attrs["stack_cluster_ports"] = _clamp_int(attrs.get("stack_cluster_ports"), 2 if core else 0, 0, 16)
    mgmt_src = attrs.get("mgmt_ports")
    if mgmt_src is None:
        mgmt_src = attrs.get("eth_mgmt_ports")
    attrs["mgmt_ports"] = _clamp_int(mgmt_src, 1, 0, 8)

    try:
        attrs["fan_count"] = max(0, min(16, int(attrs.get("fan_count") or 0)))
    except (TypeError, ValueError):
        attrs["fan_count"] = 2
    try:
        attrs["psu_count"] = max(0, min(8, int(attrs.get("psu_count") or 0)))
    except (TypeError, ValueError):
        attrs["psu_count"] = 2

    panel = attrs.get("panel_layout")
    if not isinstance(panel, dict) or "front" not in panel:
        attrs["panel_layout"] = {
            "cols": 38,
            "rows": 16,
            "grid_scale": 4,
            "front": {"cols": 38, "rows": 16, "items": []},
            "rear": {"cols": 38, "rows": 16, "items": []},
        }
    _normalize_system_ports(attrs, core)
    return attrs


def _as_int(v: Any, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _normalize_pcie_slots(raw: Any, max_slots: int, flex_fallback: int) -> list[dict[str, Any]]:
    """灵活 IO 光口按 PCIE 槽定义：0=挡板，2/4=光口。"""
    n = max(0, min(16, int(max_slots or 0)))
    if isinstance(raw, list) and raw:
        slots: list[dict[str, Any]] = []
        for i in range(n):
            src = raw[i] if i < len(raw) and isinstance(raw[i], dict) else {}
            slots.append(
                {
                    "index": i + 1,
                    "flex_ports": _as_int(src.get("flex_ports"), 0, 0, 4),
                }
            )
        return slots
    remain = max(0, min(64, int(flex_fallback or 0)))
    slots = []
    per = 2
    for i in range(n):
        take = 0 if remain <= 0 else min(4, remain, per)
        slots.append({"index": i + 1, "flex_ports": take})
        remain -= take
    if remain > 0 and slots:
        slots[-1]["flex_ports"] = max(0, min(4, int(slots[-1]["flex_ports"]) + remain))
    return slots


def _normalize_server_slots(attrs: dict[str, Any]) -> dict[str, Any]:
    """硬件规格 + 接口计数驱动 server_slots / 稳定端口 ID。"""
    try:
        form_u = int(attrs.get("form_factor_u") or 1)
    except (TypeError, ValueError):
        form_u = 1
    if form_u >= 4:
        form_u = 4
        front_max = 48
    elif form_u >= 2:
        form_u = 2
        front_max = 24
    else:
        form_u = 1
        front_max = 4
    attrs["form_factor_u"] = form_u
    attrs["disk_front_max"] = front_max
    attrs["disk_rear_max"] = 6
    attrs["disk_front_count"] = _as_int(attrs.get("disk_front_count"), min(4, front_max), 0, front_max)
    attrs["disk_rear_count"] = _as_int(attrs.get("disk_rear_count"), 0, 0, 6)
    size = str(attrs.get("disk_front_size") or "3.5")
    attrs["disk_front_size"] = "2.5" if size in ("2.5", "sff") else "3.5"
    rsize = str(attrs.get("disk_rear_size") or "2.5")
    attrs["disk_rear_size"] = "3.5" if rsize in ("3.5", "lff") else "2.5"
    proto = str(attrs.get("disk_front_proto") or "sas_sata").lower()
    attrs["disk_front_proto"] = proto if proto in ("sas", "sata", "nvme", "sas_sata") else "sas_sata"
    rproto = str(attrs.get("disk_rear_proto") or "sas_sata").lower()
    attrs["disk_rear_proto"] = rproto if rproto in ("sas", "sata", "nvme", "sas_sata") else "sas_sata"

    mem_t = str(attrs.get("memory_type") or "ddr4").lower()
    attrs["memory_type"] = mem_t if mem_t in ("ddr4", "ddr5", "other") else "ddr4"
    attrs["cpu_sockets"] = _as_int(attrs.get("cpu_sockets"), 2, 1, 8)
    attrs["cpu_cores_per_socket"] = _as_int(attrs.get("cpu_cores_per_socket"), 16, 1, 128)
    attrs["memory_module_gb"] = _as_int(attrs.get("memory_module_gb"), 16, 1, 1024)
    attrs["memory_modules"] = _as_int(attrs.get("memory_modules"), 8, 1, 64)
    try:
        total = int(attrs.get("memory_gb") or 0)
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        total = int(attrs["memory_module_gb"]) * int(attrs["memory_modules"])
    attrs["memory_gb"] = max(1, total)
    default_pcie = 2 if form_u == 1 else 6 if form_u == 2 else 8
    attrs["pcie_slot_max"] = _as_int(attrs.get("pcie_slot_max"), default_pcie, 0, 16)

    attrs["ssd_internal_count"] = _as_int(attrs.get("ssd_internal_count"), 0, 0, 16)
    ssd_if = str(attrs.get("ssd_internal_iface") or "sata").lower()
    attrs["ssd_internal_iface"] = ssd_if if ssd_if in ("sata", "nvme", "sas", "m.2", "u.2", "other") else "sata"
    attrs["ssd_max_count"] = _as_int(attrs.get("ssd_max_count"), max(2, int(attrs["ssd_internal_count"])), 0, 64)
    ssd_ty = str(attrs.get("ssd_max_type") or "sata").lower()
    attrs["ssd_max_type"] = ssd_ty if ssd_ty in ("sata", "nvme", "sas", "mixed", "other") else "sata"

    red = str(attrs.get("psu_redundancy") or "1+1")
    if red in ("1+n", "1+N"):
        red = "1+n"
    elif red != "other":
        red = "1+1"
    attrs["psu_redundancy"] = red
    attrs["psu_watt"] = _as_int(attrs.get("psu_watt"), 800, 100, 5000)
    attrs["psu_redundant_n"] = _as_int(attrs.get("psu_redundant_n"), 1, 1, 7)
    if attrs.get("psu_count") is None:
        attrs["psu_count"] = 1 + int(attrs["psu_redundant_n"]) if red == "1+n" else 2
    attrs["psu_count"] = _as_int(attrs.get("psu_count"), 2, 0, 8)
    attrs["psu_redundant"] = red != "other" and int(attrs["psu_count"]) >= 2
    attrs["fan_count"] = _as_int(attrs.get("fan_count"), 4 if form_u == 1 else 6 if form_u == 2 else 8, 0, 16)

    os_raw = attrs.get("os_support")
    if isinstance(os_raw, list):
        attrs["os_support"] = [str(x).strip() for x in os_raw if str(x).strip()]
    elif isinstance(os_raw, str) and os_raw.strip():
        attrs["os_support"] = [p.strip() for p in os_raw.replace("，", ",").split(",") if p.strip()]
    else:
        attrs["os_support"] = ["windows_server", "rhel"]
    attrs["os_support_custom"] = str(attrs.get("os_support_custom") or "")

    migrated = attrs.get("lom_1g_count") is not None or attrs.get("flex_io_count") is not None or attrs.get("vga_count") is not None

    raw_server = attrs.get("server_slots")
    server_slots: list[dict[str, Any]] = []
    if isinstance(raw_server, list):
        for item in raw_server:
            if isinstance(item, dict):
                server_slots.append(dict(item))
    if not server_slots:
        raw_slots = attrs.get("slots")
        if isinstance(raw_slots, list):
            for item in raw_slots:
                if not isinstance(item, dict):
                    continue
                stype = str(item.get("type") or "nic_10g")
                pc = max(0, min(16, int(item.get("port_count") or 2)))
                entry = {
                    "index": int(item.get("index") or len(server_slots) + 1),
                    "bmc_count": 0,
                    "ipmi_count": 0,
                    "hdmi_count": 0,
                    "usb_count": 0,
                    "ports_10g": pc if stype == "nic_10g" else 0,
                    "ports_1g": pc if stype == "nic_1g" else 0,
                    "port_start": 1,
                }
                if stype not in ("nic_10g", "nic_1g"):
                    entry["ports_10g"] = 0
                    entry["ports_1g"] = 0
                server_slots.append(entry)

    onboard = next((s for s in server_slots if int(s.get("index") or 0) == 1), server_slots[0] if server_slots else {})
    flex_slot = next((s for s in server_slots if int(s.get("index") or 0) == 2), None)
    if not migrated:
        bmc_legacy = onboard.get("bmc_count")
        ipmi_legacy = onboard.get("ipmi_count")
        if bmc_legacy is None:
            attrs["bmc_ports"] = _as_int(ipmi_legacy, 1, 0, 4)
            attrs["ipmi_iface_count"] = 0
        else:
            attrs["bmc_ports"] = _as_int(bmc_legacy, 1, 0, 4)
            attrs["ipmi_iface_count"] = _as_int(ipmi_legacy, 0, 0, 4)
        attrs["vga_count"] = _as_int(onboard.get("hdmi_count") or onboard.get("vga_count"), 1, 0, 4)
        attrs["usb_count"] = _as_int(onboard.get("usb_count"), 2, 0, 8)
        attrs["lom_1g_count"] = _as_int(onboard.get("ports_1g"), 2, 0, 8)
        flex_n = (flex_slot or {}).get("ports_10g") or onboard.get("ports_10g") or 2
        attrs["flex_io_count"] = _as_int(flex_n, 2, 0, 16)

    attrs["bmc_ports"] = _as_int(attrs.get("bmc_ports"), 1, 0, 4)
    attrs["ipmi_iface_count"] = _as_int(attrs.get("ipmi_iface_count"), 0, 0, 4)
    attrs["vga_count"] = _as_int(attrs.get("vga_count") or attrs.get("hdmi_ports"), 1, 0, 4)
    attrs["usb_count"] = _as_int(attrs.get("usb_count") or attrs.get("usb_ports"), 2, 0, 8)
    attrs["usb_ports"] = attrs["usb_count"]
    attrs["hdmi_ports"] = attrs["vga_count"]
    attrs["lom_1g_count"] = _as_int(attrs.get("lom_1g_count"), 2, 0, 8)
    flex_speed = str(attrs.get("flex_io_speed") or "10ge").lower()
    attrs["flex_io_speed"] = "25ge" if flex_speed in ("25ge", "25g", "25") else "10ge"
    pcie_slots = _normalize_pcie_slots(
        attrs.get("pcie_slots"),
        int(attrs["pcie_slot_max"]),
        _as_int(attrs.get("flex_io_count"), 2, 0, 16),
    )
    attrs["pcie_slots"] = pcie_slots
    attrs["flex_io_count"] = sum(int(s.get("flex_ports") or 0) for s in pcie_slots)

    bmc = int(attrs["bmc_ports"])
    ipmi = int(attrs["ipmi_iface_count"])
    vga = int(attrs["vga_count"])
    usb = int(attrs["usb_count"])
    lom = int(attrs["lom_1g_count"])
    flex = int(attrs["flex_io_count"])
    count = 1 + len(pcie_slots)
    attrs["slot_count"] = count
    flex_type = "25g" if attrs["flex_io_speed"] == "25ge" else "10g"

    def _ports(kind: str, n: int, ptype: str, code_prefix: str) -> list[dict[str, Any]]:
        out = []
        for i in range(n):
            pid = f"{kind}-p{i}"
            code = f"{code_prefix}{i + 1}"
            out.append(
                {
                    "index": len(out) + 1,
                    "port_type": ptype,
                    "local_label": code,
                    "local_info": pid,
                    "peer_label": "",
                    "peer_info": "",
                    "id": pid,
                    "code": code,
                }
            )
        return out

    def _pcie_ports(slot_index: int, n: int, ptype: str) -> list[dict[str, Any]]:
        out = []
        for i in range(n):
            pid = f"pcie{slot_index}-p{i}"
            code = f"S{slot_index}-{i + 1}"
            out.append(
                {
                    "index": len(out) + 1,
                    "port_type": ptype,
                    "local_label": code,
                    "local_info": pid,
                    "peer_label": "",
                    "peer_info": "",
                    "id": pid,
                    "code": code,
                    "slot_index": slot_index,
                }
            )
        return out

    onboard_ifaces = (
        _ports("bmc", bmc, "bmc", "BMC")
        + _ports("ipmi", ipmi, "bmc", "IPMI")
        + _ports("lom", lom, "1g", "LOM")
        + _ports("vga", vga, "other", "VGA")
        + _ports("usb", usb, "other", "USB")
    )
    normalized_server = [
        {
            "index": 1,
            "kind": "onboard",
            "bmc_count": bmc,
            "ipmi_count": ipmi,
            "hdmi_count": vga,
            "usb_count": usb,
            "ports_10g": 0,
            "ports_1g": lom,
            "port_start": 1,
        }
    ]
    design_slots: list[dict[str, Any]] = [
        {
            "index": 1,
            "type": "nic_1g" if lom else "blank",
            "port_count": len(onboard_ifaces),
            "interfaces": onboard_ifaces,
        }
    ]
    if flex > 0:
        normalized_server.append(
            {
                "index": 2,
                "kind": "expansion",
                "bmc_count": 0,
                "ipmi_count": 0,
                "hdmi_count": 0,
                "usb_count": 0,
                "ports_10g": flex,
                "ports_1g": 0,
                "port_start": 1,
            }
        )
    for pcie in pcie_slots:
        n = int(pcie.get("flex_ports") or 0)
        ifaces = _pcie_ports(int(pcie["index"]), n, flex_type)
        design_slots.append(
            {
                "index": len(design_slots) + 1,
                "type": "nic_10g" if n else "blank",
                "port_count": len(ifaces),
                "interfaces": ifaces,
            }
        )

    attrs["server_slots"] = normalized_server
    attrs["slots"] = design_slots
    attrs["server_ports"] = [
        {k: it[k] for k in ("id", "code", "port_type", "local_label")}
        for slot in design_slots
        for it in slot.get("interfaces") or []
    ]

    panel = attrs.get("panel_layout")
    if not isinstance(panel, dict) or "front" not in panel:
        panel = {
            "cols": 38,
            "rows": 16,
            "grid_scale": 4,
            "front": {"cols": 38, "rows": 16, "items": []},
            "rear": {"cols": 38, "rows": 16, "items": []},
        }
    attrs["panel_layout"] = panel
    if attrs.get("panel_style_mode") not in ("custom", "generated"):
        attrs["panel_style_mode"] = "custom" if attrs.get("panel_style_image") else "generated"

    custom = attrs.get("custom_attributes")
    if not isinstance(custom, list):
        attrs["custom_attributes"] = []
    return attrs


def _server_defaults(subtype: str) -> dict[str, Any]:
    form_u = 2 if subtype == "storage" else 1
    front_max = 24 if form_u == 2 else 4
    base = {
        "form_factor_u": form_u,
        "cpu_sockets": 2,
        "cpu_cores_per_socket": 16 if subtype != "hpc" else 32,
        "memory_type": "ddr4",
        "memory_gb": 256 if subtype == "hpc" else 128,
        "memory_modules": 8,
        "memory_module_gb": 16 if subtype != "hpc" else 32,
        "pcie_slot_max": 6 if form_u == 2 else 2,
        "slot_count": 2,
        "psu_count": 2,
        "psu_watt": 800,
        "psu_redundancy": "1+1",
        "psu_redundant": True,
        "psu_redundant_n": 1,
        "fan_count": 4 if form_u == 1 else 6,
        "bmc_ports": 1,
        "ipmi_iface_count": 0,
        "vga_count": 1,
        "usb_count": 2,
        "lom_1g_count": 2,
        "flex_io_count": 2,
        "flex_io_speed": "10ge",
        "disk_front_count": min(4, front_max) if subtype != "storage" else min(8, front_max),
        "disk_rear_count": 2 if form_u >= 2 else 0,
        "disk_front_size": "3.5",
        "disk_rear_size": "2.5",
        "disk_front_proto": "sas_sata",
        "disk_rear_proto": "sas_sata",
        "disk_front_max": front_max,
        "disk_rear_max": 6,
        "ssd_internal_count": 0,
        "ssd_internal_iface": "sata",
        "ssd_max_count": 2,
        "ssd_max_type": "sata",
        "os_support": ["windows_server", "rhel"],
        "os_support_custom": "",
        "panel_style_image": None,
        "panel_style_image_rear": None,
        "panel_style_mode": "generated",
        "panel_layout": {
            "cols": 38,
            "rows": 16,
            "grid_scale": 4,
            "front": {"cols": 38, "rows": 16, "items": []},
            "rear": {"cols": 38, "rows": 16, "items": []},
        },
        "custom_attributes": [],
    }
    return _normalize_server_slots(base)


def _network_defaults(subtype: str) -> dict[str, Any]:
    if subtype == "switch":
        return _normalize_switch_attrs(
            {
                "switch_role": "gigabit",
                "card_slot_count": 2,
                "switch_slots": [
                    {
                        "index": 1,
                        "purpose": "DOWNLINK",
                        "card_type": "gigabit",
                        "port_count": 48,
                        "port_start": 1,
                    },
                    {
                        "index": 2,
                        "purpose": "UPLINK",
                        "card_type": "ten_gigabit",
                        "port_count": 8,
                        "port_start": 0,
                    },
                ],
                "downlink_type": "1g",
                "downlink_count": 48,
                "optical_card_count": 1,
                "optical_ports_per_card": 48,
                "uplink_type": "10g",
                "uplink_count": 8,
                "uplink_position": "right",
                "downlink_media": "copper",
                "mgmt_ports": 1,
                "console_ports": 1,
                "eth_mgmt_ports": 1,
                "usb_ports": 1,
                "stack_cluster_ports": 0,
                "fabric_slot_count": 0,
                "airflow_type": "front_to_rear",
                "airflow_custom": "",
                "chassis_dim_a": 442,
                "chassis_dim_b": 420,
                "chassis_dim_c": 44,
                "max_power_watt": 150,
                "modular_expansion_slots": 2,
                "service_board_count": 0,
                "iface_board_type": "10ge",
                "iface_board_port_count": 48,
                "iface_board_port_custom": False,
                "panel_style_image": None,
                "panel_style_mode": "generated",
                "line_cards": [
                    {"id": "slot1", "card_type": "gigabit", "port_count": 48},
                    {"id": "slot2", "card_type": "ten_gigabit", "port_count": 6},
                ],
                "chassis_height_u": 1,
                "fan_count": 2,
                "psu_count": 2,
                "switching_capacity_gbps": None,
                "stackable": False,
                "panel_layout": {
                    "cols": 38,
                    "rows": 16,
                    "grid_scale": 4,
                    "front": {"cols": 38, "rows": 16, "items": []},
                    "rear": {"cols": 38, "rows": 16, "items": []},
                },
                "custom_attributes": [],
            }
        )
    if subtype == "router":
        return {
            "wan_type": "10g",
            "wan_count": 2,
            "lan_type": "1g",
            "lan_count": 8,
            "routing_protocols": ["OSPF", "BGP"],
        }
    if subtype == "load_balancer":
        return {
            "service_port_type": "10g",
            "service_port_count": 8,
            "mgmt_ports": 1,
            "throughput_gbps": 40,
        }
    # optical_gate
    return {
        "inner_type": "1g",
        "inner_count": 4,
        "outer_type": "1g",
        "outer_count": 4,
        "unidirectional": True,
    }


def _security_defaults(subtype: str) -> dict[str, Any]:
    return {
        "chassis_height_u": 1,
        "form_factor_u": 1,
        "slot_count": 4,
        "security_slots": [
            {
                "index": 1,
                "control_count": 1,
                "ha_count": 2,
                "mgmt_count": 1,
                "usb_count": 2,
                "ports_10g": 4,
                "ports_1g": 2,
            },
            {
                "index": 2,
                "control_count": 0,
                "ha_count": 0,
                "mgmt_count": 0,
                "usb_count": 0,
                "ports_10g": 4,
                "ports_1g": 2,
            },
            {
                "index": 3,
                "control_count": 0,
                "ha_count": 0,
                "mgmt_count": 0,
                "usb_count": 0,
                "ports_10g": 4,
                "ports_1g": 2,
            },
            {
                "index": 4,
                "control_count": 0,
                "ha_count": 0,
                "mgmt_count": 0,
                "usb_count": 0,
                "ports_10g": 4,
                "ports_1g": 2,
            },
        ],
        "data_port_type": "10g" if subtype in ("firewall", "ddos", "ips") else "1g",
        "data_port_count": 16 if subtype != "crypto" else 8,
        "control_ports": 1,
        "ha_ports": 2 if subtype in ("firewall", "vpn", "ddos") else 0,
        "mgmt_ports": 1,
        "usb_ports": 2,
        "fan_count": 2,
        "psu_count": 2,
        "cpu_cores": 8,
        "memory_gb": 32,
        "disk_gb": 480,
        "disk_count": 2,
        "throughput_gbps": None,
        "panel_layout": {
            "cols": 38,
            "rows": 16,
            "grid_scale": 4,
            "front": {"cols": 38, "rows": 16, "items": []},
            "rear": {"cols": 38, "rows": 16, "items": []},
        },
        "custom_attributes": [],
    }


def _software_defaults(subtype: str) -> dict[str, Any]:
    if subtype == "mysql":
        return {
            "version": "8.0",
            "components": ["mysqld", "proxy"],
            "compatible_os": ["CentOS 7+", "RHEL 8+", "Ubuntu 22.04"],
            "license_type": "commercial",
            "license_count": 1,
            "ha_mode": "主从/MGR",
        }
    if subtype == "bigdata":
        return {
            "version": "3.x",
            "components": ["HDFS", "YARN", "Hive", "Spark"],
            "compatible_os": ["CentOS 7+", "RHEL 8+"],
            "license_type": "subscription",
            "license_count": 1,
            "node_roles": ["NameNode", "DataNode", "ResourceManager"],
        }
    return {
        "version": "1.0",
        "components": ["控制台", "计算", "存储", "网络"],
        "compatible_os": ["RHEL 8+", "Ubuntu 22.04"],
        "license_type": "subscription",
        "license_count": 1,
        "hypervisors": ["KVM", "VMware"],
    }


def default_attributes(category: str, subtype: str) -> dict[str, Any]:
    if category == "server":
        return _server_defaults(subtype)
    if category == "network":
        return _network_defaults(subtype)
    if category == "security":
        return _security_defaults(subtype)
    if category == "software":
        return _software_defaults(subtype)
    return {}


def attribute_schema(category: str) -> CategoryAttributeSchema:
    if category == "server":
        fields = [
            AttributeFieldDef(key="form_factor_u", label="机箱高度(U)", type="int", min=1, max=4, required=True),
            AttributeFieldDef(key="cpu_sockets", label="处理器颗数", type="int", min=1, max=8, required=True),
            AttributeFieldDef(key="cpu_cores_per_socket", label="每颗核数", type="int", min=1, max=128),
            AttributeFieldDef(key="memory_type", label="内存类型", type="select", options=MEMORY_TYPE_OPTIONS),
            AttributeFieldDef(key="memory_module_gb", label="单条容量(GB)", type="int", min=1),
            AttributeFieldDef(key="memory_modules", label="内存条数", type="int", min=1, max=64, required=True),
            AttributeFieldDef(key="memory_gb", label="内存总容量(GB)", type="int", min=1, required=True),
            AttributeFieldDef(key="pcie_slot_max", label="PCIE最大插槽", type="int", min=0, max=16),
            AttributeFieldDef(key="disk_front_count", label="前置盘位数", type="int", min=0, max=48),
            AttributeFieldDef(key="disk_front_size", label="前置盘尺寸", type="select", options=DISK_SIZE_OPTIONS),
            AttributeFieldDef(key="disk_front_proto", label="前置盘协议", type="select", options=DISK_PROTO_OPTIONS),
            AttributeFieldDef(key="disk_rear_count", label="后置盘位数", type="int", min=0, max=6),
            AttributeFieldDef(key="disk_rear_size", label="后置盘尺寸", type="select", options=DISK_SIZE_OPTIONS),
            AttributeFieldDef(key="disk_rear_proto", label="后置盘协议", type="select", options=DISK_PROTO_OPTIONS),
            AttributeFieldDef(key="ssd_internal_count", label="内置SSD个数", type="int", min=0, max=16),
            AttributeFieldDef(key="ssd_internal_iface", label="内置SSD接口", type="select", options=SSD_IFACE_OPTIONS),
            AttributeFieldDef(key="ssd_max_count", label="最大SSD个数", type="int", min=0, max=64),
            AttributeFieldDef(key="ssd_max_type", label="SSD类型", type="select", options=SSD_TYPE_OPTIONS),
            AttributeFieldDef(key="psu_watt", label="电源功率(W)", type="int", min=100),
            AttributeFieldDef(key="psu_count", label="电源数量", type="int", min=1, max=8, required=True),
            AttributeFieldDef(key="psu_redundancy", label="电源冗余", type="select", options=PSU_REDUNDANCY_OPTIONS),
            AttributeFieldDef(key="fan_count", label="风扇模组", type="int", min=0, max=16),
            AttributeFieldDef(key="os_support", label="支持的操作系统", type="list"),
            AttributeFieldDef(key="bmc_ports", label="BMC管理口", type="int", min=0, max=4),
            AttributeFieldDef(key="ipmi_iface_count", label="IPMI接口", type="int", min=0, max=4),
            AttributeFieldDef(key="vga_count", label="VGA接口", type="int", min=0, max=4),
            AttributeFieldDef(key="usb_count", label="USB个数", type="int", min=0, max=8),
            AttributeFieldDef(key="flex_io_speed", label="灵活IO速率", type="select", options=FLEX_SPEED_OPTIONS),
            AttributeFieldDef(key="flex_io_count", label="灵活IO光口数", type="int", min=0, max=16),
            AttributeFieldDef(key="lom_1g_count", label="板载LOM电口", type="int", min=0, max=8),
            *SIM_ATTRIBUTE_FIELDS,
        ]
        return CategoryAttributeSchema(
            category=category, fields=fields, default_attributes=_server_defaults("compute")
        )
    if category == "network":
        fields = [
            AttributeFieldDef(
                key="switch_role",
                label="交换机样式",
                type="select",
                options=SWITCH_ROLE_OPTIONS,
                description="千兆/万兆/核心：按角色样式自动分布接口",
            ),
            AttributeFieldDef(key="downlink_type", label="下联接口类型", type="select", options=PORT_SPEED_OPTIONS),
            AttributeFieldDef(key="downlink_count", label="下联接口数量(总计)", type="int", min=0, max=256),
            AttributeFieldDef(
                key="optical_card_count",
                label="板卡数",
                type="int",
                min=1,
                max=16,
                description="千兆/万兆/汇聚：下联口按板卡拆分，总口数=板卡数×每板口数",
            ),
            AttributeFieldDef(
                key="optical_ports_per_card",
                label="每板口数",
                type="int",
                min=1,
                max=128,
            ),
            AttributeFieldDef(key="uplink_type", label="上联接口类型", type="select", options=PORT_SPEED_OPTIONS),
            AttributeFieldDef(key="uplink_count", label="上联接口数量", type="int", min=0, max=64),
            AttributeFieldDef(
                key="uplink_position", label="上联位置", type="select", options=UPLINK_POS_OPTIONS
            ),
            AttributeFieldDef(key="fabric_slot_count", label="交换网板槽位", type="int", min=0, max=16),
            AttributeFieldDef(
                key="airflow_type",
                label="风道类型",
                type="select",
                options=AIRFLOW_OPTIONS,
            ),
            AttributeFieldDef(key="chassis_dim_a", label="尺寸宽(mm)", type="int", min=1),
            AttributeFieldDef(key="chassis_dim_b", label="尺寸深(mm)", type="int", min=1),
            AttributeFieldDef(key="chassis_dim_c", label="尺寸高(mm)", type="int", min=1),
            AttributeFieldDef(key="chassis_height_u", label="整机高度(U)", type="int", min=1, max=48),
            AttributeFieldDef(key="max_power_watt", label="最大供电能力(W)", type="int", min=0),
            AttributeFieldDef(key="console_ports", label="Console口", type="int", min=0, max=8),
            AttributeFieldDef(key="eth_mgmt_ports", label="ETH管理口", type="int", min=0, max=8),
            AttributeFieldDef(key="usb_ports", label="USB接口", type="int", min=0, max=8),
            AttributeFieldDef(key="stack_cluster_ports", label="堆叠/集群接口", type="int", min=0, max=16),
            AttributeFieldDef(key="modular_expansion_slots", label="模块化扩展插槽", type="int", min=1, max=48),
            AttributeFieldDef(key="service_board_count", label="业务接口板数", type="int", min=0, max=16),
            AttributeFieldDef(key="blank_panel_rows", label="空白面板位置", type="list"),
            AttributeFieldDef(
                key="iface_board_type",
                label="接口板",
                type="select",
                options=IFACE_BOARD_OPTIONS,
            ),
            AttributeFieldDef(key="iface_board_port_count", label="接口板接口数", type="int", min=1, max=128),
            AttributeFieldDef(key="wan_type", label="WAN 类型(路由)", type="select", options=PORT_SPEED_OPTIONS),
            AttributeFieldDef(key="wan_count", label="WAN 数量", type="int", min=0),
            AttributeFieldDef(key="lan_type", label="LAN 类型(路由)", type="select", options=PORT_SPEED_OPTIONS),
            AttributeFieldDef(key="lan_count", label="LAN 数量", type="int", min=0),
            AttributeFieldDef(key="service_port_type", label="业务口类型(LB)", type="select", options=PORT_SPEED_OPTIONS),
            AttributeFieldDef(key="service_port_count", label="业务口数量(LB)", type="int", min=0),
            AttributeFieldDef(key="inner_count", label="内网口数(光闸)", type="int", min=0),
            AttributeFieldDef(key="outer_count", label="外网口数(光闸)", type="int", min=0),
            *SIM_ATTRIBUTE_FIELDS,
        ]
        return CategoryAttributeSchema(
            category=category, fields=fields, default_attributes=_network_defaults("switch")
        )
    if category == "security":
        fields = [
            AttributeFieldDef(key="data_port_type", label="业务接口类型", type="select", options=PORT_SPEED_OPTIONS),
            AttributeFieldDef(key="data_port_count", label="业务接口数量", type="int", min=0, max=128),
            AttributeFieldDef(key="control_ports", label="Control 口", type="int", min=0, max=4),
            AttributeFieldDef(key="ha_ports", label="HA 口", type="int", min=0, max=4),
            AttributeFieldDef(key="mgmt_ports", label="MGMT 口", type="int", min=0, max=4),
            AttributeFieldDef(key="cpu_cores", label="CPU 核心数", type="int", min=1),
            AttributeFieldDef(key="memory_gb", label="内存(GB)", type="int", min=1),
            AttributeFieldDef(key="disk_gb", label="单盘容量(GB)", type="int", min=1),
            AttributeFieldDef(key="disk_count", label="磁盘数量", type="int", min=0),
            AttributeFieldDef(key="throughput_gbps", label="吞吐(Gbps)", type="float", min=0),
            *SIM_ATTRIBUTE_FIELDS,
        ]
        return CategoryAttributeSchema(
            category=category, fields=fields, default_attributes=_security_defaults("firewall")
        )
    # software
    fields = [
        AttributeFieldDef(key="version", label="平台/产品版本", type="string", required=True),
        AttributeFieldDef(key="components", label="组件列表", type="list"),
        AttributeFieldDef(key="compatible_os", label="兼容操作系统", type="list"),
        AttributeFieldDef(key="license_type", label="授权类型", type="string", required=True),
        AttributeFieldDef(key="license_count", label="授权数量", type="int", min=1),
        AttributeFieldDef(key="ha_mode", label="高可用模式", type="string"),
        AttributeFieldDef(key="node_roles", label="节点角色(大数据)", type="list"),
        AttributeFieldDef(key="hypervisors", label="虚拟化支持(云)", type="list"),
        *SIM_ATTRIBUTE_FIELDS,
    ]
    return CategoryAttributeSchema(
        category=category, fields=fields, default_attributes=_software_defaults("cloud")
    )


def merge_defaults(category: str, subtype: str, attributes: dict[str, Any] | None) -> dict[str, Any]:
    base = default_attributes(category, subtype)
    # 仿真映射（拓扑实验室）
    base.setdefault("sim_engine", "eve-ng")
    base.setdefault("sim_image", "")
    base.setdefault("sim_icon", "")
    base.setdefault("sim_ram", None)
    base.setdefault("sim_cpu", None)
    if not attributes:
        return deepcopy(base)
    merged = deepcopy(base)
    merged.update(attributes)
    # 后面板硬盘硬上限
    if category == "server":
        rear = int(merged.get("disk_rear_count") or 0)
        merged["disk_rear_count"] = max(0, min(6, rear))
        merged["disk_rear_max"] = 6
        merged = _normalize_server_slots(merged)
    if category == "network" and subtype == "switch":
        merged = _normalize_switch_attrs(merged)
    return merged
