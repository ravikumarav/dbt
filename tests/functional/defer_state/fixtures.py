seed_csv = """id,name
1,Alice
2,Bob
"""

table_model_sql = """
{{ config(materialized='table') }}
select * from {{ ref('ephemeral_model') }}

-- establish a macro dependency to trigger state:modified.macros
-- depends on: {{ my_macro() }}
"""

changed_table_model_sql = """
{{ config(materialized='table') }}
select 1 as fun
"""

view_model_sql = """
select * from {{ ref('seed') }}

-- establish a macro dependency that trips infinite recursion if not handled
-- depends on: {{ my_infinitely_recursive_macro() }}
"""

changed_view_model_sql = """
select * from no.such.table
"""

ephemeral_model_sql = """
{{ config(materialized='ephemeral') }}
select * from {{ ref('view_model') }}
"""

changed_ephemeral_model_sql = """
{{ config(materialized='ephemeral') }}
select * from no.such.table
"""

schema_yml = """
version: 2
models:
  - name: view_model
    columns:
      - name: id
        tests:
          - unique:
              severity: error
          - not_null
      - name: name
"""

contract_schema_yml = """
version: 2
models:
  - name: view_model
    columns:
      - name: id
        tests:
          - unique:
              severity: error
          - not_null
      - name: name
  - name: table_model
    config:
      contract:
        enforced: True
    columns:
      - name: id
        data_type: integer
        tests:
          - unique:
              severity: error
          - not_null
      - name: name
        data_type: text
"""

modified_contract_schema_yml = """
version: 2
models:
  - name: view_model
    columns:
      - name: id
        tests:
          - unique:
              severity: error
          - not_null
      - name: name
  - name: table_model
    config:
      contract:
        enforced: True
    columns:
      - name: id
        data_type: integer
        tests:
          - unique:
              severity: error
          - not_null
      - name: user_name
        data_type: text
"""

disabled_contract_schema_yml = """
version: 2
models:
  - name: view_model
    columns:
      - name: id
        tests:
          - unique:
              severity: error
          - not_null
      - name: name
  - name: table_model
    columns:
      - name: id
        data_type: integer
        tests:
          - unique:
              severity: error
          - not_null
      - name: name
        data_type: text
"""

exposures_yml = """
version: 2
exposures:
  - name: my_exposure
    type: application
    depends_on:
      - ref('view_model')
    owner:
      email: test@example.com
"""

macros_sql = """
{% macro my_macro() %}
    {% do log('in a macro' ) %}
{% endmacro %}
"""

infinite_macros_sql = """
{# trigger infinite recursion if not handled #}

{% macro my_infinitely_recursive_macro() %}
  {{ return(adapter.dispatch('my_infinitely_recursive_macro')()) }}
{% endmacro %}

{% macro default__my_infinitely_recursive_macro() %}
    {% if unmet_condition %}
        {{ my_infinitely_recursive_macro() }}
    {% else %}
        {{ return('') }}
    {% endif %}
{% endmacro %}
"""

snapshot_sql = """
{% snapshot my_cool_snapshot %}

    {{
        config(
            target_database=database,
            target_schema=schema,
            unique_key='id',
            strategy='check',
            check_cols=['id'],
        )
    }}
    select * from {{ ref('view_model') }}

{% endsnapshot %}
"""
