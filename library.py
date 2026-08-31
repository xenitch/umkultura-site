"""Книги раздела «Прочитано»: слаги, группировка, обложки."""
from dataclasses import dataclass, field
from pathlib import Path
from zlib import crc32
import re
import sys
import urllib.request

from afisha import MONTH_TITLE, AfishaError, _sort_key

TRANSLIT = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
            "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
            "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
            "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
            "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
            "ю": "yu", "я": "ya"}

PLACEHOLDER_STYLES = ("plum", "indigo", "terra", "green", "ink")


def normalize_title(title):
    s = re.sub(r'[«»"\u201e\u201c]', "", title)
    return " ".join(s.split()).lower().replace("ё", "е")


def slugify(title):
    out = []
    for ch in normalize_title(title):
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-")


def placeholder_style(slug):
    return PLACEHOLDER_STYLES[crc32(slug.encode("utf-8")) % len(PLACEHOLDER_STYLES)]


@dataclass
class Book:
    title: str
    author: str
    slug: str
    cover_url: str
    discussions: list
    style: str
    cover_file: str = ""
    about: str = ""
    clubs_caption: str = ""


def group_books(past_events):
    books, by_slug = {}, {}
    for e in sorted(past_events, key=_sort_key):
        key = normalize_title(e.book)
        b = books.get(key)
        if b is None:
            slug = slugify(e.book)
            if slug in by_slug and by_slug[slug] != key:
                raise AfishaError(f"слаг {slug!r} совпал у разных книг")
            by_slug[slug] = key
            b = books[key] = Book(title=e.book, author=e.author, slug=slug,
                                  cover_url="", discussions=[],
                                  style=placeholder_style(slug))
        if not b.cover_url and e.cover_url:
            b.cover_url = e.cover_url
        if not b.author and e.author:
            b.author = e.author
        b.discussions.append(e)
    result = list(books.values())
    result.sort(key=lambda b: _sort_key(b.discussions[-1]), reverse=True)
    return result


def group_showcase(books, today):
    groups = []
    for b in books:
        last = b.discussions[-1]
        label = MONTH_TITLE[last.when.month]
        if last.year != today.year:
            label = f"{label} {last.year}"
        if not groups or groups[-1][0] != label:
            groups.append((label, []))
        groups[-1][1].append(b)
    return groups


def ru_plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def clubs_caption(book):
    clubs = []
    for d in book.discussions:
        if d.club and d.club not in clubs:
            clubs.append(d.club)
    if len(clubs) == 1:
        return clubs[0]
    return f"{len(clubs)} {ru_plural(len(clubs), 'клуб', 'клуба', 'клубов')}"


def discussion_date(event):
    if not event.when.days:
        return f"{MONTH_TITLE[event.when.month].lower()} {event.year}"
    return f"{event.when.display} {event.year}"


def counter_text(n):
    return (f"{n} {ru_plural(n, 'книга', 'книги', 'книг')} "
            "прочитано клубами с августа 2026")
