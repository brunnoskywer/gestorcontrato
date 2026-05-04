"""Busca insensível a maiúsculas/minúsculas e acentuação (PostgreSQL + extensão unaccent)."""

from __future__ import annotations

import unicodedata

from sqlalchemy import String, cast, func, literal
from sqlalchemy.sql.elements import ColumnElement


def escape_like_pattern(fragment: str) -> str:
    """Escapa `%`, `_` e `\\` para uso em LIKE com ESCAPE '\\'."""
    return (
        fragment.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def fold_query_term(value: str | None) -> str:
    """
    Normaliza o termo digitado para alinhar com lower(unaccent(coluna)) no SQL.
    Complementa unaccent para casos em que NFD não remove (ex.: cedilha pré-composta).
    """
    if not value:
        return ""
    s = unicodedata.normalize("NFD", str(value))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    for src, dst in (
        ("ç", "c"),
        ("Ç", "c"),
        ("ß", "ss"),
        ("Ł", "l"),
        ("ł", "l"),
        ("Æ", "ae"),
        ("æ", "ae"),
        ("Œ", "oe"),
        ("œ", "oe"),
    ):
        s = s.replace(src, dst)
    return s.casefold()


def col_folded_for_search(column: ColumnElement) -> ColumnElement:
    """Expressão SQL: lower(unaccent(coalesce(col::text, '')))."""
    return func.lower(func.unaccent(func.coalesce(cast(column, String), "")))


def folded_icontains(column: ColumnElement, raw_term: str) -> ColumnElement:
    """
    Condição equivalente a ILIKE '%termo%' ignorando acentos e caixa.
    O termo não deve ser vazio (quem chama costuma usar `if term:`).
    """
    folded = fold_query_term(raw_term.strip())
    if not folded:
        return literal(True)
    pattern = f"%{escape_like_pattern(folded)}%"
    return col_folded_for_search(column).like(pattern, escape="\\")
