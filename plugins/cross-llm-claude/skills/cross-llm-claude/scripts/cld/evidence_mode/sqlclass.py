"""Fail-closed SQL classification helpers for evidence mode."""

from hashlib import sha256
import re


_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")

_READ_STARTS = {"SELECT", "WITH", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
_WRITE_WORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "CREATE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXPORT",
    "LOAD",
    "COPY",
    "INTO",  # SELECT ... INTO creates a table (Postgres, SQL Server)
}

_SIDE_EFFECT_FUNCTIONS = {
    "NEXTVAL",
    "SETVAL",
    "PG_ADVISORY_LOCK",
    "PG_ADVISORY_XACT_LOCK",
    "PG_ADVISORY_LOCK_SHARED",
    "PG_ADVISORY_XACT_LOCK_SHARED",
    "PG_TRY_ADVISORY_LOCK",
    "PG_TRY_ADVISORY_XACT_LOCK",
    "PG_TRY_ADVISORY_LOCK_SHARED",
    "PG_TRY_ADVISORY_XACT_LOCK_SHARED",
    "LO_IMPORT",
    "LO_EXPORT",
    "LO_UNLINK",
    "DBLINK_EXEC",
    "DBLINK_CONNECT",
    "PG_TERMINATE_BACKEND",
    "PG_CANCEL_BACKEND",
    "PG_RELOAD_CONF",
    "SET_CONFIG",
}
_ROW_LOCK_CLAUSES = {
    ("FOR", "UPDATE"),
    ("FOR", "NO", "KEY", "UPDATE"),
    ("FOR", "SHARE"),
    ("FOR", "KEY", "SHARE"),
}


def _quote_at(sql: str, index: int) -> tuple[str, str] | None:
    """Return an opening and closing delimiter at *index*, if present."""
    char = sql[index]
    if char in "'\"`":
        return char, char
    if char == "[":
        return "[", "]"
    if char == "$":
        match = _DOLLAR_QUOTE.match(sql, index)
        if match:
            delimiter = match.group(0)
            return delimiter, delimiter
    return None


def _consume_quoted(
    sql: str, start: int, opening: str, closing: str
) -> tuple[int, bool]:
    """Return the end offset and whether a quoted region closes correctly."""
    index = start + len(opening)
    if opening.startswith("$"):
        end = sql.find(closing, index)
        return (len(sql), False) if end < 0 else (end + len(closing), True)

    while index < len(sql):
        if sql.startswith(closing, index):
            # SQL escapes a delimiter inside a quoted value by doubling it.
            if sql.startswith(closing + closing, index):
                index += len(closing) * 2
            else:
                return index + len(closing), True
        else:
            index += 1
    return len(sql), False


def _strip_comments(sql: str) -> tuple[str, bool]:
    """Remove SQL comments outside quoted regions and report lexical validity."""
    if not isinstance(sql, str):
        return "", False

    output: list[str] = []
    index = 0
    valid = True
    while index < len(sql):
        if sql.startswith("--", index):
            # A space keeps adjacent SQL tokens from joining after removal.
            output.append(" ")
            index += 2
            while index < len(sql) and sql[index] not in "\r\n":
                index += 1
            continue

        if sql.startswith("/*", index):
            output.append(" ")
            index += 2
            depth = 1
            while index < len(sql) and depth:
                if sql.startswith("/*", index):
                    depth += 1
                    index += 2
                elif sql.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                valid = False
            continue

        quote = _quote_at(sql, index)
        if quote:
            end, closed = _consume_quoted(sql, index, *quote)
            output.append(sql[index:end])
            valid = valid and closed
            index = end
            if not closed:
                break
            continue

        output.append(sql[index])
        index += 1

    return "".join(output), valid


def _split_statements(sql: str) -> list[str]:
    """Split on semicolons outside quoted regions."""
    statements: list[str] = []
    start = 0
    index = 0
    while index < len(sql):
        quote = _quote_at(sql, index)
        if quote:
            end, closed = _consume_quoted(sql, index, *quote)
            if not closed:
                return []
            index = end
            continue
        if sql[index] == ";":
            statements.append(sql[start:index])
            start = index + 1
        index += 1

    statements.append(sql[start:])
    # A single final terminator is normal SQL syntax. Extra terminators still
    # leave an empty statement and therefore fail closed.
    if len(statements) > 1 and not statements[-1].strip():
        statements.pop()
    return statements


def _code_words(sql: str):
    """Yield unquoted identifier-like words in a statement."""
    index = 0
    while index < len(sql):
        quote = _quote_at(sql, index)
        if quote:
            end, _ = _consume_quoted(sql, index, *quote)
            index = end
            continue

        char = sql[index]
        if char == "_" or char.isalpha() or char == "$":
            end = index + 1
            while end < len(sql):
                next_char = sql[end]
                if next_char == "_" or next_char == "$" or next_char.isalnum():
                    end += 1
                else:
                    break
            yield sql[index:end].upper()
            index = end
            continue

        index += 1


def _has_side_effecting_select_tokens(sql: str) -> bool:
    """Check for side-effect calls and row locks outside quoted regions."""
    words = list(_code_words(sql))
    for clause in _ROW_LOCK_CLAUSES:
        width = len(clause)
        if any(tuple(words[index:index + width]) == clause
               for index in range(len(words) - width + 1)):
            return True

    index = 0
    while index < len(sql):
        quote = _quote_at(sql, index)
        if quote:
            end, _ = _consume_quoted(sql, index, *quote)
            index = end
            continue

        char = sql[index]
        if char == "_" or char.isalpha() or char == "$":
            end = index + 1
            while end < len(sql):
                next_char = sql[end]
                if next_char == "_" or next_char == "$" or next_char.isalnum():
                    end += 1
                else:
                    break
            word = sql[index:end].upper()
            if word in _SIDE_EFFECT_FUNCTIONS:
                next_index = end
                while next_index < len(sql) and sql[next_index].isspace():
                    next_index += 1
                if next_index < len(sql) and sql[next_index] == "(":
                    return True
            index = end
            continue

        index += 1

    return False


def _first_word(sql: str) -> str | None:
    """Return the leading SQL word, treating Unicode letters as identifier text."""
    sql = sql.lstrip()
    if not sql or not (sql[0] == "_" or sql[0].isalpha()):
        return None

    end = 1
    while end < len(sql):
        char = sql[end]
        if char == "_" or char == "$" or char.isalnum():
            end += 1
        else:
            break
    return sql[:end].upper()


def classify_sql(sql: str) -> str:
    """Classify SQL as ``read`` only when every statement passes the allowlist."""
    cleaned, valid = _strip_comments(sql)
    if not valid:
        return "write"

    statements = _split_statements(cleaned)
    if not statements:
        return "write"

    for statement in statements:
        if not statement.strip():
            return "write"
        if _first_word(statement) not in _READ_STARTS:
            return "write"
        if any(word in _WRITE_WORDS for word in _code_words(statement)):
            return "write"
        if _has_side_effecting_select_tokens(statement):
            return "write"

    return "read"


def _collapse_whitespace(sql: str) -> str:
    """Collapse SQL formatting whitespace while preserving quoted contents."""
    output: list[str] = []
    pending_space = False
    index = 0
    while index < len(sql):
        quote = _quote_at(sql, index)
        if quote:
            if pending_space and output:
                output.append(" ")
            pending_space = False
            end, _ = _consume_quoted(sql, index, *quote)
            output.append(sql[index:end])
            index = end
            continue

        char = sql[index]
        if char.isspace():
            pending_space = True
        else:
            if pending_space and output:
                output.append(" ")
            pending_space = False
            output.append(char)
        index += 1

    return "".join(output)


def statement_hash(sql: str) -> str:
    """Hash comment-stripped SQL with formatting whitespace collapsed."""
    if not isinstance(sql, str):
        raise TypeError("sql must be a string")
    cleaned, _ = _strip_comments(sql)
    normalized = _collapse_whitespace(cleaned)
    return sha256(normalized.encode("utf-8")).hexdigest()
