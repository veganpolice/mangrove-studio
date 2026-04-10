"""MCP server for AI-assisted carbon model building.

Exposes Mangrove Studio operations as MCP tools that can be used by
Claude Code, Claude Desktop, or any MCP-compatible AI agent.
"""

import json
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from mangrove_studio.engine.generator import (
    generate_composition_yaml,
    generate_yaml,
    load_component,
    load_component_by_id,
    load_composition,
    collect_dpt_slugs,
    DEFINITIONS_DIR,
    COMPOSITIONS_DIR,
)
from mangrove_studio.engine.runner import run_model
from mangrove_studio.engine.validator import validate_component, validate_composition

mcp = FastMCP(
    "Mangrove Studio",
    instructions=(
        "Mangrove Studio is a carbon modeling tool. Use these tools to build, "
        "validate, and run carbon accounting models. Models are defined as YAML "
        "component definitions (reusable calculation patterns) that are assembled "
        "into compositions (complete models with tree structure)."
    ),
)


@mcp.tool()
def list_components() -> str:
    """List all available component definitions with their IDs and descriptions."""
    components = []
    for path in sorted(DEFINITIONS_DIR.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "component" in data:
            comp = data["component"]
            components.append({
                "id": comp["id"],
                "name": comp["name"],
                "description": comp.get("metadata", {}).get("description", ""),
                "pathway": comp.get("metadata", {}).get("pathway", "any"),
                "stage": comp.get("metadata", {}).get("stage", "any"),
            })
    return yaml.dump(components, default_flow_style=False, allow_unicode=True)


@mcp.tool()
def list_compositions() -> str:
    """List all available model compositions."""
    compositions = []
    for path in sorted(COMPOSITIONS_DIR.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data:
            model = data["model"]
            compositions.append({
                "id": model["id"],
                "name": model["name"],
                "description": model.get("description", ""),
                "components_count": len(model.get("components", [])),
            })
    return yaml.dump(compositions, default_flow_style=False, allow_unicode=True)


@mcp.tool()
def get_component(component_id: str) -> str:
    """Get the full YAML definition of a component by its ID.

    Args:
        component_id: The component ID (e.g., 'activity-emission-factor')
    """
    comp = load_component_by_id(component_id)
    return yaml.dump({"component": comp}, default_flow_style=False, allow_unicode=True, sort_keys=False)


@mcp.tool()
def get_composition(composition_id: str) -> str:
    """Get the full YAML definition of a model composition by its ID.

    Args:
        composition_id: The composition ID (e.g., 'example-biochar-produced')
    """
    for path in COMPOSITIONS_DIR.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data and data["model"]["id"] == composition_id:
            return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    raise ValueError(f"Composition '{composition_id}' not found")


@mcp.tool()
def validate_model(yaml_content: str) -> str:
    """Validate a component or composition YAML string.

    Args:
        yaml_content: The YAML string to validate

    Returns issues found, or 'Valid' if no issues.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        return f"YAML parse error: {e}"

    if "component" in data:
        issues = validate_component(data["component"])
        label = "component"
    elif "model" in data:
        issues = validate_composition(data["model"])
        label = "composition"
    else:
        return "Error: YAML must have 'component' or 'model' top-level key"

    if issues:
        return f"Validation failed ({len(issues)} issues):\n" + "\n".join(f"  - {i}" for i in issues)
    return f"Valid {label}"


@mcp.tool()
def generate_model_yaml(composition_id: str) -> str:
    """Generate the full expanded YAML for a composition (resolving all components).

    Args:
        composition_id: The composition ID to expand
    """
    for path in COMPOSITIONS_DIR.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data and data["model"]["id"] == composition_id:
            return generate_composition_yaml(data["model"])
    raise ValueError(f"Composition '{composition_id}' not found")


@mcp.tool()
def run_composition(composition_id: str, input_data_json: str) -> str:
    """Run a model composition with input data and return calculated outputs.

    Args:
        composition_id: The composition ID to run
        input_data_json: JSON string mapping DPT slugs to values.
            Values can be numbers (scalars) or arrays (per-event data).
            Example: {"mass-input": [10, 20, 30], "ef-electricity": 0.5}
    """
    # Find and generate the composition
    for path in COMPOSITIONS_DIR.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data and data["model"]["id"] == composition_id:
            yaml_str = generate_composition_yaml(data["model"])
            tree = yaml.safe_load(yaml_str)
            break
    else:
        raise ValueError(f"Composition '{composition_id}' not found")

    # Parse input data
    input_data = json.loads(input_data_json)

    # Run
    outputs = run_model(tree, input_data)

    return json.dumps(outputs, indent=2)


@mcp.tool()
def explain_component(component_id: str) -> str:
    """Get a human-readable explanation of a component.

    Args:
        component_id: The component ID
    """
    comp = load_component_by_id(component_id)
    lines = [
        f"# {comp['name']} (v{comp['version']})",
        f"ID: {comp['id']}",
        "",
        f"**Pathway:** {comp.get('metadata', {}).get('pathway', 'any')}",
        f"**Stage:** {comp.get('metadata', {}).get('stage', 'any')}",
        "",
        comp.get("metadata", {}).get("description", ""),
        "",
    ]

    # Methodology
    for m in comp.get("metadata", {}).get("methodology", []):
        lines.append(f"**Methodology [{m['registry']}]:** {m['requirement']}")
    lines.append("")

    # Parameters
    params = comp.get("parameters", [])
    if params:
        lines.append("## Parameters")
        for p in params:
            req = "required" if p.get("required") else f"default: {p.get('default', 'none')}"
            lines.append(f"- `{p['name']}` ({req}): {p['description']}")
        lines.append("")

    # Inputs
    inputs = comp.get("inputs", {})
    for section, label in [
        ("event_data_points", "Event Inputs"),
        ("static_data_points", "Static Inputs"),
        ("upstream_references", "Upstream References"),
    ]:
        entries = inputs.get(section, [])
        if entries:
            lines.append(f"## {label}")
            for e in entries:
                lines.append(f"- `{e['slug_template']}` [{e['unit']}]: {e['description']}")
            lines.append("")

    # Outputs
    outputs = comp.get("outputs", {}).get("calculated_data_points", [])
    if outputs:
        lines.append("## Outputs")
        for o in outputs:
            lines.append(f"- `{o['slug_template']}` [{o['unit']}]: {o['description']}")

    return "\n".join(lines)


@mcp.tool()
def list_required_inputs(composition_id: str) -> str:
    """List all DPT slugs required as inputs for a composition.

    This helps identify what data needs to be provided to run the model.

    Args:
        composition_id: The composition ID
    """
    for path in COMPOSITIONS_DIR.glob("*.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data and "model" in data and data["model"]["id"] == composition_id:
            # Generate the full tree and collect all DPT slugs
            yaml_str = generate_composition_yaml(data["model"])
            tree = yaml.safe_load(yaml_str)

            all_slugs = set()
            for root in tree.get("nexus_nodes_attributes", []):
                all_slugs.update(collect_dpt_slugs(root))

            # Separate calculated (outputs) from inputs
            calculated = {s for s in all_slugs if s.startswith("calculated-")}
            inputs = all_slugs - calculated

            result = {
                "composition_id": composition_id,
                "input_slugs": sorted(inputs),
                "output_slugs": sorted(calculated),
            }
            return yaml.dump(result, default_flow_style=False)

    raise ValueError(f"Composition '{composition_id}' not found")


def serve():
    """Start the MCP server."""
    mcp.run()
