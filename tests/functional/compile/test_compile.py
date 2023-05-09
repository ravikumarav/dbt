import json
import pathlib
import pytest

from dbt.cli.main import dbtRunner
from dbt.exceptions import DbtRuntimeError, TargetNotFoundError
from dbt.tests.util import run_dbt, run_dbt_and_capture
from tests.functional.compile.fixtures import (
    first_model_sql,
    second_model_sql,
    first_ephemeral_model_sql,
    second_ephemeral_model_sql,
    third_ephemeral_model_sql,
    schema_yml,
    model_multiline_jinja,
)


def get_lines(model_name):
    from dbt.tests.util import read_file

    f = read_file("target", "compiled", "test", "models", model_name + ".sql")
    return [line for line in f.splitlines() if line]


def file_exists(model_name):
    from dbt.tests.util import file_exists

    return file_exists("target", "compiled", "test", "models", model_name + ".sql")


class TestIntrospectFlag:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "first_model.sql": first_model_sql,
            "second_model.sql": second_model_sql,
            "schema.yml": schema_yml,
        }

    def test_default(self, project):
        run_dbt(["compile"])
        assert get_lines("first_model") == ["select 1 as fun"]
        assert any("_test_compile as schema" in line for line in get_lines("second_model"))

    @pytest.mark.skip("Investigate flaky test #7179")
    def test_no_introspect(self, project):
        with pytest.raises(DbtRuntimeError):
            run_dbt(["compile", "--no-introspect"])


class TestEphemeralModels:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "first_ephemeral_model.sql": first_ephemeral_model_sql,
            "second_ephemeral_model.sql": second_ephemeral_model_sql,
            "third_ephemeral_model.sql": third_ephemeral_model_sql,
        }

    def test_first_selector(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--select", "first_ephemeral_model"]
        )
        assert file_exists("first_ephemeral_model")
        assert not file_exists("second_ephemeral_model")
        assert not file_exists("third_ephemeral_model")
        assert "Compiled node 'first_ephemeral_model' is" in log_output

    def test_middle_selector(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--select", "second_ephemeral_model"]
        )
        assert file_exists("first_ephemeral_model")
        assert file_exists("second_ephemeral_model")
        assert not file_exists("third_ephemeral_model")
        assert "Compiled node 'second_ephemeral_model' is" in log_output

    def test_last_selector(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--select", "third_ephemeral_model"]
        )
        assert file_exists("first_ephemeral_model")
        assert file_exists("second_ephemeral_model")
        assert file_exists("third_ephemeral_model")
        assert "Compiled node 'third_ephemeral_model' is" in log_output

    def test_no_selector(self, project):
        run_dbt(["compile"])

        assert get_lines("first_ephemeral_model") == ["select 1 as fun"]
        assert get_lines("second_ephemeral_model") == [
            "with __dbt__cte__first_ephemeral_model as (",
            "select 1 as fun",
            ")select * from __dbt__cte__first_ephemeral_model",
        ]
        assert get_lines("third_ephemeral_model") == [
            "with __dbt__cte__first_ephemeral_model as (",
            "select 1 as fun",
            "),  __dbt__cte__second_ephemeral_model as (",
            "select * from __dbt__cte__first_ephemeral_model",
            ")select * from __dbt__cte__second_ephemeral_model",
            "union all",
            "select 2 as fun",
        ]


class TestCompile:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "first_model.sql": first_model_sql,
            "second_model.sql": second_model_sql,
            "schema.yml": schema_yml,
        }

    def test_none(self, project):
        (results, log_output) = run_dbt_and_capture(["compile"])
        assert len(results) == 4
        assert "Compiled node" not in log_output

    def test_inline_pass(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--inline", "select * from {{ ref('first_model') }}"]
        )
        assert len(results) == 1
        assert "Compiled inline node is:" in log_output

    def test_select_pass(self, project):
        (results, log_output) = run_dbt_and_capture(["compile", "--select", "second_model"])
        assert len(results) == 3
        assert "Compiled node 'second_model' is:" in log_output

    def test_select_pass_empty(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--indirect-selection", "empty", "--select", "second_model"]
        )
        assert len(results) == 1
        assert "Compiled node 'second_model' is:" in log_output

    def test_inline_fail(self, project):
        with pytest.raises(
            TargetNotFoundError, match="depends on a node named 'third_model' which was not found"
        ):
            run_dbt(["compile", "--inline", "select * from {{ ref('third_model') }}"])

    def test_multiline_jinja(self, project):
        (results, log_output) = run_dbt_and_capture(["compile", "--inline", model_multiline_jinja])
        assert len(results) == 1
        assert "Compiled inline node is:" in log_output

    def test_output_json_select(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--select", "second_model", "--output", "json"]
        )
        assert len(results) == 3
        assert "node" in log_output
        assert "compiled" in log_output

    def test_output_json_inline(self, project):
        (results, log_output) = run_dbt_and_capture(
            ["compile", "--inline", "select * from {{ ref('second_model') }}", "--output", "json"]
        )
        assert len(results) == 1
        assert '"node"' not in log_output
        assert '"compiled"' in log_output

    def test_compile_inline_not_add_node(self, project):
        dbt = dbtRunner()
        parse_result = dbt.invoke(["parse"])
        manifest = parse_result.result
        assert len(manifest.nodes) == 4
        dbt = dbtRunner(manifest=manifest)
        dbt.invoke(
            ["compile", "--inline", "select * from {{ ref('second_model') }}"],
            populate_cache=False,
        )
        assert len(manifest.nodes) == 4

    def test_graph_summary_output(self, project):
        """Ensure that the compile command generates a file named graph_summary.json
        in the target directory, that the file contains valid json, and that the
        json has the high level structure it should."""
        dbtRunner().invoke(["compile"])
        summary_path = pathlib.Path(project.project_root, "target/graph_summary.json")
        with open(summary_path, "r") as summary_file:
            summary = json.load(summary_file)
            assert "_invocation_id" in summary
            assert "linked" in summary
