select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_3') }}
union all
select * from {{ ref('node_421') }}
union all
select * from {{ ref('node_1076') }}
union all
select * from {{ ref('node_1319') }}
