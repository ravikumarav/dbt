select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_24') }}
union all
select * from {{ ref('node_49') }}
union all
select * from {{ ref('node_209') }}
union all
select * from {{ ref('node_737') }}
union all
select * from {{ ref('node_1276') }}
