select 1 as id
union all
select * from {{ ref('node_0') }}
union all
select * from {{ ref('node_2') }}
union all
select * from {{ ref('node_13') }}
union all
select * from {{ ref('node_66') }}
union all
select * from {{ ref('node_79') }}
union all
select * from {{ ref('node_269') }}
union all
select * from {{ ref('node_304') }}
union all
select * from {{ ref('node_415') }}
union all
select * from {{ ref('node_1465') }}
