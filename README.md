# Mangrove Studio

Open-source, AI-powered carbon modeling tool. Build, validate, run, and explain
carbon accounting models using composable YAML components.

## Install

```sh
pip install mangrove-studio
```

For AI features (model generation from LCA documents):

```sh
pip install mangrove-studio[ai]
```

## Quick Start

Scaffold a new project:

```sh
mangrove init my-project
cd my-project
```

Validate a model:

```sh
mangrove validate path/to/model.yaml
```

Run a model with input data:

```sh
mangrove run path/to/composition.yaml --data path/to/data.yaml
```

Explain what a model calculates:

```sh
mangrove explain path/to/component.yaml
```

Generate a model sketch from an Excel LCA:

```sh
mangrove generate --from lca-workbook.xlsx --sketch-only
```

## Architecture

### Components

Reusable, parameterizable calculation templates defined in YAML. Each component
encodes a single calculation pattern (e.g., "activity x emission factor",
"carbon sequestration", "tonne-km transport emissions").

```yaml
component:
  id: activity-emission-factor
  name: Activity x Emission Factor
  parameters:
    - name: activity_slug
      required: true
  node_tree:
    nexus_nodes_attributes:
    - name: "Emissions"
      operator: product
      nexus_nodes_attributes:
      - name: "Activity"
        data_point_type: "{activity_slug}"
      - name: "EF"
        data_point_type: "{ef_slug}"
```

### Compositions

Assemble components into complete models with proper tree nesting.

```yaml
model:
  id: biochar-production
  components:
    - component_id: activity-emission-factor
      instance_id: electricity-emissions
      params:
        activity_slug: "electricity-kwh"
        ef_slug: "ef-electricity"
  tree:
    - component: electricity-emissions
```

### Engine

- **Generator**: Resolves parameters and assembles component trees
- **Validator**: Checks component/composition structure
- **Runner**: Evaluates node trees with real data using simpleeval

### Agent

- **Doc Parser**: Extracts LCA structure from Excel workbooks
- **Model Generator**: AI-powered YAML generation from descriptions or parsed documents
- **MCP Server**: Exposes all operations as MCP tools for IDE/agent integration

## Shipped Components

| ID | Description |
|----|-------------|
| `activity-emission-factor` | Activity quantity x emission factor |
| `carbon-intensity` | Emissions / mass ratio (tCO₂e/t) |
| `carbon-sequestration` | Mass x C% x 3.667 (CO₂/C ratio) |
| `credit-buffer` | Net removal x buffer fraction |
| `embodied-emissions-amortization` | Amortize one-time emissions over time |
| `embodied-transport-emissions` | Vehicle embodied emissions per distance |
| `fuel-combustion-emissions` | Fuel consumption x emission factor |
| `heating-value-attribution-factor` | Biochar allocation via heating values |
| `mass-aggregation` | Sum mass events across a period |
| `net-carbon-removal` | Stored - biomass - production - use emissions |
| `permanence-factor` | Gross stored x Woolf decay factor |
| `tonne-km-transport-emissions` | SUM(mass x distance) x EF |
| `unit-conversion` | Value x conversion factor |

## Shipped Compositions

| ID | Description |
|----|-------------|
| `alberta-feedstock-sourcing` | Simple feedstock mass aggregation |
| `biochar-carbon-credit` | Full credit pipeline: sequestration → permanence → net → buffer |
| `example-biochar-delivered` | Delivery transport + application + embodied vehicle emissions |
| `example-biochar-produced` | Production mass + 8 emission sources + embodied equipment |
| `example-feedstock-sourcing` | Feedstock transport + embodied, with heating-value attribution |

## MCP Server

Start the MCP server for AI-assisted model building:

```sh
mangrove mcp
```

Available tools: `list_components`, `list_compositions`, `get_component`,
`get_composition`, `validate_model`, `generate_model_yaml`, `run_composition`,
`explain_component`, `list_required_inputs`.

## Development

```sh
git clone https://github.com/veganpolice/mangrove-studio.git
cd mangrove-studio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Apache-2.0
