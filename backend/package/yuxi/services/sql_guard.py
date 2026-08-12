"""基于 SQL AST 的只读查询安全校验。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp, parse

READ_ONLY_ROOT = (exp.Select,)
FORBIDDEN_NODES = (
    exp.Alter,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.Transaction,
    exp.TruncateTable,
    exp.Update,
)
FORBIDDEN_FUNCTIONS = {
    "BENCHMARK",
    "COPY",
    "DBLINK",
    "DBLINK_EXEC",
    "GET_LOCK",
    "LOAD_DATA",
    "LOAD_FILE",
    "LO_IMPORT",
    "LASTVAL",
    "NEXTVAL",
    "PG_ADVISORY_LOCK",
    "PG_ADVISORY_UNLOCK",
    "PG_CANCEL_BACKEND",
    "PG_TERMINATE_BACKEND",
    "PG_READ_BINARY_FILE",
    "PG_READ_FILE",
    "PG_SLEEP",
    "PG_RELOAD_CONF",
    "RELEASE_LOCK",
    "SET_CONFIG",
    "SETVAL",
    "SLEEP",
    "XP_CMDSHELL",
}
FORBIDDEN_KEYS = {"for", "lock", "locks", "pragma", "set", "use"}


@dataclass(frozen=True)
class SQLValidationResult:
    """SQL AST 校验后的规范 SQL 和表引用。"""

    sql: str
    tables: tuple[str, ...]


def _normalize_table_name(table: exp.Table) -> str:
    name = table.name.strip().lower()
    database = (table.db or "").strip().lower()
    return f"{database}.{name}" if database else name


def _cte_names(statement: exp.Expression) -> set[str]:
    with_clause = statement.args.get("with")
    if not with_clause:
        return set()
    return {cte.alias_or_name.strip().lower() for cte in with_clause.find_all(exp.CTE) if cte.alias_or_name}


def validate_read_only_sql(sql: str, *, dialect: str, allowed_tables: set[str]) -> SQLValidationResult:
    """拒绝多语句、写操作、危险函数和白名单之外的表。"""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL 不能为空")
    try:
        parsed = parse(sql, read=dialect)
    except Exception as exc:
        raise ValueError("SQL 语法无效") from exc
    if len(parsed) != 1:
        raise ValueError("只允许执行单条 SQL")
    statement = parsed[0]
    if not isinstance(statement, READ_ONLY_ROOT):
        raise ValueError("只允许执行 SELECT 或包含 CTE 的 SELECT")
    if statement.args.get("into") is not None:
        raise ValueError("SELECT INTO 不允许执行")

    for node in statement.walk():
        if node.key in FORBIDDEN_KEYS:
            raise ValueError(f"SQL 包含禁止的操作: {node.key}")
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f"SQL 包含禁止的操作: {node.key}")
        if isinstance(node, exp.Func):
            try:
                function_name = (getattr(node, "name", None) or node.sql_name()).upper()
            except Exception:
                function_name = ""
            if function_name in FORBIDDEN_FUNCTIONS:
                raise ValueError(f"SQL 包含危险函数: {function_name}")

    allowlist = {str(item).strip().lower() for item in allowed_tables if str(item).strip()}
    cte_names = _cte_names(statement)
    tables = []
    for table in statement.find_all(exp.Table):
        if table.catalog:
            raise ValueError("不允许跨数据库引用表")
        normalized = _normalize_table_name(table)
        if normalized in cte_names:
            continue
        short_name = table.name.strip().lower()
        if normalized not in allowlist and short_name not in allowlist:
            raise ValueError(f"查询表不在白名单中: {normalized}")
        tables.append(normalized)

    return SQLValidationResult(sql=statement.sql(dialect=dialect), tables=tuple(dict.fromkeys(tables)))
