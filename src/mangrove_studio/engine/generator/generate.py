"""
YAML Template Generator for Mangrove Component Definitions.

Supports two modes:
1. Single component: component definition + params -> YAML subtree
2. Model composition: composition file -> assembled nested model YAML from components
"""

import copy
import re
from pathlib import Path

import yaml

DEFINITIONS_DIR = Path(__file__).parent.parent / "components"
COMPOSITIONS_DIR = Path(__file__).parent.parent / "compositions"


def load_component(path: str) -> dict:
    """Load a component definition from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["component"]


def load_component_by_id(component_id: str) -> dict:
    """Load a component definition by its ID from the definitions directory."""
    for path in DEFINITIONS_DIR.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "component" in data and data["component"]["id"] == component_id:
            return data["component"]
    raise ValueError(f"Component '{component_id}' not found in {DEFINITIONS_DIR}")


def load_composition(path: str) -> dict:
    """Load a model composition from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["model"]


def resolve_parameters(component: dict, param_values: dict) -> dict:
    """Merge provided parameter values with defaults."""
    resolved = {}
    for param in component.get("parameters", []):
        name = param["name"]
        if name in param_values:
            resolved[name] = param_values[name]
        elif "default" in param:
            resolved[name] = param["default"]
        elif param.get("required", False):
            raise ValueError(f"Required parameter '{name}' not provided")
    return resolved


def substitute_placeholders(value: str, params: dict) -> str:
    """Replace {param} placeholders in a string with resolved values."""
    if not isinstance(value, str):
        return value

    def replacer(match):
        key = match.group(1)
        if key not in params:
            raise ValueError(f"Unknown parameter '{key}' in template: {value}")
        return str(params[key])

    return re.sub(r"\{(\w+)\}", replacer, value)


def process_node(node: dict, params: dict) -> dict:
    """Recursively process a node tree, substituting parameter placeholders."""
    result = {}
    for key, value in node.items():
        if key == "nexus_nodes_attributes":
            result[key] = [process_node(child, params) for child in value]
        elif isinstance(value, str):
            result[key] = substitute_placeholders(value, params)
        else:
            result[key] = value
    return result


def generate_component_yaml(component: dict, param_values: dict) -> dict:
    """Generate processed node tree dict from a component definition."""
    params = resolve_parameters(component, param_values)
    node_tree = copy.deepcopy(component["node_tree"])
    return {
        "nexus_nodes_attributes": [
            process_node(node, params)
            for node in node_tree["nexus_nodes_attributes"]
        ]
    }


def generate_yaml(component: dict, param_values: dict) -> str:
    """Generate valid Mangrove model YAML string from a component definition."""
    processed = generate_component_yaml(component, param_values)
    return yaml.dump(
        processed,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def _build_instance_lookup(composition: dict) -> dict:
    """Build a lookup from instance_id to (component_def, params)."""
    lookup = {}
    for instance in composition["components"]:
        iid = instance["instance_id"]
        component = load_component_by_id(instance["component_id"])
        lookup[iid] = (component, instance["params"])
    return lookup


def _resolve_tree_entry(entry: dict, instances: dict) -> list[dict]:
    """Resolve a single tree entry into nexus node(s)."""
    if "component" in entry:
        iid = entry["component"]
        if iid not in instances:
            raise ValueError(f"Tree references unknown instance_id '{iid}'")
        component, params = instances[iid]
        result = generate_component_yaml(component, params)
        nodes = result["nexus_nodes_attributes"]

        if "children" in entry:
            extra_children = []
            for child_entry in entry["children"]:
                extra_children.extend(_resolve_tree_entry(child_entry, instances))
            for node in nodes:
                existing = node.get("nexus_nodes_attributes", [])
                node["nexus_nodes_attributes"] = existing + extra_children

        return nodes

    if "node" in entry:
        node = dict(entry["node"])

        if "children" in entry:
            child_nodes = []
            for child_entry in entry["children"]:
                child_nodes.extend(_resolve_tree_entry(child_entry, instances))
            node["nexus_nodes_attributes"] = child_nodes

        return [node]

    raise ValueError(f"Tree entry must have 'component' or 'node': {entry}")


def generate_composition_yaml(composition: dict) -> str:
    """Generate nested model YAML from a tree-structured composition."""
    instances = _build_instance_lookup(composition)

    root_nodes = []
    for entry in composition["tree"]:
        root_nodes.extend(_resolve_tree_entry(entry, instances))

    output = {"nexus_nodes_attributes": root_nodes}
    return yaml.dump(
        output,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )


def collect_dpt_slugs(node: dict) -> set[str]:
    """Recursively collect all data_point_type slugs from a node tree."""
    slugs = set()
    if "data_point_type" in node:
        slugs.add(node["data_point_type"])
    for child in node.get("nexus_nodes_attributes", []):
        slugs.update(collect_dpt_slugs(child))
    return slugs
