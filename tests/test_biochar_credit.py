"""End-to-end test for the complete biochar carbon credit pipeline."""

import yaml
from pathlib import Path

from mangrove_studio.engine.generator import generate_composition_yaml
from mangrove_studio.engine.runner import run_model
from mangrove_studio.engine.validator import validate_composition


COMPOSITIONS_DIR = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"


def test_biochar_credit_model_validates():
    """The credit model should pass validation."""
    with open(COMPOSITIONS_DIR / "biochar-credit-model.yaml") as f:
        data = yaml.safe_load(f)
    issues = validate_composition(data["model"])
    assert issues == [], f"Validation issues: {issues}"


def test_biochar_credit_pipeline():
    """Full credit pipeline: sequestration → permanence → net removal → buffer."""
    with open(COMPOSITIONS_DIR / "biochar-credit-model.yaml") as f:
        data = yaml.safe_load(f)

    yaml_str = generate_composition_yaml(data["model"])
    tree = yaml.safe_load(yaml_str)

    input_data = {
        "calculated-biochar-produced-dry": 90.0,
        "biochar-organic-carbon-fraction": 0.82,
        "biochar-permanence-factor": 0.89,
        "calculated-feedstock-sourcing-emissions": 5.2,
        "calculated-biochar-production-emissions": 12.8,
        "calculated-biochar-end-use-emissions": 3.1,
        "puro-buffer-fraction": 0.90,
    }

    outputs = run_model(tree, input_data)

    # Gross stored: 90 × 0.82 × 3.667 = 270.6246
    assert abs(outputs["calculated-biochar-gross-co2e-stored"] - 270.6246) < 0.01

    # Durable: 270.6246 × 0.89 = 240.855894
    assert abs(outputs["calculated-biochar-durable-co2e-stored"] - 240.8559) < 0.01

    # Net: 240.856 - 5.2 - 12.8 - 3.1 = 219.756
    assert abs(outputs["calculated-biochar-net-removal"] - 219.7559) < 0.01

    # Issued: 219.756 × 0.90 = 197.780
    assert abs(outputs["calculated-biochar-issued-credits"] - 197.7803) < 0.01

    # Net removal should be positive (viable project)
    assert outputs["calculated-biochar-net-removal"] > 0

    # Issued credits should be less than net (buffer deducted)
    assert outputs["calculated-biochar-issued-credits"] < outputs["calculated-biochar-net-removal"]


def test_biochar_credit_high_emissions_scenario():
    """If lifecycle emissions exceed stored carbon, net removal is negative."""
    with open(COMPOSITIONS_DIR / "biochar-credit-model.yaml") as f:
        data = yaml.safe_load(f)

    yaml_str = generate_composition_yaml(data["model"])
    tree = yaml.safe_load(yaml_str)

    input_data = {
        "calculated-biochar-produced-dry": 10.0,
        "biochar-organic-carbon-fraction": 0.50,
        "biochar-permanence-factor": 0.80,
        "calculated-feedstock-sourcing-emissions": 20.0,  # Very high emissions
        "calculated-biochar-production-emissions": 15.0,
        "calculated-biochar-end-use-emissions": 5.0,
        "puro-buffer-fraction": 0.90,
    }

    outputs = run_model(tree, input_data)

    # Gross: 10 × 0.50 × 3.667 = 18.335
    # Durable: 18.335 × 0.80 = 14.668
    # Net: 14.668 - 20 - 15 - 5 = -25.332 (negative!)
    assert outputs["calculated-biochar-net-removal"] < 0
