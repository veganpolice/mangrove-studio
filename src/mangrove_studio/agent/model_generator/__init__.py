"""AI-powered model generator — uses Claude to generate component YAML from LCA documents.

Takes a parsed LCA structure (from doc_parser) or a text description and generates
valid Mangrove component/composition YAML using the Anthropic API.
"""

import json
from pathlib import Path

import yaml

# Lazy import — only needed when actually generating
_anthropic_client = None


def _get_client():
    """Get or create the Anthropic client (lazy import)."""
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
            _anthropic_client = anthropic.Anthropic()
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for AI generation. "
                "Install with: pip install mangrove-studio[ai]"
            )
    return _anthropic_client


# The system prompt that teaches Claude how to generate Mangrove YAML
SYSTEM_PROMPT = """You are a carbon accounting model builder for Mangrove Studio.
You generate YAML component definitions and model compositions following Mangrove's schema.

## Component Definition Schema

A component is a reusable, parameterizable calculation template:

```yaml
component:
  id: kebab-case-id
  name: Human Readable Name
  version: "1.0"
  metadata:
    pathway: biochar|dac|enhanced-weathering|any
    stage: sourcing|production|delivery|sequestration|credit|any
    description: What this component calculates and why
    methodology:
      - registry: isometric|puro|verra|any
        requirement: Specific methodology requirement this satisfies
  inputs:
    event_data_points:
      - slug_template: "{param}-slug-name"
        unit: "kWh"
        description: What this input measures
    static_data_points:
      - slug_template: "ef-something"
        unit: "kgCO₂e/kWh"
        description: Emission factor or constant
    upstream_references:
      - slug_template: "calculated-upstream-value"
        unit: "tCO₂e"
        description: Calculated value from upstream model
  outputs:
    calculated_data_points:
      - slug_template: "calculated-{param}-output"
        unit: "tCO₂e"
        description: What this component produces
  parameters:
    - name: param_name
      description: What this parameter controls
      required: true
    - name: optional_param
      description: Has a default value
      default: "some-value"
  node_tree:
    nexus_nodes_attributes:
    - name: "Root Node {param}"
      output_unit: tCO₂e
      operator: product|summation|quotient|difference
      data_point_type: "calculated-{param}-output"
      nexus_nodes_attributes:
      - name: "Child leaf"
        output_unit: kWh
        data_point_type: "{param}-slug"
        should_aggregate: true
```

## Model Composition Schema

A composition assembles components into a complete model:

```yaml
model:
  id: model-id
  name: Model Name
  description: What this model calculates
  components:
    - component_id: existing-component-id
      instance_id: unique-instance-name
      params:
        param_name: "value"
  tree:
    - component: instance-id
    - node:
        name: Grouping Node
        operator: summation
        output_unit: tCO₂e
        data_point_type: calculated-total
      children:
        - component: instance-a
        - component: instance-b
```

## Available Components

These component types are available for use in compositions:
- activity-emission-factor: activity × EF (generic)
- carbon-intensity: emissions / mass ratio
- carbon-sequestration: mass × C% × 3.667
- credit-buffer: net × buffer fraction
- embodied-emissions-amortization: (EE × days) / (rate × 365)
- embodied-transport-emissions: distance × embodied EF
- fuel-combustion-emissions: fuel × EF
- heating-value-attribution-factor: biochar attribution via heating values
- mass-aggregation: sum of mass events
- net-carbon-removal: stored - E_biomass - E_production - E_use
- permanence-factor: gross × permanence fraction
- tonne-km-transport-emissions: SUM(mass × distance) × EF
- unit-conversion: value × conversion factor

## Key Rules

1. Slugs: lowercase, hyphens, e.g., "tons-biochar-produced-dry"
2. Calculated DPTs always start with "calculated-"
3. Units use Unicode: tCO₂e (not tCO2e), kgCO₂e
4. Each stage model outputs BOTH mass AND emissions
5. Models connect by slug references (no formal links)
6. Use should_aggregate: true for event data that sums across events
7. Order matters for quotient and difference operators (use order: 0, 1)
8. The sumproduct pattern: inner product with should_aggregate: false, wrapped in summation

Output ONLY valid YAML. No explanations before or after the YAML block."""


def generate_component_from_description(description: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Generate a component YAML from a text description.

    Args:
        description: Natural language description of the component
        model: Claude model to use

    Returns:
        YAML string of the generated component
    """
    client = _get_client()

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Generate a Mangrove component definition for:\n\n{description}",
        }],
    )

    return _extract_yaml(message.content[0].text)


def generate_composition_from_description(description: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Generate a composition YAML from a text description.

    Args:
        description: Natural language description of the model
        model: Claude model to use

    Returns:
        YAML string of the generated composition
    """
    client = _get_client()

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "Generate a Mangrove model composition for:\n\n"
                f"{description}\n\n"
                "Use existing component types from the Available Components list where possible. "
                "Only create inline nodes for project-specific calculations that don't fit a component."
            ),
        }],
    )

    return _extract_yaml(message.content[0].text)


def generate_from_parsed_lca(parsed_lca_summary: str, sketch_yaml: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Generate refined component YAML from a parsed LCA sketch.

    Takes the rough sketch from doc_parser.to_component_sketch() and
    refines it into proper Mangrove component/composition YAML.

    Args:
        parsed_lca_summary: Human-readable summary of the parsed LCA
        sketch_yaml: YAML string from to_component_sketch()
        model: Claude model to use

    Returns:
        Refined YAML string
    """
    client = _get_client()

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "I have parsed an Excel LCA spreadsheet. Here's the summary:\n\n"
                f"{parsed_lca_summary}\n\n"
                "And here's a rough auto-generated sketch:\n\n"
                f"```yaml\n{sketch_yaml}\n```\n\n"
                "Please refine this into a proper Mangrove model composition that:\n"
                "1. Uses existing component types where possible\n"
                "2. Has proper slug naming conventions\n"
                "3. Has correct operators and tree structure\n"
                "4. Includes proper metadata and methodology references\n"
                "5. Follows the stage model pattern (each stage outputs mass + emissions)"
            ),
        }],
    )

    return _extract_yaml(message.content[0].text)


def validate_generated_yaml(yaml_str: str) -> list[str]:
    """Validate generated YAML against the Mangrove schema.

    Returns list of issues found, empty if valid.
    """
    from mangrove_studio.engine.validator import validate_component, validate_composition

    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["YAML must be a dict"]

    if "component" in data:
        return validate_component(data["component"])
    elif "model" in data:
        return validate_composition(data["model"])
    else:
        return ["YAML must have a 'component' or 'model' top-level key"]


def _extract_yaml(text: str) -> str:
    """Extract YAML from a response that may contain markdown code fences."""
    # Try to find YAML in code fences
    import re
    match = re.search(r"```(?:yaml)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no code fences, return the text as-is (assume it's all YAML)
    return text.strip()
