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
select * from {{ ref('node_15') }}
union all
select * from {{ ref('node_259') }}
union all
select * from {{ ref('node_325') }}
union all
select * from {{ ref('node_416') }}
