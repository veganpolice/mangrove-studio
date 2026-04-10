"""Integration test for the complete biochar lifecycle model.

Uses properly-scaled emission factors (tCO₂e/unit) to produce realistic
carbon credit numbers. In production, Mangrove's Unitwise engine handles
unit conversion automatically; here we pre-scale EFs to tCO₂e.
"""

import yaml
from pathlib import Path

from mangrove_studio.engine.generator import generate_composition_yaml
from mangrove_studio.engine.runner import run_model
from mangrove_studio.engine.validator import validate_composition


COMPOSITIONS_DIR = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"


def test_complete_lifecycle_validates():
    with open(COMPOSITIONS_DIR / "complete-biochar-lifecycle.yaml") as f:
        data = yaml.safe_load(f)
    issues = validate_composition(data["model"])
    assert issues == [], f"Validation: {issues}"


def test_complete_lifecycle_positive_credits():
    """With properly-scaled EFs, a viable biochar project produces positive credits."""
    with open(COMPOSITIONS_DIR / "complete-biochar-lifecycle.yaml") as f:
        data = yaml.safe_load(f)

    yaml_str = generate_composition_yaml(data["model"])
    tree = yaml.safe_load(yaml_str)

    # All emission factors pre-scaled to tCO₂e per unit
    input_data = {
        # Feedstock (3 deliveries)
        "feedstock-mass-tonnes": [50.0, 40.0, 35.0],
        # Production (2 runs)
        "biochar-produced-wet-tonnes": [30.0, 25.0],
        "biochar-produced-dry-tonnes": [24.0, 20.0],
        # Production inputs
        "electricity-kwh": [2000.0, 1800.0],
        "diesel-litres": [50.0, 45.0],
        "water-litres": [500.0, 450.0],
        "days-in-period": 30.0,
        # Equipment
        "constant-equipment-embodied-emissions": 25.0,  # tCO₂e total (pre-scaled)
        "constant-amortization-years": 15.0,
        # EFs in tCO₂e per unit (pre-scaled from kgCO₂e by /1000)
        "ef-grid-electricity": 0.00042,     # tCO₂e/kWh
        "ef-diesel": 0.00268,               # tCO₂e/L
        "ef-water": 0.000001,               # tCO₂e/L
        "ef-heavy-truck": 0.0001,           # tCO₂e/t.km
        "ef-application": 0.0005,           # tCO₂e/t
        # Feedstock emissions
        "calculated-feedstock-emissions": 3.5,
        # Delivery
        "delivery-distance-km": [150.0, 200.0],
        # Biochar characterization
        "biochar-organic-carbon-fraction": 0.78,
        "permanence-factor-woolf": 0.87,
        "buffer-fraction": 0.90,
    }

    outputs = run_model(tree, input_data)

    # Verify mass tracking
    assert outputs["calculated-feedstock-received"] == 125.0
    assert outputs["calculated-biochar-produced-wet"] == 55.0
    assert outputs["calculated-biochar-produced-dry"] == 44.0

    # Gross stored: 44 × 0.78 × 3.667 = 125.85
    assert abs(outputs["calculated-biochar-gross-co2e-stored"] - 125.85) < 0.1

    # Production emissions should be small (< 10 tCO₂e)
    assert outputs["calculated-production-emissions"] < 10.0

    # Net removal should be positive for a viable project
    assert outputs["calculated-biochar-net-removal"] > 0

    # Issued credits should be positive
    assert outputs["calculated-biochar-issued-credits"] > 0

    # Issued credits = 90% of net (10% buffer)
    assert abs(
        outputs["calculated-biochar-issued-credits"]
        - outputs["calculated-biochar-net-removal"] * 0.90
    ) < 0.01

    # Carbon intensity should be reasonable (< 5 tCO₂e/t)
    assert outputs["lifecycle-carbon-intensity"] < 5.0
