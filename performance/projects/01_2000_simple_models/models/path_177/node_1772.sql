select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_2') }}
union all
select * from {{ ref('node_13') }}
union all
select * from {{ ref('node_252') }}
union all
select * from {{ ref('node_301') }}
union all
select * from {{ ref('node_307') }}
union all
select * from {{ ref('node_1511') }}
