select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_3') }}
union all
select * from {{ ref('node_6') }}
union all
select * from {{ ref('node_8') }}
union all
select * from {{ ref('node_17') }}
union all
select * from {{ ref('node_85') }}
union all
select * from {{ ref('node_156') }}
union all
select * from {{ ref('node_164') }}
union all
select * from {{ ref('node_1078') }}
union all
select * from {{ ref('node_1145') }}
