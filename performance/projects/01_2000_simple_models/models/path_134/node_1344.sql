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
select * from {{ ref('node_32') }}
union all
select * from {{ ref('node_37') }}
union all
select * from {{ ref('node_284') }}
union all
select * from {{ ref('node_298') }}
union all
select * from {{ ref('node_506') }}
union all
select * from {{ ref('node_631') }}
union all
select * from {{ ref('node_1129') }}
union all
select * from {{ ref('node_1227') }}
