select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_4') }}
union all
select * from {{ ref('node_87') }}
union all
select * from {{ ref('node_144') }}
union all
select * from {{ ref('node_216') }}
union all
select * from {{ ref('node_898') }}
