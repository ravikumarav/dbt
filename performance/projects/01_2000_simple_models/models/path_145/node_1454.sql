select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_3') }}
union all
select * from {{ ref('node_6') }}
union all
select * from {{ ref('node_263') }}
union all
select * from {{ ref('node_270') }}
union all
select * from {{ ref('node_890') }}
union all
select * from {{ ref('node_1188') }}
union all
select * from {{ ref('node_1415') }}
