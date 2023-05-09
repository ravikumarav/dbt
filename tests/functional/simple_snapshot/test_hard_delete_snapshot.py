import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import time

import pytz
import pytest
from dbt.tests.util import run_dbt, check_relations_equal
from tests.functional.simple_snapshot.fixtures import (
    models__schema_yml,
    models__ref_snapshot_sql,
    macros__test_no_overlaps_sql,
    snapshots_pg__snapshot_sql,
)


# These tests uses the same seed data, containing 20 records of which we hard delete the last 10.
# These deleted records set the dbt_valid_to to time the snapshot was ran.

# Using replace on a timestamp won't account for hour differences unless given the local timezone.
# We can force python as utc but not postgres fields which need to be handled as local timestamps.
def currenttz():
    if time.daylight:
        return timezone(timedelta(seconds=-time.altzone), time.tzname[1])
    else:
        return timezone(timedelta(seconds=-time.timezone), time.tzname[0])


def datetime_snapshot():
    NUM_SNAPSHOT_MODELS = 1
    begin_snapshot_datetime = datetime.now(pytz.UTC)
    results = run_dbt(["snapshot", "--vars", "{invalidate_hard_deletes: true}"])
    assert len(results) == NUM_SNAPSHOT_MODELS

    return begin_snapshot_datetime


@pytest.fixture(scope="class", autouse=True)
def setUp(project):
    path = os.path.join(project.test_data_dir, "seed_pg.sql")
    project.run_sql_file(path)


@pytest.fixture(scope="class")
def snapshots():
    return {"snapshot.sql": snapshots_pg__snapshot_sql}


@pytest.fixture(scope="class")
def models():
    return {
        "schema.yml": models__schema_yml,
        "ref_snapshot.sql": models__ref_snapshot_sql,
    }


@pytest.fixture(scope="class")
def macros():
    return {"test_no_overlaps.sql": macros__test_no_overlaps_sql}


def test_snapshot_hard_delete(project):
    # run the first snapshot
    datetime_snapshot()

    check_relations_equal(project.adapter, ["snapshot_expected", "snapshot_actual"])

    invalidated_snapshot_datetime = None
    revived_snapshot_datetime = None

    # hard delete last 10 records
    project.run_sql(
        "delete from {}.{}.seed where id >= 10;".format(project.database, project.test_schema)
    )

    # snapshot and assert invalidated
    invalidated_snapshot_datetime = datetime_snapshot()

    snapshotted = project.run_sql(
        """
        select
            id,
            dbt_valid_to
        from {}.{}.snapshot_actual
        order by id
        """.format(
            project.database, project.test_schema
        ),
        fetch="all",
    )

    assert len(snapshotted) == 20
    for result in snapshotted[10:]:
        # result is a tuple, the dbt_valid_to column is the latest
        assert isinstance(result[-1], datetime)
        assert result[-1].replace(tzinfo=currenttz()) >= invalidated_snapshot_datetime

    # revive records
    # Timestamp must have microseconds for tests below to be meaningful
    revival_timestamp = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    project.run_sql(
        """
        insert into {}.{}.seed (id, first_name, last_name, email, gender, ip_address, updated_at) values
        (10, 'Rachel', 'Lopez', 'rlopez9@themeforest.net', 'Female', '237.165.82.71', '{}'),
        (11, 'Donna', 'Welch', 'dwelcha@shutterfly.com', 'Female', '103.33.110.138', '{}')
        """.format(
            project.database, project.test_schema, revival_timestamp, revival_timestamp
        )
    )

    # snapshot and assert records were revived
    # Note: the revived_snapshot_datetime here is later than the revival_timestamp above
    revived_snapshot_datetime = datetime_snapshot()

    # records which weren't revived (id != 10, 11)
    # dbt_valid_to is not null
    invalidated_records = project.run_sql(
        """
        select
            id,
            dbt_valid_to
        from {}.{}.snapshot_actual
        where dbt_valid_to is not null
        order by id
        """.format(
            project.database, project.test_schema
        ),
        fetch="all",
    )

    assert len(invalidated_records) == 11
    for result in invalidated_records:
        # result is a tuple, the dbt_valid_to column is the latest
        assert isinstance(result[1], datetime)
        assert result[1].replace(tzinfo=currenttz()) >= invalidated_snapshot_datetime

    # records which were revived (id = 10, 11)
    # dbt_valid_to is null
    revived_records = project.run_sql(
        """
        select
            id,
            dbt_valid_from,
            dbt_valid_to
        from {}.{}.snapshot_actual
        where dbt_valid_to is null
        and id IN (10, 11)
        """.format(
            project.database, project.test_schema
        ),
        fetch="all",
    )

    assert len(revived_records) == 2
    for result in revived_records:
        # result is a tuple, the dbt_valid_from is second and dbt_valid_to is latest
        # dbt_valid_from is the same as the 'updated_at' added in the revived_rows
        # dbt_valid_to is null
        assert isinstance(result[1], datetime)
        assert result[1].replace(tzinfo=pytz.UTC) <= revived_snapshot_datetime
        assert result[2] is None
