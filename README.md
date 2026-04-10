# Mangrove Studio

Open-source carbon modeling tool. Build, validate, run, and explain carbon
accounting models using composable YAML components written in Mangrove YAML.

## Why Open Source

Carbon accounting is too important to be a black box. Every tonne of carbon
removal sold as a credit depends on calculations that buyers, auditors, and
regulators need to trust. Mangrove Studio makes those calculations transparent,
reproducible, and community-driven.

**For project developers:** Model your carbon removal project locally before
deploying to production. Validate your methodology implementation against
registry requirements. Run calculations with real data and see exactly how
every number is derived.

**For auditors and verifiers:** Inspect the full calculation tree for any
model. Every operator, every input, every emission factor is visible in
plain YAML. No hidden spreadsheet formulas or proprietary black boxes.

**For the carbon removal community:** Contribute components and model
compositions that encode real-world methodology knowledge. When you solve
a modeling problem — transport emissions for a specific corridor, permanence
factors for a new feedstock, allocation logic for a coproduct — share it so
the next project doesn't start from scratch.

## Mangrove YAML

Mangrove YAML is a declarative modeling syntax for carbon accounting. Models
are defined as trees of calculation nodes that evaluate bottom-up — leaf nodes
hold input data, operator nodes combine their children, and the root produces
the final result.

The syntax is designed to be readable by both humans and machines:

```yaml
component:
  id: activity-emission-factor
  name: Activity x Emission Factor
  parameters:
    - name: activity_slug
      required: true
  node_tree:
    mangrove_nodes:
    - name: "Emissions from {activity_name}"
      operator: product
      mangrove_nodes:
      - name: "Activity"
        data_point_type: "{activity_slug}"
      - name: "Emission Factor"
        data_point_type: "{ef_slug}"
```

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

Reusable, parameterizable calculation templates. Each component encodes a
single calculation pattern that can be instantiated with different parameters
for different projects. Components are the building blocks — small, tested,
and methodology-aware.

### Compositions

Assemble components into complete models with proper tree nesting. A composition
declares which component instances it uses, provides their parameters, and
defines how they connect in the calculation tree.

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
- **Validator**: Structural checks + JSON Schema validation
- **Runner**: Evaluates node trees with real data using simpleeval

### Agent

- **Doc Parser**: Extracts LCA structure from Excel workbooks
- **Model Generator**: AI-powered YAML generation from descriptions or parsed documents
- **MCP Server**: Exposes all operations as MCP tools for IDE/agent integration

## Component Library

The shipped component library covers the most common carbon accounting
calculation patterns. Each component is a standalone YAML file that can be
validated, explained, and tested independently.

| Component | Description |
|-----------|-------------|
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

## Example Compositions

| Composition | Description |
|-------------|-------------|
| `alberta-feedstock-sourcing` | Simple feedstock mass aggregation |
| `biochar-carbon-credit` | Full credit pipeline: sequestration -> permanence -> net -> buffer |
| `complete-biochar-lifecycle` | End-to-end 15-component lifecycle model |
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

## Contributing

Mangrove Studio is built to grow through community contributions. The component
library and composition catalog are where contributions have the most impact.

### Contributing Components

A component encodes a single reusable calculation pattern. Good component
contributions:

- **Solve a real problem.** If you built a calculation for your project that
  others would need — a regional transport emission factor pattern, a
  methodology-specific allocation formula, a novel permanence model — package
  it as a component.

- **Are parameterizable.** Use `{parameter}` placeholders so the component
  works across different projects. The same transport emissions component
  should work for feedstock delivery and product delivery.

- **Include methodology references.** Add `methodology` entries in the metadata
  linking to the registry requirement the component satisfies (Isometric,
  Puro, Verra, CARB, etc.).

- **Pass validation.** Run `mangrove validate --strict your-component.yaml`
  before submitting.

To add a component, create a YAML file in `src/mangrove_studio/engine/components/`
following the existing patterns. See `activity-emission-factor.yaml` for a
simple example or `heating-value-attribution-factor.yaml` for a complex one.

### Contributing Compositions

A composition shows how components fit together for a specific project type.
Good composition contributions:

- **Represent a real methodology.** A complete Puro biochar model, an Isometric
  enhanced weathering model, a Verra REDD+ deforestation model. These are
  the reference implementations that help new projects get started.

- **Cover a full stage or lifecycle.** A feedstock sourcing model, a production
  emissions model, a delivery model, a complete credit pipeline.

- **Include example data.** Add a matching data YAML file in `examples/` so
  users can run the model immediately and see real outputs.

To add a composition, create a YAML file in
`src/mangrove_studio/engine/compositions/` and an example data file in
`examples/`.

### How to Submit

1. Fork the repository
2. Create a branch (`git checkout -b add-transport-component`)
3. Add your component or composition with tests
4. Run `pytest` to make sure everything passes
5. Open a pull request with a description of what the component models
   and which methodology it implements

### Other Ways to Contribute

- **Methodology implementations.** Port a registry's methodology requirements
  into a set of components and compositions.
- **LCA tool parsers.** Add import support for new LCA tool formats (openLCA
  JSON-LD, SimaPro CSV, Brightway2).
- **Emission factor libraries.** Curate emission factors for specific regions,
  industries, or transport corridors.
- **Documentation.** Explain how a particular carbon removal pathway works
  and how to model it with Mangrove YAML.
- **Bug reports and test cases.** Found an edge case? Submit a failing test.

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
