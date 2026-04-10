# Mangrove Studio

Open-source, AI-powered carbon modeling tool. Build, validate, run, and explain
carbon accounting models using composable YAML components.

## Project Structure

```
src/mangrove_studio/
├── __init__.py                     # Version
├── cli/main.py                     # Click CLI (init, validate, run, explain, generate, mcp)
├── engine/
│   ├── components/                 # 13 YAML component definitions
│   ├── compositions/               # 6 YAML model compositions
│   ├── schema/                     # JSON Schema for component + composition
│   ├── generator/generate.py       # YAML template generation + composition assembly
│   ├── validator/__init__.py       # Structural + JSON Schema validation
│   └── runner/__init__.py          # Calculation engine (simpleeval)
└── agent/
    ├── doc_parser/__init__.py      # Excel LCA parser (openpyxl)
    ├── model_generator/__init__.py # AI model generation (Anthropic API)
    └── mcp_server/__init__.py      # MCP server (FastMCP, 8 tools)
```

## Commands

```sh
mangrove init <name>                 # Scaffold a new project
mangrove validate <path> [--strict]  # Validate component/composition YAML
mangrove run <path> --data <file>    # Run calculations locally
mangrove explain <path>              # Human-readable model description
mangrove generate --from <xlsx>      # Generate YAML from Excel LCA
mangrove mcp                         # Start MCP server
```

## Key Concepts

- **Components**: Reusable calculation patterns (activity×EF, mass aggregation, etc.)
- **Compositions**: Assemble components into complete model trees
- **Node trees**: Bottom-up calculation graphs with operators (summation, product, quotient, difference, keisan)
- **DPT slugs**: Data point type identifiers that connect models (calculated-* for outputs)
- **Keisan expressions**: Free-form math expressions evaluated with simpleeval

## Testing

```sh
pytest                               # 89 tests
pytest tests/test_runner.py          # Runner unit + integration tests
pytest tests/test_complete_lifecycle.py  # End-to-end biochar credit pipeline
```

## Dependencies

Core: pyyaml, click, simpleeval, jsonschema
AI: anthropic, openpyxl (optional, install with pip install .[ai])
MCP: mcp[cli] (optional, install with pip install .[mcp])
Dev: pytest, ruff
