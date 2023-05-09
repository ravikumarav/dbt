import pytest
from hologram import ValidationError
from dbt.contracts.graph.model_config import MetricConfig
from dbt.exceptions import CompilationError
from dbt.tests.util import run_dbt, update_config_file, get_manifest


from tests.functional.metrics.fixtures import (
    models_people_sql,
    models_people_metrics_yml,
    disabled_metric_level_schema_yml,
    enabled_metric_level_schema_yml,
    models_people_metrics_sql,
    invalid_config_metric_yml,
)


class MetricConfigTests:
    @pytest.fixture(scope="class", autouse=True)
    def setUp(self):
        pytest.expected_config = MetricConfig(
            enabled=True,
        )


# Test enabled config in dbt_project.yml
class TestMetricEnabledConfigProjectLevel(MetricConfigTests):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "people.sql": models_people_sql,
            "schema.yml": models_people_metrics_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "metrics": {
                "number_of_people": {
                    "enabled": True,
                },
            }
        }

    def test_enabled_metric_config_dbt_project(self, project):
        run_dbt(["parse"])
        manifest = get_manifest(project.project_root)
        assert "metric.test.number_of_people" in manifest.metrics

        new_enabled_config = {
            "metrics": {
                "test": {
                    "number_of_people": {
                        "enabled": False,
                    },
                }
            }
        }
        update_config_file(new_enabled_config, project.project_root, "dbt_project.yml")
        run_dbt(["parse"])
        manifest = get_manifest(project.project_root)
        assert "metric.test.number_of_people" not in manifest.metrics
        assert "metric.test.collective_tenure" in manifest.metrics


# Test enabled config at metrics level in yml file
class TestConfigYamlMetricLevel(MetricConfigTests):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "people.sql": models_people_sql,
            "schema.yml": disabled_metric_level_schema_yml,
        }

    def test_metric_config_yaml_metric_level(self, project):
        run_dbt(["parse"])
        manifest = get_manifest(project.project_root)
        assert "metric.test.number_of_people" not in manifest.metrics
        assert "metric.test.collective_tenure" in manifest.metrics


# Test inheritence - set configs at project and metric level - expect metric level to win
class TestMetricConfigsInheritence(MetricConfigTests):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "people.sql": models_people_sql,
            "schema.yml": enabled_metric_level_schema_yml,
        }

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"metrics": {"enabled": False}}

    def test_metrics_all_configs(self, project):
        run_dbt(["parse"])
        manifest = get_manifest(project.project_root)
        # This should be overridden
        assert "metric.test.number_of_people" in manifest.metrics
        # This should stay disabled
        assert "metric.test.collective_tenure" not in manifest.metrics

        config_test_table = manifest.metrics.get("metric.test.number_of_people").config

        assert isinstance(config_test_table, MetricConfig)
        assert config_test_table == pytest.expected_config


# Test CompilationError if a model references a disabled metric
class TestDisabledMetricRef(MetricConfigTests):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "people.sql": models_people_sql,
            "people_metrics.sql": models_people_metrics_sql,
            "schema.yml": models_people_metrics_yml,
        }

    def test_disabled_metric_ref_model(self, project):
        run_dbt(["parse"])
        manifest = get_manifest(project.project_root)
        assert "metric.test.number_of_people" in manifest.metrics
        assert "metric.test.collective_tenure" in manifest.metrics
        assert "model.test.people_metrics" in manifest.nodes

        new_enabled_config = {
            "metrics": {
                "test": {
                    "number_of_people": {
                        "enabled": False,
                    },
                }
            }
        }

        update_config_file(new_enabled_config, project.project_root, "dbt_project.yml")
        with pytest.raises(CompilationError):
            run_dbt(["parse"])


# Test invalid metric configs
class TestInvalidMetric(MetricConfigTests):
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "people.sql": models_people_sql,
            "schema.yml": invalid_config_metric_yml,
        }

    def test_invalid_config_metric(self, project):
        with pytest.raises(ValidationError) as excinfo:
            run_dbt(["parse"])
        expected_msg = "'True and False' is not of type 'boolean'"
        assert expected_msg in str(excinfo.value)
