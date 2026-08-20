from backend.app.schemas.wiring_rule_config import normalize_wiring_config


def test_rule_engine_extension_fields_are_preserved() -> None:
    config = normalize_wiring_config({
        "connection_type": "ACCESS_ENDPOINT",
        "rule_category": "GIG_TO_ENDPOINT",
        "scenario_template": "GIG_TO_SERVER",
        "source_device_types": ["ACCESS_SWITCH_1G"],
        "target_device_types": ["SERVER", "SECURITY_DEVICE"],
        "max_source_devices": 2,
        "source_port_limit_per_device": 40,
        "media": "COPPER",
    })

    assert config["rule_category"] == "GIG_TO_ENDPOINT"
    assert config["scenario_template"] == "GIG_TO_SERVER"
    assert config["source_device_types"] == ["ACCESS_SWITCH_1G"]
    assert config["target_device_types"] == ["SERVER", "SECURITY_DEVICE"]
    assert config["max_source_devices"] == 2
    assert config["source_port_limit_per_device"] == 40


def test_new_optical_media_values_are_accepted() -> None:
    config = normalize_wiring_config({
        "connection_type": "ACCESS_ENDPOINT",
        "rule_category": "TEN_GIG_TO_ENDPOINT",
        "source_device_types": ["ACCESS_SWITCH_10G"],
        "media": "LC_LC_OM34",
    })
    assert config["media"] == "LC_LC_OM34"
