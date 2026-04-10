"""Tests for the calculation runner."""

import pytest
import yaml
from pathlib import Path

from mangrove_studio.engine.runner import RunContext, evaluate_node, run_model


class TestRunContext:
    def test_resolve_scalar(self):
        ctx = RunContext({"slug-a": 10.0})
        assert ctx.resolve("slug-a") == 10.0

    def test_resolve_list_aggregated(self):
        ctx = RunContext({"slug-a": [1.0, 2.0, 3.0]})
        assert ctx.resolve("slug-a", aggregate=True) == 6.0

    def test_resolve_list_not_aggregated(self):
        ctx = RunContext({"slug-a": [1.0, 2.0, 3.0]})
        assert ctx.resolve("slug-a", aggregate=False) == [1.0, 2.0, 3.0]

    def test_resolve_missing_slug(self):
        ctx = RunContext({})
        with pytest.raises(ValueError, match="not found"):
            ctx.resolve("missing-slug")

    def test_resolve_output(self):
        ctx = RunContext({})
        ctx.outputs["calculated-x"] = 42.0
        assert ctx.resolve("calculated-x") == 42.0


class TestLeafNodes:
    def test_constant_node(self):
        node = {"name": "Conversion", "constant": 3.67}
        ctx = RunContext({})
        assert evaluate_node(node, ctx) == 3.67

    def test_dpt_leaf_scalar(self):
        node = {"name": "Mass", "data_point_type": "tons-produced"}
        ctx = RunContext({"tons-produced": 100.0})
        assert evaluate_node(node, ctx) == 100.0

    def test_dpt_leaf_aggregated(self):
        node = {"name": "Mass", "data_point_type": "tons-produced", "should_aggregate": True}
        ctx = RunContext({"tons-produced": [10.0, 20.0, 30.0]})
        assert evaluate_node(node, ctx) == 60.0

    def test_dpt_leaf_not_aggregated(self):
        node = {"name": "Mass", "data_point_type": "tons-produced", "should_aggregate": False}
        ctx = RunContext({"tons-produced": [10.0, 20.0, 30.0]})
        assert evaluate_node(node, ctx) == [10.0, 20.0, 30.0]


class TestSummation:
    def test_simple_sum(self):
        node = {
            "name": "Total",
            "operator": "summation",
            "mangrove_nodes": [
                {"name": "A", "constant": 10.0},
                {"name": "B", "constant": 20.0},
                {"name": "C", "constant": 30.0},
            ],
        }
        ctx = RunContext({})
        assert evaluate_node(node, ctx) == 60.0

    def test_sum_with_data_points(self):
        node = {
            "name": "Total Mass",
            "operator": "summation",
            "data_point_type": "calculated-total",
            "mangrove_nodes": [
                {"name": "Wet", "data_point_type": "tons-wet"},
                {"name": "Dry", "data_point_type": "tons-dry"},
            ],
        }
        ctx = RunContext({"tons-wet": 100.0, "tons-dry": 80.0})
        assert evaluate_node(node, ctx) == 180.0
        assert ctx.outputs["calculated-total"] == 180.0


class TestProduct:
    def test_simple_product(self):
        node = {
            "name": "Emissions",
            "operator": "product",
            "mangrove_nodes": [
                {"name": "Activity", "data_point_type": "kwh-used"},
                {"name": "EF", "data_point_type": "ef-electricity"},
            ],
        }
        ctx = RunContext({"kwh-used": 1000.0, "ef-electricity": 0.5})
        assert evaluate_node(node, ctx) == 500.0

    def test_product_with_aggregated_events(self):
        """Activity summed across events, then multiplied by EF."""
        node = {
            "name": "Emissions",
            "operator": "product",
            "mangrove_nodes": [
                {"name": "Activity", "data_point_type": "kwh-used", "should_aggregate": True},
                {"name": "EF", "data_point_type": "ef-electricity"},
            ],
        }
        ctx = RunContext({"kwh-used": [100.0, 200.0, 300.0], "ef-electricity": 0.5})
        assert evaluate_node(node, ctx) == 300.0  # (100+200+300) * 0.5


class TestQuotient:
    def test_simple_quotient(self):
        node = {
            "name": "CI",
            "operator": "quotient",
            "mangrove_nodes": [
                {"name": "Emissions", "data_point_type": "total-emissions", "order": 0},
                {"name": "Mass", "data_point_type": "total-mass", "order": 1},
            ],
        }
        ctx = RunContext({"total-emissions": 10.0, "total-mass": 100.0})
        assert evaluate_node(node, ctx) == 0.1

    def test_quotient_division_by_zero(self):
        node = {
            "name": "CI",
            "operator": "quotient",
            "mangrove_nodes": [
                {"name": "Num", "constant": 10.0, "order": 0},
                {"name": "Den", "constant": 0.0, "order": 1},
            ],
        }
        ctx = RunContext({})
        with pytest.raises(ValueError, match="Division by zero"):
            evaluate_node(node, ctx)


class TestDifference:
    def test_simple_difference(self):
        node = {
            "name": "Net",
            "operator": "difference",
            "mangrove_nodes": [
                {"name": "Gross", "constant": 100.0, "order": 0},
                {"name": "Deduction", "constant": 30.0, "order": 1},
            ],
        }
        ctx = RunContext({})
        assert evaluate_node(node, ctx) == 70.0


class TestKeisan:
    def test_keisan_expression_with_children(self):
        """Embodied emissions amortization: (ee * days) / (rate * 365)"""
        node = {
            "name": "Amortized EE",
            "operator": "(ee_slug * days_slug) / (rate_slug * 365)",
            "mangrove_nodes": [
                {"name": "EE", "data_point_type": "ee-slug", "order": 0},
                {"name": "Rate", "data_point_type": "rate-slug", "order": 1},
                {"name": "Days", "data_point_type": "days-slug", "order": 2},
            ],
        }
        ctx = RunContext({"ee-slug": 10000.0, "rate-slug": 10.0, "days-slug": 30.0})
        result = evaluate_node(node, ctx)
        expected = (10000.0 * 30.0) / (10.0 * 365)
        assert abs(result - expected) < 0.001

    def test_literal_keisan_expression(self):
        """Expression like '1 - fuel-moisture-content-'"""
        node = {
            "name": "Dry Percentage",
            "operator": "1 - fuel-moisture-content-",
            "data_point_type": "fuel-dry-percentage",
            "mangrove_nodes": [
                {"name": "Moisture", "data_point_type": "fuel-moisture-content-"},
            ],
        }
        ctx = RunContext({"fuel-moisture-content-": 0.35})
        result = evaluate_node(node, ctx)
        assert abs(result - 0.65) < 0.001
        assert abs(ctx.outputs["fuel-dry-percentage"] - 0.65) < 0.001

    def test_keisan_difference_expression(self):
        """Expression like 'slug-a - slug-b'"""
        node = {
            "name": "Dry Mass",
            "operator": "tons-wet - tons-water",
            "data_point_type": "calculated-dry",
            "mangrove_nodes": [
                {"name": "Wet", "data_point_type": "tons-wet"},
                {"name": "Water", "data_point_type": "tons-water"},
            ],
        }
        ctx = RunContext({"tons-wet": 100.0, "tons-water": 20.0})
        result = evaluate_node(node, ctx)
        assert result == 80.0


class TestSumproductPattern:
    def test_tonne_km_transport(self):
        """The critical sumproduct pattern: SUM(mass_i * distance_i) * EF."""
        node = {
            "name": "Transport Emissions",
            "operator": "product",
            "mangrove_nodes": [
                {
                    "name": "Tonne-km total",
                    "operator": "summation",
                    "mangrove_nodes": [
                        {
                            "name": "Per-delivery tonne-km",
                            "operator": "product",
                            "should_aggregate": False,
                            "mangrove_nodes": [
                                {
                                    "name": "Distance",
                                    "data_point_type": "delivery-distance",
                                    "should_aggregate": False,
                                },
                                {
                                    "name": "Mass",
                                    "data_point_type": "delivery-mass",
                                    "should_aggregate": False,
                                },
                            ],
                        },
                    ],
                },
                {"name": "EF", "data_point_type": "ef-transport"},
            ],
        }
        ctx = RunContext({
            "delivery-distance": [100.0, 200.0, 50.0],
            "delivery-mass": [10.0, 5.0, 20.0],
            "ef-transport": 0.1,
        })
        result = evaluate_node(node, ctx)
        # SUM(100*10, 200*5, 50*20) * 0.1 = SUM(1000, 1000, 1000) * 0.1 = 3000 * 0.1 = 300
        assert result == 300.0


class TestOutputCapture:
    def test_output_stored_in_context(self):
        node = {
            "name": "Total",
            "operator": "summation",
            "data_point_type": "calculated-total",
            "mangrove_nodes": [
                {"name": "A", "constant": 10.0},
                {"name": "B", "constant": 20.0},
            ],
        }
        ctx = RunContext({})
        evaluate_node(node, ctx)
        assert ctx.outputs["calculated-total"] == 30.0


class TestRunModel:
    def test_run_simple_model(self):
        tree = {
            "mangrove_nodes": [
                {
                    "name": "Emissions",
                    "operator": "product",
                    "data_point_type": "calculated-emissions",
                    "mangrove_nodes": [
                        {"name": "Activity", "data_point_type": "kwh-used"},
                        {"name": "EF", "data_point_type": "ef-electricity"},
                    ],
                },
            ],
        }
        outputs = run_model(tree, {"kwh-used": 1000.0, "ef-electricity": 0.5})
        assert outputs == {"calculated-emissions": 500.0}

    def test_run_multi_root_model(self):
        """Model with multiple root nodes (like biochar produced model)."""
        tree = {
            "mangrove_nodes": [
                {
                    "name": "Total Mass",
                    "operator": "summation",
                    "data_point_type": "calculated-mass-total",
                    "mangrove_nodes": [
                        {"name": "Mass Input", "data_point_type": "tons-input"},
                    ],
                },
                {
                    "name": "Emissions",
                    "operator": "product",
                    "data_point_type": "calculated-emissions",
                    "mangrove_nodes": [
                        {"name": "Activity", "data_point_type": "kwh-used"},
                        {"name": "EF", "data_point_type": "ef-electricity"},
                    ],
                },
            ],
        }
        outputs = run_model(tree, {
            "tons-input": [10.0, 20.0],
            "kwh-used": 500.0,
            "ef-electricity": 0.4,
        })
        assert outputs["calculated-mass-total"] == 30.0
        assert outputs["calculated-emissions"] == 200.0


class TestWithGeneratedCompositions:
    """Test runner with actual generated composition YAML from the project."""

    def _load_and_generate(self, composition_path: str) -> dict:
        from mangrove_studio.engine.generator import generate_composition_yaml
        with open(composition_path) as f:
            data = yaml.safe_load(f)
        yaml_str = generate_composition_yaml(data["model"])
        return yaml.safe_load(yaml_str)

    def test_alberta_feedstock_model(self):
        """Alberta feedstock: simple mass aggregation."""
        compositions_dir = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"
        tree = self._load_and_generate(str(compositions_dir / "alberta-feedstock-model.yaml"))

        outputs = run_model(tree, {
            "mass-feedstock-transported": [50.0, 30.0, 20.0],
        })
        assert outputs["calculated-feedstock-received"] == 100.0

    def test_example_biochar_produced_model(self):
        """Example biochar production: mass tracking + process emissions."""
        compositions_dir = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"
        tree = self._load_and_generate(str(compositions_dir / "example-biochar-produced-model.yaml"))

        # Provide all the input data points the model needs
        data = {
            # Mass tracking
            "tons-biochar-produced-wet": [50.0, 60.0],
            "tons-biochar-produced-dry": [40.0, 50.0],
            # Embodied emissions amortization
            "constant-equipment-and-material-embodied-emissions": 50000.0,
            "constant-embodied-emissions-amortization-rate": 10.0,
            "production---days-in-production-period": 30.0,
            # Feedstock sourcing (upstream reference)
            "calculated-feedstock-sourcing-emissions": 5.0,
            # Electricity
            "production-electricity-use-full-allocation": [100.0, 150.0],
            "ef-electricity": 0.5,
            # Lubricant
            "production---lubricant-usage-gallon": [2.0, 3.0],
            "ef-lubricant": 10.0,
            # Stack (methane)
            "production---methane-emissions-per-us-ton-feedstock": [0.1, 0.15],
            "gwp-ch4-to-co2e": 28.0,
            # Processing
            "ef-blending-with-compost": 5.0,
            # Water
            "water-added-to-biochar": [100.0, 120.0],
            "ef-water": 0.001,
            # Packaging
            "constant-packaging-bags-used-per-day": [10.0, 12.0],
            "ef-textile-bag-material": 2.0,
            # Mailing
            "production---usd-spent-on-mailing-samples": [50.0, 30.0],
            "ef-mailing-per-usd": 0.01,
            # Staff travel
            "production---staff-travel-miles": [100.0, 150.0],
            "ef-staff-travel-per-mile": 0.4,
        }

        outputs = run_model(tree, data)

        # Mass tracking should sum correctly
        assert outputs["calculated-biochar-produced-wet-monthly"] == 110.0
        assert outputs["calculated-biochar-produced-dry"] == 90.0

        # Production emissions should be calculated
        assert "calculated-biochar-production-emissions" in outputs

        # Carbon intensity should be calculated
        assert "biochar-produced-ci" in outputs

        # All values should be finite numbers
        for slug, value in outputs.items():
            assert isinstance(value, (int, float)), f"{slug} is not a number: {value}"
