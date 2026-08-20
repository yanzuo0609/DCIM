from io import BytesIO

from openpyxl import load_workbook

from app.domains.network_model_taxonomy import TAXONOMY, default_attributes, merge_defaults
from app.services.network_interface_export import NetworkInterfaceExportService


def test_security_taxonomy_contains_audit_and_isolation_models() -> None:
    security = next(item for item in TAXONOMY if item.value == "security")
    values = {item.value for item in security.subtypes}
    assert {"firewall", "ips", "ids", "vpn", "optical_gate", "host_audit", "database_audit"} <= values


def test_interface_template_keeps_full_import_schema_and_styling() -> None:
    service = NetworkInterfaceExportService.__new__(NetworkInterfaceExportService)
    sheet = load_workbook(BytesIO(service.template_excel())).active
    assert [cell.value for cell in sheet[1]] == service.IMPORT_HEADERS
    assert service.EXPORT_HEADERS == [
        "本端设备", "设备名称", "设备位置", "U位", "本端接口",
        "对端设备", "设备名称", "对端位置", "U位", "对端接口",
        "接口类型", "线缆类型", "本端标签", "对端标签",
    ]
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:AD2"

def test_server_pcie_cards_preserve_card_type_media_and_speed() -> None:
    attrs = merge_defaults("server", "compute", {
        "form_factor_u": 2,
        "pcie_slot_max": 3,
        "pcie_slots": [
            {"index": 1, "card_type": "raid", "raid_level": "raid10", "port_count": 0, "orientation": "vertical", "placement": "bottom"},
            {"index": 2, "card_type": "nic_copper", "port_count": 4, "speed": "10ge"},
            {"index": 3, "card_type": "nic_optical", "port_count": 2, "speed": "100ge"},
        ],
    })
    assert attrs["pcie_slots"][0]["card_type"] == "raid"
    assert attrs["pcie_slots"][0]["raid_level"] == "raid10"
    assert attrs["pcie_slots"][0]["orientation"] == "vertical"
    assert attrs["pcie_slots"][0]["placement"] == "bottom"
    assert attrs["pcie_slots"][1]["port_count"] == 4
    assert attrs["pcie_slots"][2]["speed"] == "100ge"
    assert attrs["slots"][1]["type"] == "raid"
    assert attrs["slots"][3]["interfaces"][0]["port_type"] == "40_100g"


def test_security_defaults_are_type_specific() -> None:
    firewall = default_attributes("security", "firewall")
    database_audit = default_attributes("security", "database_audit")
    optical_gate = default_attributes("security", "optical_gate")
    ids = default_attributes("security", "ids")
    ddos = default_attributes("security", "ddos")
    assert firewall["concurrent_sessions_10k"] == 400
    assert database_audit["database_instances"] == 500
    assert database_audit["disk_count"] > firewall["disk_count"]
    assert optical_gate["slot_count"] == 2
    assert optical_gate["deployment_mode"] == "dual-network/isolation"
    assert ids["disk_count"] == 8
    assert ids["memory_gb"] == 192
    assert ddos["throughput_gbps"] == 400
    assert ddos["cpu_cores"] == 48
    assert ddos["security_profile_type_applied"] == "ddos"
    assert ddos["security_profile_version"] == 3

def test_network_taxonomy_exposes_four_switch_subtypes() -> None:
    network = next(item for item in TAXONOMY if item.value == "network")
    assert [(item.value, item.label) for item in network.subtypes] == [
        ("gigabit", "千兆交换机"),
        ("ten_gigabit", "万兆交换机"),
        ("aggregation", "汇聚交换机"),
        ("core", "核心交换机"),
    ]
    assert default_attributes("network", "gigabit")["switch_role"] == "gigabit"
    assert default_attributes("network", "ten_gigabit")["switch_role"] == "ten_gigabit"
    assert default_attributes("network", "aggregation")["switch_role"] == "aggregation"
    assert default_attributes("network", "core")["switch_role"] == "core"


def test_security_subtype_overrides_stale_firewall_attributes() -> None:
    stale = {
        "security_device_type": "firewall",
        "security_profile_type_applied": "firewall",
        "security_profile_version": 2,
        "cpu_cores": 24,
        "memory_gb": 128,
        "throughput_gbps": 40,
        "concurrent_sessions_10k": 400,
    }
    ddos = merge_defaults("security", "ddos", stale)
    assert ddos["security_device_type"] == "ddos"
    assert ddos["security_profile_type_applied"] == "ddos"
    assert ddos["security_profile_version"] == 3
    assert ddos["cpu_cores"] == 48
    assert ddos["memory_gb"] == 256
    assert ddos["throughput_gbps"] == 400
    assert ddos["cleaning_gbps"] == 400
    assert "concurrent_sessions_10k" not in ddos

    unversioned_vpn = merge_defaults("security", "vpn", {
        "cpu_cores": 8,
        "memory_gb": 32,
        "disk_count": 2,
        "disk_gb": 480,
    })
    assert unversioned_vpn["security_device_type"] == "vpn"
    assert unversioned_vpn["security_profile_version"] == 3
    assert unversioned_vpn["cpu_cores"] == 20
    assert unversioned_vpn["memory_gb"] == 64
    assert unversioned_vpn["throughput_gbps"] == 20
