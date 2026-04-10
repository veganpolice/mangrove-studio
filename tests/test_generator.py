"""Tests for the YAML generator — ported from spike test_roundtrip.py."""

import pytest

from mangrove_studio.engine.generator import (
    generate_composition_yaml,
    generate_yaml,
    load_component_by_id,
    resolve_parameters,
)
from mangrove_studio.engine.validator import validate_component, validate_composition


def test_load_component():
    comp = load_component_by_id("activity-emission-factor")
    assert comp["id"] == "activity-emission-factor"
    assert "node_tree" in comp


def test_resolve_parameters_with_defaults():
    comp = load_component_by_id("activity-emission-factor")
    params = resolve_parameters(comp, {
        "activity_name": "Test Activity",
        "activity_slug": "test-activity",
        "activity_unit": "kWh",
        "ef_slug": "test-ef",
        "ef_unit": "kgCO2e/kWh",
        "output_prefix": "test",
    })
    assert "activity_slug" in params
    assert params["should_aggregate"] is True  # default value


def test_validate_all_components():
    """All shipped component definitions must pass validation."""
    from pathlib import Path
    import yaml

    components_dir = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "components"
    for path in components_dir.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "component" in data:
            issues = validate_component(data["component"])
            assert issues == [], f"{path.name}: {issues}"


def test_validate_all_compositions():
    """All shipped compositions must pass validation."""
    from pathlib import Path
    import yaml

    compositions_dir = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"
    for path in compositions_dir.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data:
            issues = validate_composition(data["model"])
            assert issues == [], f"{path.name}: {issues}"


def test_generate_composition():
    """Compositions should generate valid YAML."""
    from pathlib import Path
    import yaml

    compositions_dir = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"
    for path in compositions_dir.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data:
            result = generate_composition_yaml(data["model"])
            assert "mangrove_nodes" in result
            parsed = yaml.safe_load(result)
            assert "mangrove_nodes" in parsed
