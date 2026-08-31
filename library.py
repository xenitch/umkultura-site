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
