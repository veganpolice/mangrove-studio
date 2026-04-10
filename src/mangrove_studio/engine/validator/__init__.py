"""Model and component validation — structural checks + JSON Schema validation."""

import json
import re
from pathlib import Path

import jsonschema

from mangrove_studio.engine.generator.generate import (
    load_component_by_id,
    resolve_parameters,
)


SCHEMA_DIR = Path(__file__).parent.parent / "schema"


def _load_schema(name: str) -> dict:
    """Load a JSON Schema from the schema directory."""
    path = SCHEMA_DIR / name
    with open(path) as f:
        return json.load(f)


def validate_component_schema(data: dict) -> list[str]:
    """Validate a component definition against the JSON Schema.

    Args:
        data: The full YAML dict (with 'component' top-level key)

    Returns:
        List of validation errors (empty if valid)
    """
    schema = _load_schema("component-definition.schema.json")
    issues = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        issues.append(f"Schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
    except jsonschema.SchemaError as e:
        issues.append(f"Schema error: {e.message}")
    return issues


def validate_composition_schema(data: dict) -> list[str]:
    """Validate a composition definition against the JSON Schema.

    Args:
        data: The full YAML dict (with 'model' top-level key)

    Returns:
        List of validation errors (empty if valid)
    """
    schema = _load_schema("model-composition.schema.json")
    issues = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        issues.append(f"Schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
    except jsonschema.SchemaError as e:
        issues.append(f"Schema error: {e.message}")
    return issues


def validate_component(component: dict) -> list[str]:
    """Basic validation of a component definition. Returns list of issues."""
    issues = []

    for field in ["id", "name", "version", "metadata", "inputs", "outputs", "parameters", "node_tree"]:
        if field not in component:
            issues.append(f"Missing required field: {field}")

    outputs = component.get("outputs", {}).get("calculated_data_points", [])
    if not outputs:
        issues.append("Component must have at least one calculated output")

    tree = component.get("node_tree", {})
    nodes = tree.get("mangrove_nodes", [])
    if not nodes:
        issues.append("node_tree must have at least one root node")

    param_names = {p["name"] for p in component.get("parameters", [])}
    all_slugs = []
    for section in ["event_data_points", "static_data_points", "upstream_references"]:
        for entry in component.get("inputs", {}).get(section, []):
            all_slugs.append(entry.get("slug_template", ""))
    for entry in outputs:
        all_slugs.append(entry.get("slug_template", ""))

    for slug in all_slugs:
        for match in re.finditer(r"\{(\w+)\}", slug):
            if match.group(1) not in param_names:
                issues.append(f"Slug template references undefined parameter '{match.group(1)}': {slug}")

    return issues


def validate_composition(composition: dict) -> list[str]:
    """Validate a model composition. Returns list of issues."""
    issues = []

    instance_ids = set()
    for i, instance in enumerate(composition.get("components", [])):
        cid = instance.get("component_id", "")
        iid = instance.get("instance_id", "")

        if not iid:
            issues.append(f"Component instance {i} ({cid}): missing instance_id")
        elif iid in instance_ids:
            issues.append(f"Duplicate instance_id: '{iid}'")
        instance_ids.add(iid)

        try:
            component = load_component_by_id(cid)
        except ValueError as e:
            issues.append(f"Component instance '{iid}': {e}")
            continue

        try:
            resolve_parameters(component, instance.get("params", {}))
        except ValueError as e:
            issues.append(f"Component '{iid}': {e}")

    def _check_tree_refs(entries, path="tree"):
        for j, entry in enumerate(entries):
            loc = f"{path}[{j}]"
            if "component" in entry:
                ref = entry["component"]
                if ref not in instance_ids:
                    issues.append(f"{loc}: references unknown instance_id '{ref}'")
            if "children" in entry:
                _check_tree_refs(entry["children"], f"{loc}.children")
            if "component" not in entry and "node" not in entry:
                issues.append(f"{loc}: must have 'component' or 'node'")

    _check_tree_refs(composition.get("tree", []))

    return issues
