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
    "NXTVAL",  # Treat the supplied Unicode spelling conservatively as a write.
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
    "LO_CREATE",
    "LO_CREAT",
    "LO_FROM_BYTEA",
    "LO_PUT",
    "LO_TRUNCATE",
    "LO_TRUNCATE64",
    "LOWRITE",
    "LO_OPEN",
    "DBLINK",
    "DBLINK_SEND_QUERY",
    "DBLINK_OPEN",
    "PG_NOTIFY",
    "PG_SWITCH_WAL",
    "PG_SWITCH_XLOG",
    "PG_CREATE_RESTORE_POINT",
    "PG_CREATE_LOGICAL_REPLICATION_SLOT",
    "PG_CREATE_PHYSICAL_REPLICATION_SLOT",
    "PG_DROP_REPLICATION_SLOT",
    "PG_REPLICATION_SLOT_ADVANCE",
    "PG_LOGICAL_EMIT_MESSAGE",
    "PG_FILE_WRITE",
    "PG_FILE_RENAME",
    "PG_FILE_UNLINK",
    "PG_FILE_SYNC",
    "PG_ROTATE_LOGFILE",
    "PG_PROMOTE",
    "PG_IMPORT_SYSTEM_COLLATIONS",
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


def _identifier_char(char: str) -> bool:
    return char == "_" or char == "$" or char.isalnum()


def _quote_at(sql: str, index: int) -> tuple[str, str, str] | None:
    """Return opening delimiter, closing delimiter, and lexical mode."""
    if index >= len(sql):
        return None

    at_token_boundary = index == 0 or not _identifier_char(sql[index - 1])
    if at_token_boundary and index + 2 < len(sql):
        if sql[index:index + 2].upper() == "U&" and sql[index + 2] in "'\"":
            quote = sql[index + 2]
            mode = "unicode_identifier" if quote == '"' else "unicode_string"
            return sql[index:index + 3], quote, mode
    if (at_token_boundary and sql[index] in "Ee" and index + 1 < len(sql)
            and sql[index + 1] == "'"):
        return sql[index:index + 2], "'", "escape_string"

    char = sql[index]
    if char == "'":
        return char, char, "string"
    if char == '"':
        return char, char, "identifier"
    # Preserve the older cross-dialect quote handling for callers that use
    # this helper, while applying PostgreSQL rules to PostgreSQL quote forms.
    if char == "`":
        return char, char, "identifier"
    if char == "[":
        return "[", "]", "identifier"
    if char == "$":
        match = _DOLLAR_QUOTE.match(sql, index)
        if match:
            delimiter = match.group(0)
            return delimiter, delimiter, "dollar"
    return None


def _consume_quoted(
    sql: str, start: int, opening: str, closing: str, mode: str = "string"
) -> tuple[int, bool]:
    """Return the end offset and whether a quoted region closes correctly."""
    index = start + len(opening)
    if mode == "dollar" or opening.startswith("$"):
        end = sql.find(closing, index)
        return (len(sql), False) if end < 0 else (end + len(closing), True)

    while index < len(sql):
        if mode == "escape_string" and sql[index] == "\\":
            # In E strings a backslash quotes the next character, including a
            # quote. A final backslash leaves the string unterminated.
            index += 2
            continue
        if sql.startswith(closing, index):
            # SQL escapes a delimiter inside a quoted value by doubling it.
            if sql.startswith(closing + closing, index):
                index += len(closing) * 2
            else:
                end = index + len(closing)
                resume = _string_continuation(sql, end) if mode == "escape_string" else None
                if resume is None:
                    return end, True
                # PostgreSQL joins string constants separated by whitespace
                # containing a newline; the continuation keeps E-string escapes.
                index = resume + 1
        else:
            index += 1
    return len(sql), False


def _string_continuation(sql: str, index: int) -> int | None:
    """Return the offset of a continuing quote after whitespace with a newline."""
    newline = False
    while index < len(sql) and sql[index] in " \t\r\n\f\v":
        newline = newline or sql[index] in "\r\n"
        index += 1
    return index if newline and index < len(sql) and sql[index] == "'" else None


def _quoted_value(sql: str, start: int, end: int, opening: str, closing: str) -> str:
    """Return a quoted value with doubled delimiters reduced to one."""
    return sql[start + len(opening):end - len(closing)].replace(closing * 2, closing)


def _decode_unicode_value(value: str, escape: str) -> str | None:
    """Decode PostgreSQL's four- and six-hex-digit Unicode escapes."""
    codepoints: list[int] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != escape:
            codepoint = ord(char)
            if codepoint == 0 or 0xD800 <= codepoint <= 0xDFFF:
                return None
            codepoints.append(codepoint)
            index += 1
            continue

        if index + 1 >= len(value):
            return None
        if value[index + 1] == escape:
            codepoints.append(ord(escape))
            index += 2
            continue

        if value[index + 1] == "+":
            digits_start = index + 2
            digits_end = digits_start + 6
        else:
            digits_start = index + 1
            digits_end = digits_start + 4
        digits = value[digits_start:digits_end]
        if (len(digits) != digits_end - digits_start
                or any(char not in "0123456789abcdefABCDEF" for char in digits)):
            return None
        codepoint = int(digits, 16)
        if codepoint == 0 or codepoint > 0x10FFFF:
            return None
        codepoints.append(codepoint)
        index = digits_end

    decoded: list[str] = []
    index = 0
    while index < len(codepoints):
        codepoint = codepoints[index]
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(codepoints) or not 0xDC00 <= codepoints[index + 1] <= 0xDFFF:
                return None
            low = codepoints[index + 1]
            codepoint = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00)
            index += 1
        elif 0xDC00 <= codepoint <= 0xDFFF:
            return None
        decoded.append(chr(codepoint))
        index += 1
    return "".join(decoded)


def _unicode_escape_clause(sql: str, after_value: int) -> tuple[str, int, bool]:
    """Read an optional UESCAPE clause and return its character and end."""
    index = after_value
    while index < len(sql) and sql[index].isspace():
        index += 1
    keyword_end = index + len("UESCAPE")
    if (sql[index:keyword_end].upper() != "UESCAPE"
            or (keyword_end < len(sql) and _identifier_char(sql[keyword_end]))):
        return "\\", after_value, True

    index = keyword_end
    while index < len(sql) and sql[index].isspace():
        index += 1
    if index >= len(sql) or sql[index] != "'":
        return "\\", len(sql), False
    end, closed = _consume_quoted(sql, index, "'", "'", "string")
    if not closed:
        return "\\", end, False
    value = _quoted_value(sql, index, end, "'", "'")
    if len(value) != 1:
        return "\\", end, False
    escape = value
    if (escape.isspace() or escape in "+'\""
            or escape in "0123456789abcdefABCDEF"
            or 0xD800 <= ord(escape) <= 0xDFFF):
        return "\\", end, False
    return escape, end, True


def _unicode_token(
    sql: str, start: int, opening: str, closing: str, mode: str
) -> tuple[int, str | None, bool]:
    """Decode one U& identifier/string, including its optional UESCAPE clause."""
    value_end, closed = _consume_quoted(sql, start, opening, closing, mode)
    if not closed:
        return value_end, None, False
    escape, token_end, escape_valid = _unicode_escape_clause(sql, value_end)
    value = _quoted_value(sql, start, value_end, opening, closing)
    decoded = _decode_unicode_value(value, escape) if escape_valid else None
    return token_end, decoded, escape_valid and decoded is not None


def _validate_unicode_tokens(sql: str) -> bool:
    """Reject Unicode escape tokens that PostgreSQL cannot decode."""
    index = 0
    while index < len(sql):
        quote = _quote_at(sql, index)
        if quote:
            opening, closing, mode = quote
            if mode.startswith("unicode_"):
                end, _decoded, valid = _unicode_token(sql, index, opening, closing, mode)
                if not valid:
                    return False
                index = end
                continue
            end, closed = _consume_quoted(sql, index, opening, closing, mode)
            if not closed:
                return False
            index = end
            continue
        index += 1
    return True


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

    cleaned = "".join(output)
    return cleaned, valid and _validate_unicode_tokens(cleaned)


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


def _identifier_at(sql: str, index: int) -> tuple[str, int] | None:
    """Return a normalized identifier value and its end offset, if present."""
    if index >= len(sql):
        return None

    quote = _quote_at(sql, index)
    if quote and quote[2] == "unicode_identifier":
        end, decoded, valid = _unicode_token(sql, index, *quote)
        if not valid or decoded is None:
            return None
        return decoded.upper(), end

    if quote and quote[2] == "identifier" and quote[0] == '"':
        end, closed = _consume_quoted(sql, index, *quote)
        if not closed:
            return None
        return _quoted_value(sql, index, end, quote[0], quote[1]).upper(), end

    char = sql[index]
    if char != "_" and not char.isalpha() and char != "$":
        return None

    end = index + 1
    while end < len(sql):
        next_char = sql[end]
        if next_char == "_" or next_char == "$" or next_char.isalnum():
            end += 1
        else:
            break
    return sql[index:end].upper(), end


def _is_side_effecting_function(name: str) -> bool:
    return name in _SIDE_EFFECT_FUNCTIONS or name.startswith("PG_STAT_RESET")


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
        if quote and quote[2] not in {"identifier", "unicode_identifier"}:
            end, _ = _consume_quoted(sql, index, *quote)
            index = end
            continue

        identifier = _identifier_at(sql, index)
        if identifier:
            name, end = identifier
            next_index = end
            while next_index < len(sql) and sql[next_index].isspace():
                next_index += 1

            # The final identifier in a dotted name is the function name;
            # preceding identifiers may be a schema or catalog qualifier.
            while next_index < len(sql) and sql[next_index] == ".":
                part_index = next_index + 1
                while part_index < len(sql) and sql[part_index].isspace():
                    part_index += 1
                part = _identifier_at(sql, part_index)
                if not part:
                    break
                name, next_index = part
                while next_index < len(sql) and sql[next_index].isspace():
                    next_index += 1

            if (next_index < len(sql) and sql[next_index] == "("
                    and _is_side_effecting_function(name)):
                return True
            index = end
            continue

        quote = _quote_at(sql, index)
        if quote:
            end, _ = _consume_quoted(sql, index, *quote)
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
