"""v0.5 second review (SQLCLASS): side-effect functions match however they are spelled."""
import pytest

from tests.evidence._lazy import resolve


@pytest.mark.parametrize("sql", [
    "SELECT \"nextval\"('orders_id_seq')",
    "SELECT pg_catalog.\"setval\"('orders_id_seq', 1000)",
    "SELECT pg_catalog.nextval('orders_id_seq')",
    "SELECT nextval ('orders_id_seq')",
    "SELECT lo_create(0)",
    "SELECT lo_from_bytea(0, 'x')",
    "SELECT lo_put(1, 0, 'x')",
    "SELECT lowrite(0, 'x')",
    "SELECT lo_truncate(0, 0)",
    "SELECT dblink('db', 'DELETE FROM t')",
    "SELECT pg_notify('channel', 'x')",
    "SELECT pg_switch_wal()",
    "SELECT pg_create_logical_replication_slot('s', 'p')",
    "SELECT pg_drop_replication_slot('s')",
    "SELECT pg_logical_emit_message(true, 'p', 'x')",
    "SELECT pg_file_write('f', 'x', false)",
    "SELECT pg_stat_reset()",
    "SELECT pg_rotate_logfile()",
])
def test_spelled_or_qualified_side_effects_are_writes(sql):
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")(sql) == "write"


@pytest.mark.parametrize("sql", [
    "SELECT t.\"nextval\" FROM t",
    "SELECT 'nextval(1)' AS label",
    "SELECT nextval_count FROM t",
    "SELECT currval('orders_id_seq')",
    "SELECT count(*) FROM t -- nextval('s')",
    "SELECT date_trunc('day', ts), coalesce(a, 0) FROM t",
])
def test_lookalikes_stay_reads(sql):
    assert resolve("cld.evidence_mode.sqlclass", "classify_sql")(sql) == "read"
