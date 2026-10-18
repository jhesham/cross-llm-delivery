"""v0.5 Task 3: fail-closed SQL read/write classifier and statement hash."""
import pytest

from tests.evidence._lazy import resolve

M = "cld.evidence_mode.sqlclass"


def classify(sql):
    return resolve(M, "classify_sql")(sql)


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "-- leading comment\n/* block */\nSELECT a FROM orders",
    "SELECT 1; SELECT 2;",
    "WITH a AS (SELECT 1 AS x) SELECT x FROM a",
    "SHOW TABLES", "DESCRIBE orders", "EXPLAIN SELECT 1",
    "SELECT 'insert' AS note, \"delete\" AS other",
])
def test_reads(sql):
    assert classify(sql) == "read"


@pytest.mark.parametrize("sql", [
    "-- note\nWITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a",
    "CREATE TABLE t AS SELECT 1",
    "INSERT INTO t VALUES (1)", "UPDATE t SET a = 1", "DELETE FROM t WHERE 1=1",
    "MERGE t USING s ON t.id = s.id WHEN MATCHED THEN DELETE",
    "DROP TABLE t", "ALTER TABLE t ADD COLUMN c INT64", "TRUNCATE TABLE t",
    "DECLARE x INT64 DEFAULT 1; SELECT x",
    "SELECT 1; INSERT INTO t VALUES (1)",
    "SELECT 'unbalanced",
    "", "   ", "-- only a comment",
])
def test_writes_fail_closed(sql):
    assert classify(sql) == "write"


def test_cte_then_insert_is_write():
    assert classify("-- note\nWITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a") == "write"


def test_hash_ignores_comments_and_whitespace():
    h = resolve(M, "statement_hash")
    assert h("SELECT  a\nFROM t -- x") == h("/* c */ SELECT a FROM t")
    assert h("SELECT a FROM t") != h("SELECT b FROM t")
    assert len(h("SELECT 1")) == 64
