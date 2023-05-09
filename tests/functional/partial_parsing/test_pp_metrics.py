import pytest

from dbt.contracts.graph.nodes import RefArgs
from dbt.tests.util import run_dbt, write_file, get_manifest
from tests.functional.partial_parsing.fixtures import (
    people_sql,
    people_metrics_yml,
    people_metrics2_yml,
    metric_model_a_sql,
    people_metrics3_yml,
)

from dbt.exceptions import CompilationError


class TestMetrics:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "people.sql": people_sql,
        }

    def test_metrics(self, project):
        # initial run
        results = run_dbt(["run"])
        assert len(results) == 1
        manifest = get_manifest(project.project_root)
        assert len(manifest.nodes) == 1

        # Add metrics yaml file
        write_file(people_metrics_yml, project.project_root, "models", "people_metrics.yml")
        results = run_dbt(["run"])
        assert len(results) == 1
        manifest = get_manifest(project.project_root)
        assert len(manifest.metrics) == 2
        metric_people_id = "metric.test.number_of_people"
        metric_tenure_id = "metric.test.collective_tenure"
        metric_people = manifest.metrics[metric_people_id]
        metric_tenure = manifest.metrics[metric_tenure_id]
        expected_meta = {"my_meta": "testing"}
        assert metric_people.meta == expected_meta
        assert metric_people.refs == [RefArgs(name="people")]
        assert metric_tenure.refs == [RefArgs(name="people")]
        expected_depends_on_nodes = ["model.test.people"]
        assert metric_people.depends_on.nodes == expected_depends_on_nodes

        # Change metrics yaml files
        write_file(people_metrics2_yml, project.project_root, "models", "people_metrics.yml")
        results = run_dbt(["run"])
        assert len(results) == 1
        manifest = get_manifest(project.project_root)
        metric_people = manifest.metrics[metric_people_id]
        expected_meta = {"my_meta": "replaced"}
        assert metric_people.meta == expected_meta
        expected_depends_on_nodes = ["model.test.people"]
        assert metric_people.depends_on.nodes == expected_depends_on_nodes

        # Add model referring to metric
        write_file(metric_model_a_sql, project.project_root, "models", "metric_model_a.sql")
        results = run_dbt(["run"])
        manifest = get_manifest(project.project_root)
        model_a = manifest.nodes["model.test.metric_model_a"]
        expected_depends_on_nodes = [
            "metric.test.number_of_people",
            "metric.test.collective_tenure",
        ]
        assert model_a.depends_on.nodes == expected_depends_on_nodes

        # Then delete a metric
        write_file(people_metrics3_yml, project.project_root, "models", "people_metrics.yml")
        with pytest.raises(CompilationError):
            # We use "parse" here and not "run" because we're checking that the CompilationError
            # occurs at parse time, not compilation
            results = run_dbt(["parse"])
