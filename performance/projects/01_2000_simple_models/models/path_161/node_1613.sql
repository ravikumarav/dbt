select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_3') }}
union all
select * from {{ ref('node_6') }}
union all
select * from {{ ref('node_7') }}
union all
select * from {{ ref('node_139') }}
union all
select * from {{ ref('node_374') }}
union all
select * from {{ ref('node_576') }}
