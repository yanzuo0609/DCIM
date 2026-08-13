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


def _normalize_switch_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """交换机角色驱动上下联类型/数量，核心机按板卡口数布局。"""
    role = str(attrs.get("switch_role") or "").strip()
    if role not in ("gigabit", "ten_gigabit", "core", "aggregation"):
        dt = str(attrs.get("downlink_type") or "1g")
        role = "ten_gigabit" if dt in ("10g", "25g", "40_100g") else "gigabit"
    attrs["switch_role"] = role

    if role in ("gigabit", "ten_gigabit", "aggregation"):
        if role == "gigabit":
            attrs["downlink_type"] = "1g"
            attrs["uplink_type"] = "10g"
        else:
            attrs["downlink_type"] = "10g"
            attrs["uplink_type"] = "40_100g"
        try:
            cards = max(1, min(16, int(attrs.get("optical_card_count") or 1)))
        except (TypeError, ValueError):
            cards = 1
        try:
            ppc = int(attrs.get("optical_ports_per_card") or 0)
        except (TypeError, ValueError):
            ppc = 0
        if ppc <= 0:
            # 兼容旧数据：仅有总口数时，视为 1 板 × N 口
            try:
                total = max(1, min(256, int(attrs.get("downlink_count") or 48)))
            except (TypeError, ValueError):
                total = 48
            ppc = max(1, min(128, total // max(1, cards)))
        else:
            ppc = max(1, min(128, ppc))
        attrs["optical_card_count"] = cards
        attrs["optical_ports_per_card"] = ppc
        attrs["downlink_count"] = max(1, min(256, cards * ppc))
        try:
            up = int(attrs.get("uplink_count") or 0)
        except (TypeError, ValueError):
            up = 4
        if role == "gigabit":
            if up > 4 and up % 2 != 0:
                up -= 1
        elif up % 2 != 0:
            up -= 1
        attrs["uplink_count"] = max(0, min(8, up))
        pos = str(attrs.get("uplink_position") or "right")
        attrs["uplink_position"] = pos if pos in ("middle", "right") else "right"
    else:
        # core：板卡数由机箱高度(U)决定，上下联字段不参与布局
        attrs["downlink_count"] = 0
        attrs["uplink_count"] = 0
        try:
            height = int(attrs.get("chassis_height_u") or 1)
        except (TypeError, ValueError):
            height = 1
        height = max(1, min(16, height))
        attrs["chassis_height_u"] = height
        raw_cards = attrs.get("line_cards")
        cards: list[dict[str, Any]] = []
        if isinstance(raw_cards, list):
            for i, item in enumerate(raw_cards):
                if not isinstance(item, dict):
                    continue
                ct = str(item.get("card_type") or "ten_gigabit")
                if ct not in ("gigabit", "ten_gigabit", "100g", "blank"):
                    ct = "ten_gigabit"
                try:
                    pc = 0 if ct == "blank" else max(1, min(128, int(item.get("port_count") or 48)))
                except (TypeError, ValueError):
                    pc = 0 if ct == "blank" else 48
                cid = str(item.get("id") or f"card{i + 1}")
                cards.append({"id": cid, "card_type": ct, "port_count": pc})
        while len(cards) < height:
            idx = len(cards) + 1
            cards.append({"id": f"card{idx}", "card_type": "ten_gigabit", "port_count": 48})
        attrs["line_cards"] = cards[:height]

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
    return attrs


def _normalize_server_slots(attrs: dict[str, Any]) -> dict[str, Any]:
    """slot_count 驱动 server_slots / slots[]；磁盘槽位按高度封顶。"""
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
    try:
        attrs["disk_front_count"] = max(0, min(front_max, int(attrs.get("disk_front_count") or 0)))
    except (TypeError, ValueError):
        attrs["disk_front_count"] = min(4, front_max)
    try:
        attrs["disk_rear_count"] = max(0, min(6, int(attrs.get("disk_rear_count") or 0)))
    except (TypeError, ValueError):
        attrs["disk_rear_count"] = 0

    raw_server = attrs.get("server_slots")
    server_slots: list[dict[str, Any]] = []
    if isinstance(raw_server, list):
        for item in raw_server:
            if isinstance(item, dict):
                server_slots.append(dict(item))

    # 若无 server_slots，从旧 slots 迁移
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

    count = attrs.get("slot_count")
    if count is None:
        count = len(server_slots) if server_slots else 3
    count = max(1, min(16, int(count or 3)))
    attrs["slot_count"] = count

    while len(server_slots) < count:
        idx = len(server_slots) + 1
        server_slots.append(
            {
                "index": idx,
                "ipmi_count": 1 if idx == 1 else 0,
                "hdmi_count": 1 if idx == 1 else 0,
                "usb_count": 2 if idx == 1 else 0,
                "ports_10g": 2,
                "ports_1g": 2,
                "port_start": 1,
            }
        )
    server_slots = server_slots[:count]
    normalized_server: list[dict[str, Any]] = []
    design_slots: list[dict[str, Any]] = []
    for i, slot in enumerate(server_slots):
        entry = {
            "index": i + 1,
            "ipmi_count": max(0, min(4, int(slot.get("ipmi_count") or 0))),
            "hdmi_count": max(0, min(4, int(slot.get("hdmi_count") or 0))),
            "usb_count": max(0, min(8, int(slot.get("usb_count") or 0))),
            "ports_10g": max(0, min(16, int(slot.get("ports_10g") or 0))),
            "ports_1g": max(0, min(16, int(slot.get("ports_1g") or 0))),
            "port_start": 1,
        }
        normalized_server.append(entry)
        n10 = int(entry["ports_10g"])
        n1 = int(entry["ports_1g"])
        if n10 <= 0 and n1 <= 0:
            design_slots.append({"index": i + 1, "type": "blank", "port_count": 0, "interfaces": []})
        elif n10 > 0:
            design_slots.append({"index": i + 1, "type": "nic_10g", "port_count": n10})
        else:
            design_slots.append({"index": i + 1, "type": "nic_1g", "port_count": max(1, n1)})

    attrs["server_slots"] = normalized_server
    attrs["slots"] = design_slots

    try:
        attrs["fan_count"] = max(0, min(16, int(attrs.get("fan_count") or 0)))
    except (TypeError, ValueError):
        attrs["fan_count"] = 4
    try:
        attrs["psu_count"] = max(0, min(8, int(attrs.get("psu_count") or 0)))
    except (TypeError, ValueError):
        attrs["psu_count"] = 2

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
        "memory_gb": 256 if subtype == "hpc" else 128,
        "memory_modules": 8,
        "memory_module_gb": 16 if subtype != "hpc" else 32,
        "slot_count": 3,
        "server_slots": [
            {
                "index": 1,
                "ipmi_count": 1,
                "hdmi_count": 1,
                "usb_count": 2,
                "ports_10g": 2,
                "ports_1g": 2,
                "port_start": 1,
            },
            {
                "index": 2,
                "ipmi_count": 0,
                "hdmi_count": 0,
                "usb_count": 0,
                "ports_10g": 2,
                "ports_1g": 2,
                "port_start": 1,
            },
            {
                "index": 3,
                "ipmi_count": 0,
                "hdmi_count": 0,
                "usb_count": 0,
                "ports_10g": 2,
                "ports_1g": 2,
                "port_start": 1,
            },
        ],
        "slots": [
            {"index": 1, "type": "nic_10g", "port_count": 2},
            {"index": 2, "type": "nic_10g", "port_count": 2},
            {"index": 3, "type": "nic_10g", "port_count": 2},
        ],
        "psu_count": 2,
        "psu_watt": 800,
        "psu_redundant": True,
        "fan_count": 4 if form_u == 1 else 6,
        "bmc_ports": 1,
        "usb_ports": 2,
        "disk_front_count": min(4, front_max) if subtype != "storage" else min(8, front_max),
        "disk_rear_count": 2,
        "disk_front_max": front_max,
        "disk_rear_max": 6,
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
                        "port_count": 6,
                        "port_start": 49,
                    },
                ],
                "downlink_type": "1g",
                "downlink_count": 48,
                "optical_card_count": 1,
                "optical_ports_per_card": 48,
                "uplink_type": "10g",
                "uplink_count": 6,
                "uplink_position": "right",
                "mgmt_ports": 1,
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
            AttributeFieldDef(key="cpu_sockets", label="CPU 路数", type="int", min=1, max=8, required=True),
            AttributeFieldDef(key="cpu_cores_per_socket", label="单路核心数", type="int", min=1, max=128),
            AttributeFieldDef(key="memory_gb", label="内存总容量(GB)", type="int", min=1, required=True),
            AttributeFieldDef(key="memory_modules", label="内存条数", type="int", min=1, max=64, required=True),
            AttributeFieldDef(key="memory_module_gb", label="单条容量(GB)", type="int", min=1),
            AttributeFieldDef(
                key="slot_count",
                label="扩展 Slot 数量",
                type="int",
                min=0,
                max=16,
                required=True,
                description="每个 Slot 可单独选择千兆/万兆/RAID卡/磁盘插槽",
            ),
            AttributeFieldDef(key="psu_count", label="电源数量", type="int", min=1, max=8, required=True),
            AttributeFieldDef(key="psu_watt", label="单电源功率(W)", type="int", min=100),
            AttributeFieldDef(key="psu_redundant", label="电源冗余", type="bool"),
            AttributeFieldDef(key="fan_count", label="风扇个数", type="int", min=0, max=16),
            AttributeFieldDef(key="bmc_ports", label="IPMI/BMC 口数", type="int", min=0, max=4),
            AttributeFieldDef(key="usb_ports", label="USB 口数", type="int", min=0, max=8),
            AttributeFieldDef(key="disk_front_count", label="前面板硬盘槽", type="int", min=0, max=48),
            AttributeFieldDef(
                key="disk_rear_count",
                label="后面板硬盘槽",
                type="int",
                min=0,
                max=4,
                description="后面板最多 4 块硬盘插槽",
            ),
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
            AttributeFieldDef(key="fan_count", label="风扇个数", type="int", min=0, max=16),
            AttributeFieldDef(key="psu_count", label="电源数量", type="int", min=0, max=8),
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
