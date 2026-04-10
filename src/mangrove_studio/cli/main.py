"""Mangrove Studio CLI."""

import json
import sys
from pathlib import Path

import click
import yaml

from mangrove_studio.engine.generator import (
    generate_composition_yaml,
    generate_yaml,
    load_component,
    load_composition,
)
from mangrove_studio.engine.runner import run_model
from mangrove_studio.engine.validator import validate_component, validate_composition


def _detect_type(data: dict) -> str:
    """Detect whether a YAML file is a component or composition."""
    if "component" in data:
        return "component"
    if "model" in data:
        return "composition"
    raise click.ClickException("File must contain a 'component' or 'model' top-level key")


def _load_yaml(path: str) -> dict:
    """Load and parse a YAML file."""
    p = Path(path)
    if not p.exists():
        raise click.ClickException(f"File not found: {path}")
    with open(p) as f:
        return yaml.safe_load(f)


@click.group()
@click.version_option()
def cli():
    """Mangrove Studio — AI-powered carbon modeling tool."""
    pass


@cli.command()
@click.argument("name")
@click.option("--path", default=".", help="Parent directory for the new project")
def init(name, path):
    """Scaffold a new project."""
    project_dir = Path(path) / name
    if project_dir.exists():
        raise click.ClickException(f"Directory already exists: {project_dir}")

    project_dir.mkdir(parents=True)
    (project_dir / "components").mkdir()
    (project_dir / "compositions").mkdir()
    (project_dir / "data").mkdir()

    # Example component
    example_component = {
        "component": {
            "id": "example-emissions",
            "name": "Example Activity Emissions",
            "version": "1.0",
            "metadata": {
                "pathway": "any",
                "stage": "any",
                "description": "Example: activity × emission factor",
            },
            "inputs": {
                "event_data_points": [
                    {"slug_template": "{activity_slug}", "unit": "{activity_unit}", "description": "Activity quantity"}
                ],
                "static_data_points": [
                    {"slug_template": "{ef_slug}", "unit": "{ef_unit}", "description": "Emission factor"}
                ],
            },
            "outputs": {
                "calculated_data_points": [
                    {
                        "slug_template": "calculated-{output_prefix}-emissions",
                        "unit": "tCO\u2082e",
                        "description": "Calculated emissions",
                    }
                ]
            },
            "parameters": [
                {"name": "activity_slug", "description": "DPT slug for activity", "required": True},
                {"name": "activity_unit", "description": "Activity unit", "required": True},
                {"name": "ef_slug", "description": "EF slug", "required": True},
                {"name": "ef_unit", "description": "EF unit", "required": True},
                {"name": "output_prefix", "description": "Output slug prefix", "required": True},
            ],
            "node_tree": {
                "nexus_nodes_attributes": [
                    {
                        "name": "Emissions",
                        "operator": "product",
                        "output_unit": "tCO\u2082e",
                        "nexus_nodes_attributes": [
                            {"name": "Activity", "data_point_type": "{activity_slug}", "output_unit": "{activity_unit}"},
                            {"name": "EF", "data_point_type": "{ef_slug}", "output_unit": "{ef_unit}"},
                        ],
                    }
                ]
            },
        }
    }

    with open(project_dir / "components" / "example-emissions.yaml", "w") as f:
        yaml.dump(example_component, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Example data file
    example_data = {
        "electricity-kwh": [100.0, 200.0, 150.0],
        "ef-electricity": 0.5,
    }
    with open(project_dir / "data" / "example-data.yaml", "w") as f:
        yaml.dump(example_data, f, default_flow_style=False)

    click.echo(f"Created project: {project_dir}")
    click.echo(f"  components/  — component definitions")
    click.echo(f"  compositions/ — model compositions")
    click.echo(f"  data/        — input data files")


@cli.command()
@click.argument("path")
@click.option("--strict", is_flag=True, help="Also validate against JSON Schema")
def validate(path, strict):
    """Validate model YAML (component or composition)."""
    data = _load_yaml(path)
    file_type = _detect_type(data)

    if file_type == "component":
        issues = validate_component(data["component"])
    else:
        issues = validate_composition(data["model"])

    if strict:
        from mangrove_studio.engine.validator import (
            validate_component_schema,
            validate_composition_schema,
        )
        if file_type == "component":
            issues.extend(validate_component_schema(data))
        else:
            issues.extend(validate_composition_schema(data))

    if issues:
        click.echo(f"Validation failed ({len(issues)} issues):", err=True)
        for issue in issues:
            click.echo(f"  - {issue}", err=True)
        sys.exit(1)
    else:
        click.echo(f"Valid {file_type}: {path}")


@cli.command()
@click.argument("path")
@click.option("--data", "data_file", required=True, help="Path to input data file (YAML or JSON)")
@click.option("--format", "output_format", type=click.Choice(["table", "yaml", "json"]), default="table")
def run(path, data_file, output_format):
    """Execute calculations locally."""
    model_data = _load_yaml(path)
    file_type = _detect_type(model_data)

    # Load input data
    data_path = Path(data_file)
    if not data_path.exists():
        raise click.ClickException(f"Data file not found: {data_file}")

    with open(data_path) as f:
        if data_path.suffix == ".json":
            input_data = json.load(f)
        else:
            input_data = yaml.safe_load(f)

    # Generate node tree
    if file_type == "composition":
        yaml_str = generate_composition_yaml(model_data["model"])
        tree = yaml.safe_load(yaml_str)
    else:
        # For single components, we'd need params — for now just use the raw node tree
        tree = model_data["component"]["node_tree"]

    # Run calculations
    outputs = run_model(tree, input_data)

    if not outputs:
        click.echo("No calculated outputs produced.")
        return

    if output_format == "yaml":
        click.echo(yaml.dump(outputs, default_flow_style=False, allow_unicode=True))
    elif output_format == "json":
        click.echo(json.dumps(outputs, indent=2))
    else:
        # Table format
        click.echo(f"{'Slug':<55} {'Value':>15}")
        click.echo("-" * 72)
        for slug, value in sorted(outputs.items()):
            click.echo(f"{slug:<55} {value:>15.6f}")


@cli.command()
@click.argument("path")
def explain(path):
    """Generate human-readable methodology report."""
    data = _load_yaml(path)
    file_type = _detect_type(data)

    if file_type == "component":
        _explain_component(data["component"])
    else:
        _explain_composition(data["model"])


def _explain_component(comp: dict):
    """Print a human-readable explanation of a component."""
    click.echo(f"Component: {comp['name']} (v{comp['version']})")
    click.echo(f"ID: {comp['id']}")
    click.echo()

    meta = comp.get("metadata", {})
    click.echo(f"Pathway: {meta.get('pathway', 'any')}")
    click.echo(f"Stage: {meta.get('stage', 'any')}")
    click.echo()
    click.echo(f"Description: {meta.get('description', 'N/A')}")
    click.echo()

    # Methodology
    for m in meta.get("methodology", []):
        click.echo(f"Methodology [{m['registry']}]: {m['requirement']}")
    click.echo()

    # Parameters
    params = comp.get("parameters", [])
    if params:
        click.echo("Parameters:")
        for p in params:
            req = " (required)" if p.get("required") else f" (default: {p.get('default', 'none')})"
            click.echo(f"  {p['name']}{req} — {p['description']}")
        click.echo()

    # Inputs
    inputs = comp.get("inputs", {})
    for section, label in [
        ("event_data_points", "Event Inputs"),
        ("static_data_points", "Static Inputs"),
        ("upstream_references", "Upstream References"),
    ]:
        entries = inputs.get(section, [])
        if entries:
            click.echo(f"{label}:")
            for e in entries:
                click.echo(f"  {e['slug_template']} [{e['unit']}] — {e['description']}")
            click.echo()

    # Outputs
    outputs = comp.get("outputs", {}).get("calculated_data_points", [])
    if outputs:
        click.echo("Outputs:")
        for o in outputs:
            click.echo(f"  {o['slug_template']} [{o['unit']}] — {o['description']}")
        click.echo()

    # Calculation tree summary
    click.echo("Calculation Tree:")
    _print_tree(comp["node_tree"]["nexus_nodes_attributes"], indent=2)


def _explain_composition(model: dict):
    """Print a human-readable explanation of a composition."""
    click.echo(f"Model: {model['name']}")
    click.echo(f"ID: {model['id']}")
    click.echo()
    click.echo(f"Description: {model.get('description', 'N/A')}")
    click.echo()

    # Components used
    click.echo(f"Components ({len(model['components'])}):")
    for inst in model["components"]:
        click.echo(f"  [{inst['instance_id']}] {inst['component_id']}")
        for k, v in inst["params"].items():
            click.echo(f"    {k}: {v}")
    click.echo()

    # Tree structure
    click.echo("Tree Structure:")
    _print_tree_entries(model["tree"], indent=2)


def _print_tree(nodes: list[dict], indent: int = 0):
    """Print a node tree with indentation."""
    prefix = " " * indent
    for node in nodes:
        op = node.get("operator", "")
        dpt = node.get("data_point_type", "")
        const = node.get("constant")
        unit = node.get("output_unit", "")

        label = node.get("name", "?")
        extras = []
        if op:
            extras.append(f"op={op}")
        if dpt:
            extras.append(f"dpt={dpt}")
        if const is not None:
            extras.append(f"const={const}")
        if unit:
            extras.append(f"unit={unit}")

        extra_str = f" ({', '.join(extras)})" if extras else ""
        click.echo(f"{prefix}- {label}{extra_str}")

        children = node.get("nexus_nodes_attributes", [])
        if children:
            _print_tree(children, indent + 2)


def _print_tree_entries(entries: list[dict], indent: int = 0):
    """Print a composition tree with indentation."""
    prefix = " " * indent
    for entry in entries:
        if "component" in entry:
            click.echo(f"{prefix}- [component] {entry['component']}")
        elif "node" in entry:
            node = entry["node"]
            op = node.get("operator", "")
            dpt = node.get("data_point_type", "")
            extras = []
            if op:
                extras.append(f"op={op}")
            if dpt:
                extras.append(f"dpt={dpt}")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            click.echo(f"{prefix}- {node.get('name', '?')}{extra_str}")

        children = entry.get("children", [])
        if children:
            _print_tree_entries(children, indent + 2)


@cli.command()
@click.option("--from", "from_file", help="Path to LCA document (Excel) or text description")
@click.option("--describe", help="Generate from a text description instead of a file")
@click.option("--output", "-o", help="Output file path (default: stdout)")
@click.option("--sketch-only", is_flag=True, help="Only output the auto-parsed sketch (no AI)")
def generate(from_file, describe, output, sketch_only):
    """Generate model YAML from LCA documents or descriptions."""
    if describe:
        # Generate from text description (requires AI)
        try:
            from mangrove_studio.agent.model_generator import generate_composition_from_description
        except ImportError:
            raise click.ClickException("AI generation requires: pip install mangrove-studio[ai]")

        click.echo("Generating model from description...", err=True)
        result = generate_composition_from_description(describe)
        _output_result(result, output)
        return

    if not from_file:
        raise click.ClickException("Provide --from <file> or --describe <text>")

    from_path = Path(from_file)
    if not from_path.exists():
        raise click.ClickException(f"File not found: {from_file}")

    if from_path.suffix in (".xlsx", ".xls"):
        # Parse Excel LCA
        from mangrove_studio.agent.doc_parser import parse_excel, to_component_sketch

        click.echo(f"Parsing {from_path.name}...", err=True)
        parsed = parse_excel(from_path)
        click.echo(parsed.summary(), err=True)

        sketch = to_component_sketch(parsed)
        sketch_yaml = yaml.dump(sketch, default_flow_style=False, allow_unicode=True, sort_keys=False)

        if sketch_only:
            _output_result(sketch_yaml, output)
            return

        # Refine with AI
        try:
            from mangrove_studio.agent.model_generator import generate_from_parsed_lca
        except ImportError:
            click.echo("AI refinement requires: pip install mangrove-studio[ai]", err=True)
            click.echo("Outputting auto-parsed sketch instead:", err=True)
            _output_result(sketch_yaml, output)
            return

        click.echo("Refining with AI...", err=True)
        result = generate_from_parsed_lca(parsed.summary(), sketch_yaml)
        _output_result(result, output)
    else:
        raise click.ClickException(f"Unsupported file format: {from_path.suffix}. Use .xlsx")


def _output_result(content: str, output_path: str | None):
    """Output result to file or stdout."""
    if output_path:
        Path(output_path).write_text(content)
        click.echo(f"Written to: {output_path}", err=True)
    else:
        click.echo(content)


@cli.command()
@click.option("--port", default=3000, help="Port for local web server")
def studio(port):
    """Open Mangrove Studio web UI."""
    click.echo(f"TODO: start Studio on port {port}")


@cli.command()
def mcp():
    """Start the MCP server for AI-assisted model building."""
    from mangrove_studio.agent.mcp_server import serve
    serve()
