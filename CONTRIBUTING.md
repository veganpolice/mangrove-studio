# Contributing to Mangrove Studio

Thank you for contributing to open carbon accounting.

## What to Contribute

The most impactful contributions are **components** and **compositions** that
encode real-world carbon accounting methodology knowledge.

### Components

A component is a reusable calculation pattern. The component library currently
covers common LCA patterns (activity x emission factor, transport emissions,
carbon sequestration). Components needed:

- Regional electricity grid emission factors
- Soil carbon modeling (enhanced weathering, soil amendment)
- Direct air capture energy and material balance
- Biogas/biomethane pathway calculations
- Forestry and land use change accounting
- Ocean-based carbon removal (alkalinity enhancement, seaweed)
- Waste-to-energy and waste diversion credits

### Compositions

A composition assembles components into a complete model for a specific project
type. Reference implementations needed for:

- Puro.earth biochar (full methodology)
- Isometric biochar (with modular accounting)
- Isometric enhanced weathering
- Isometric direct air capture
- Verra VM0044 (biochar)
- CARB LCFS (renewable natural gas, hydrogen)
- Gold Standard improved cookstoves
- Any new methodology you're implementing

### Emission Factor Libraries

Curated, sourced emission factors for specific contexts:

- Country-specific grid electricity factors
- Regional freight transport factors (road, rail, maritime, air)
- Fuel combustion factors by fuel type and region
- Construction material embodied emissions
- Agricultural input emission factors

## Component Anatomy

Every component follows this structure:

```yaml
component:
  id: kebab-case-id          # Unique identifier
  name: Human Readable Name
  version: "1.0"

  metadata:
    pathway: biochar          # Carbon removal pathway
    stage: production         # Lifecycle stage
    description: >-
      What this component calculates and why.
    methodology:
      - registry: isometric   # Which standard this satisfies
        requirement: "Specific requirement text"

  inputs:
    event_data_points:        # Per-event measurements
      - slug_template: "{param}-slug"
        unit: "kWh"
        description: What this measures
    static_data_points:       # Constants and emission factors
      - slug_template: "ef-something"
        unit: "kgCO₂e/kWh"
        description: Emission factor source

  outputs:
    calculated_data_points:
      - slug_template: "calculated-{param}-result"
        unit: "tCO₂e"
        description: What this produces

  parameters:                 # Make it reusable
    - name: param_name
      description: What this controls
      required: true

  node_tree:                  # The calculation
    mangrove_nodes:
    - name: "Root Node"
      operator: product
      mangrove_nodes:
      - name: "Input A"
        data_point_type: "{param}-slug"
      - name: "Input B"
        data_point_type: "ef-something"
```

## Quality Checklist

Before submitting a component or composition:

- [ ] `mangrove validate --strict your-file.yaml` passes
- [ ] Parameters use `{placeholder}` syntax for project-specific values
- [ ] Methodology references point to specific registry requirements
- [ ] Description explains the calculation clearly
- [ ] Units are correct (use tCO₂e, kgCO₂e, not kgCO2e)
- [ ] Example data file is provided (for compositions)
- [ ] Tests are included
- [ ] `pytest` passes

## Development Setup

```sh
git clone https://github.com/veganpolice/mangrove-studio.git
cd mangrove-studio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Code Style

- Python: ruff with line-length 120
- YAML: 2-space indent, no flow style
- Slugs: lowercase, hyphens, calculated outputs prefixed with `calculated-`
- Units: Unicode subscripts (tCO₂e not tCO2e)
