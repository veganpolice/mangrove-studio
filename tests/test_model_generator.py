"""Tests for the AI model generator (non-API parts)."""

import yaml

from mangrove_studio.agent.model_generator import (
    SYSTEM_PROMPT,
    _extract_yaml,
    validate_generated_yaml,
)


class TestExtractYaml:
    def test_extract_from_code_fence(self):
        text = "Here's the YAML:\n```yaml\ncomponent:\n  id: test\n```\nThat's it."
        assert _extract_yaml(text) == "component:\n  id: test"

    def test_extract_from_plain_fence(self):
        text = "```\nmodel:\n  id: test\n```"
        assert _extract_yaml(text) == "model:\n  id: test"

    def test_extract_plain_text(self):
        text = "component:\n  id: test"
        assert _extract_yaml(text) == "component:\n  id: test"


class TestValidateGeneratedYaml:
    def test_valid_component(self):
        yaml_str = yaml.dump({
            "component": {
                "id": "test-component",
                "name": "Test Component",
                "version": "1.0",
                "metadata": {
                    "pathway": "any",
                    "stage": "any",
                    "description": "Test",
                },
                "inputs": {
                    "event_data_points": [
                        {"slug_template": "test-input", "unit": "kg", "description": "Test input"}
                    ],
                },
                "outputs": {
                    "calculated_data_points": [
                        {"slug_template": "calculated-test", "unit": "tCO₂e", "description": "Test output"}
                    ],
                },
                "parameters": [],
                "node_tree": {
                    "nexus_nodes_attributes": [
                        {"name": "Test", "data_point_type": "test-input", "output_unit": "kg"}
                    ],
                },
            }
        })
        issues = validate_generated_yaml(yaml_str)
        assert issues == []

    def test_invalid_yaml(self):
        issues = validate_generated_yaml("not: valid: yaml: {{}")
        assert len(issues) > 0

    def test_missing_component(self):
        issues = validate_generated_yaml("something:\n  id: test")
        assert any("component" in i or "model" in i for i in issues)

    def test_component_missing_fields(self):
        issues = validate_generated_yaml("component:\n  id: test")
        assert len(issues) > 0


class TestSystemPrompt:
    def test_prompt_contains_key_patterns(self):
        assert "activity-emission-factor" in SYSTEM_PROMPT
        assert "carbon-sequestration" in SYSTEM_PROMPT
        assert "net-carbon-removal" in SYSTEM_PROMPT
        assert "permanence-factor" in SYSTEM_PROMPT
        assert "nexus_nodes_attributes" in SYSTEM_PROMPT

    def test_prompt_contains_rules(self):
        assert "calculated-" in SYSTEM_PROMPT
        assert "tCO₂e" in SYSTEM_PROMPT
        assert "should_aggregate" in SYSTEM_PROMPT
