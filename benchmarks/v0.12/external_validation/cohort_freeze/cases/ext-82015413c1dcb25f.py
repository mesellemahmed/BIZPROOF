def find_import_violations(
    file_path: Path,
    *,
    is_violating_module: Callable[[str], bool],
    nocheck_code: str,
    check_plain_imports: bool = False,
) -> list[tuple[int, str]]:
    """
    Walk imports in ``file_path`` and return ``(lineno, statement)`` for each
    that matches ``is_violating_module`` and is not suppressed by a
    ``# noqa: <nocheck_code>`` comment.

    :param check_plain_imports: also check ``import x`` statements (in addition
        to ``from x import y``).
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    source_lines = source.splitlines()
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            if is_violating_module(node.module):
                violating_names = [alias.name for alias in node.names]
            else:
                # Catch ``from airflow import settings`` style imports where the
                # offending module is the dotted ``<module>.<name>`` path.
                violating_names = [
                    alias.name for alias in node.names if is_violating_module(f"{node.module}.{alias.name}")
                ]
            if not violating_names:
                continue
            if has_nocheck_marker(source_lines, node, nocheck_code):
                continue
            statement = f"from {node.module} import {', '.join(violating_names)}"
            violations.append((node.lineno, statement))
        elif check_plain_imports and isinstance(node, ast.Import):
            for alias in node.names:
                if is_violating_module(alias.name):
                    if has_nocheck_marker(source_lines, node, nocheck_code):
                        continue
                    statement = f"import {alias.name}"
                    if alias.asname:
                        statement += f" as {alias.asname}"
                    violations.append((node.lineno, statement))

    return violations
