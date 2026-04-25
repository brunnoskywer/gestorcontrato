"""Paginação padrão das listagens administrativas (10 itens por página)."""
from __future__ import annotations

import math
from typing import Any, Iterator

from flask import request, url_for

ADMIN_LIST_PER_PAGE = 10


def admin_list_page() -> int:
    try:
        p = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        return 1
    return max(1, p)


def paginated_url(endpoint: str, page: int, **overrides: Any) -> str:
    """Monta URL da listagem preservando query string atual e alterando a página."""
    flat = request.args.to_dict(flat=True)
    for k, v in overrides.items():
        if v is None or v == "":
            flat.pop(k, None)
        else:
            flat[k] = v
    try:
        p = max(1, int(page))
    except (TypeError, ValueError):
        p = 1
    if p <= 1:
        flat.pop("page", None)
    else:
        flat["page"] = str(p)
    flat = {k: v for k, v in flat.items() if v not in (None, "")}
    return url_for(endpoint, **flat)


class SlicePagination:
    """Paginação em memória (ex.: listas já agregadas na view)."""

    def __init__(self, sequence: list, page: int, per_page: int = ADMIN_LIST_PER_PAGE):
        self.per_page = per_page
        self.total = len(sequence)
        self.pages = max(1, math.ceil(self.total / per_page)) if per_page and self.total else 1
        self.page = max(1, min(max(1, page), self.pages))
        start = (self.page - 1) * per_page
        self.items = sequence[start : start + per_page]
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None

    def iter_pages(
        self,
        left_edge: int = 1,
        right_edge: int = 1,
        left_current: int = 2,
        right_current: int = 2,
    ) -> Iterator[int | None]:
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (num > self.page - left_current - 1 and num < self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num
