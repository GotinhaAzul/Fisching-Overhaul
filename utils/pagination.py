from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple, TypeVar


PAGE_PREV_KEY = "o"
PAGE_NEXT_KEY = "p"

T = TypeVar("T")


@dataclass(frozen=True)
class PageSlice:
    page: int
    total_pages: int
    start: int
    end: int

    @property
    def has_prev(self) -> bool:
        return self.page > 0

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages - 1


def get_page_slice(total_items: int, page: int, page_size: int) -> PageSlice:
    safe_page_size = max(1, int(page_size))
    safe_total_items = max(0, int(total_items))
    total_pages = max(1, (safe_total_items + safe_page_size - 1) // safe_page_size)
    clamped_page = max(0, min(int(page), total_pages - 1))
    start = clamped_page * safe_page_size
    end = min(start + safe_page_size, safe_total_items)
    return PageSlice(
        page=clamped_page,
        total_pages=total_pages,
        start=start,
        end=end,
    )


def apply_page_hotkey(
    choice: str,
    page: int,
    total_pages: int,
) -> Tuple[int, bool]:
    if total_pages <= 1:
        return page, False

    lowered = choice.strip().lower()
    if lowered == PAGE_NEXT_KEY:
        return min(page + 1, total_pages - 1), True
    if lowered == PAGE_PREV_KEY:
        return max(page - 1, 0), True
    return page, False


def slice_page(items: Sequence[T], page: int, page_size: int) -> Tuple[Sequence[T], PageSlice]:
    page_slice = get_page_slice(len(items), page, page_size)
    return items[page_slice.start:page_slice.end], page_slice
