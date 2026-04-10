"""Tests for the CLI commands."""

import json
import tempfile
from pathlib import Path

import yaml
from click.testing import CliRunner

from mangrove_studio.cli.main import cli


runner = CliRunner()

COMPONENTS_DIR = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "components"
COMPOSITIONS_DIR = Path(__file__).parent.parent / "src" / "mangrove_studio" / "engine" / "compositions"


class TestValidate:
    def test_validate_component(self):
        result = runner.invoke(cli, ["validate", str(COMPONENTS_DIR / "activity-emission-factor.yaml")])
        assert result.exit_code == 0
        assert "Valid component" in result.output

    def test_validate_composition(self):
        result = runner.invoke(cli, ["validate", str(COMPOSITIONS_DIR / "alberta-feedstock-model.yaml")])
        assert result.exit_code == 0
        assert "Valid composition" in result.output

    def test_validate_all_shipped_components(self):
        for path in COMPONENTS_DIR.glob("*.yaml"):
            result = runner.invoke(cli, ["validate", str(path)])
            assert result.exit_code == 0, f"{path.name}: {result.output}"

    def test_validate_all_shipped_compositions(self):
        for path in COMPOSITIONS_DIR.glob("*.yaml"):
            result = runner.invoke(cli, ["validate", str(path)])
            assert result.exit_code == 0, f"{path.name}: {result.output}"

    def test_validate_missing_file(self):
        result = runner.invoke(cli, ["validate", "nonexistent.yaml"])
        assert result.exit_code != 0


class TestRun:
    def test_run_alberta_feedstock(self):
        data = {"mass-feedstock-transported": [50.0, 30.0, 20.0]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            data_path = f.name

        result = runner.invoke(cli, [
            "run", str(COMPOSITIONS_DIR / "alberta-feedstock-model.yaml"),
            "--data", data_path,
        ])
        assert result.exit_code == 0
        assert "calculated-feedstock-received" in result.output
        assert "100.000000" in result.output

    def test_run_json_output(self):
        data = {"mass-feedstock-transported": [50.0, 30.0, 20.0]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            data_path = f.name

        result = runner.invoke(cli, [
            "run", str(COMPOSITIONS_DIR / "alberta-feedstock-model.yaml"),
            "--data", data_path, "--format", "json",
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["calculated-feedstock-received"] == 100.0

    def test_run_yaml_output(self):
        data = {"mass-feedstock-transported": [50.0, 30.0, 20.0]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            data_path = f.name

        result = runner.invoke(cli, [
            "run", str(COMPOSITIONS_DIR / "alberta-feedstock-model.yaml"),
            "--data", data_path, "--format", "yaml",
        ])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["calculated-feedstock-received"] == 100.0


class TestExplain:
    def test_explain_component(self):
        result = runner.invoke(cli, ["explain", str(COMPONENTS_DIR / "carbon-intensity.yaml")])
        assert result.exit_code == 0
        assert "Carbon Intensity" in result.output
        assert "quotient" in result.output

    def test_explain_composition(self):
        result = runner.invoke(cli, ["explain", str(COMPOSITIONS_DIR / "example-biochar-produced-model.yaml")])
        assert result.exit_code == 0
        assert "Biochar Production" in result.output
        assert "12" in result.output  # 12 components


class TestInit:
    def test_init_creates_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, ["init", "my-project", "--path", tmpdir])
            assert result.exit_code == 0

            project_dir = Path(tmpdir) / "my-project"
            assert project_dir.exists()
            assert (project_dir / "components").is_dir()
            assert (project_dir / "compositions").is_dir()
            assert (project_dir / "data").is_dir()
            assert (project_dir / "components" / "example-emissions.yaml").exists()

    def test_init_fails_if_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "existing").mkdir()
            result = runner.invoke(cli, ["init", "existing", "--path", tmpdir])
            assert result.exit_code != 0
