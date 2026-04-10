"""Tests for the MCP server tools (testing the tool functions directly)."""

import json

import yaml

from mangrove_studio.agent.mcp_server import (
    list_components,
    list_compositions,
    get_component,
    get_composition,
    validate_model,
    generate_model_yaml,
    run_composition,
    explain_component,
    list_required_inputs,
)


class TestListTools:
    def test_list_components(self):
        result = yaml.safe_load(list_components())
        assert isinstance(result, list)
        assert len(result) >= 7  # Original 7 + new ones
        ids = [c["id"] for c in result]
        assert "activity-emission-factor" in ids
        assert "carbon-sequestration" in ids

    def test_list_compositions(self):
        result = yaml.safe_load(list_compositions())
        assert isinstance(result, list)
        assert len(result) >= 5
        ids = [c["id"] for c in result]
        assert "example-biochar-produced" in ids
        assert "biochar-carbon-credit" in ids


class TestGetTools:
    def test_get_component(self):
        result = yaml.safe_load(get_component("activity-emission-factor"))
        assert "component" in result
        assert result["component"]["id"] == "activity-emission-factor"

    def test_get_composition(self):
        result = yaml.safe_load(get_composition("alberta-feedstock-sourcing"))
        assert "model" in result
        assert result["model"]["id"] == "alberta-feedstock-sourcing"

    def test_get_missing_component(self):
        try:
            get_component("nonexistent")
            assert False, "Should have raised"
        except ValueError:
            pass


class TestValidateTool:
    def test_validate_valid_component(self):
        yaml_str = get_component("activity-emission-factor")
        result = validate_model(yaml_str)
        assert "Valid" in result

    def test_validate_invalid_yaml(self):
        result = validate_model("not valid yaml {{{")
        assert "error" in result.lower()


class TestGenerateTool:
    def test_generate_composition(self):
        result = generate_model_yaml("alberta-feedstock-sourcing")
        parsed = yaml.safe_load(result)
        assert "mangrove_nodes" in parsed


class TestRunTool:
    def test_run_composition(self):
        input_data = json.dumps({"mass-feedstock-transported": [50, 30, 20]})
        result = json.loads(run_composition("alberta-feedstock-sourcing", input_data))
        assert result["calculated-feedstock-received"] == 100.0


class TestExplainTool:
    def test_explain_component(self):
        result = explain_component("carbon-intensity")
        assert "Carbon Intensity" in result
        assert "emissions_slug" in result


class TestListRequiredInputs:
    def test_list_inputs(self):
        result = yaml.safe_load(list_required_inputs("alberta-feedstock-sourcing"))
        assert "input_slugs" in result
        assert "output_slugs" in result
        assert "mass-feedstock-transported" in result["input_slugs"]
        assert "calculated-feedstock-received" in result["output_slugs"]
