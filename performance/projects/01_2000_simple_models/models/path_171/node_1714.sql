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
select * from {{ ref('node_10') }}
union all
select * from {{ ref('node_84') }}
union all
select * from {{ ref('node_527') }}
union all
select * from {{ ref('node_1134') }}
union all
select * from {{ ref('node_1411') }}
