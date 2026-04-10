"""Tests for JSON Schema validation of components and compositions."""

from pathlib import Path

import yaml

from mangrove_studio.engine.validator import (
    validate_component_schema,
    validate_composition_schema,
)


COMPONENTS_DIR = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "components"
COMPOSITIONS_DIR = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"


class TestComponentSchemaValidation:
    def test_all_shipped_components_pass_schema(self):
        """Every shipped component should pass JSON Schema validation."""
        for path in COMPONENTS_DIR.glob("*.yaml"):
            with open(path) as f:
                data = yaml.safe_load(f)
            if data and "component" in data:
                issues = validate_component_schema(data)
                assert issues == [], f"{path.name}: {issues}"

    def test_invalid_component_fails(self):
        data = {"component": {"id": "123-bad"}}
        issues = validate_component_schema(data)
        assert len(issues) > 0

    def test_missing_component_key_fails(self):
        data = {"not_a_component": {}}
        issues = validate_component_schema(data)
        assert len(issues) > 0


class TestCompositionSchemaValidation:
    def test_all_shipped_compositions_pass_schema(self):
        """Every shipped composition should pass JSON Schema validation."""
        for path in COMPOSITIONS_DIR.glob("*.yaml"):
            with open(path) as f:
                data = yaml.safe_load(f)
            if data and "model" in data:
                issues = validate_composition_schema(data)
                assert issues == [], f"{path.name}: {issues}"

    def test_invalid_composition_fails(self):
        data = {"model": {"id": "bad"}}
        issues = validate_composition_schema(data)
        assert len(issues) > 0
