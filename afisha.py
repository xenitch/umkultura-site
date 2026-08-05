"""Загрузка и разбор городской афиши книжных клубов из Google-таблицы."""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv
import io
import re
import sys
import urllib.request

CSV_URL = ("https://docs.google.com/spreadsheets/d/"
           "1yqYAs1A-pI7IkMz7w2l2GKv09PjGg-RzbxI2Ng-AWaA/export?format=csv")

MONTHS_NOM = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5,
              "июнь": 6, "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10,
              "ноябрь": 11, "декабрь": 12}
MONTHS_GEN = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5,
              "июня": 6, "июля": 7, "августа": 8, "сентября": 9, "октября": 10,
              "ноября": 11, "декабря": 12}
MONTH_TITLE = {n: name.capitalize() for name, n in MONTHS_NOM.items()}
GEN_BY_NUM = {n: name for name, n in MONTHS_GEN.items()}


class AfishaError(ValueError):
    """Данные таблицы, которые не удалось разобрать."""


@dataclass
class ParsedDate:
    month: int
    days: list        # [] — известен только месяц
    display: str      # «10 августа», «13 и 15 августа», «в течение месяца»


def parse_date_field(raw):
    s = " ".join(raw.strip().lower().replace("ё", "е").split())
    if not s:
        raise AfishaError("пустая дата")
    if s in MONTHS_NOM:
        return ParsedDate(MONTHS_NOM[s], [], "в течение месяца")
    m = re.fullmatch(r"(\d{1,2}) ([а-я]+)", s)
    if m and m.group(2) in MONTHS_GEN:
        day = int(m.group(1))
        return ParsedDate(MONTHS_GEN[m.group(2)], [day], f"{day} {m.group(2)}")
    if re.fullmatch(r"[\d., ;]+", s):
        days, month = [], None
        for part in re.split(r"[,;] *", s):
            m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.?", part)
            if not m:
                raise AfishaError(f"непонятная дата: {raw!r}")
            if month is not None and int(m.group(2)) != month:
                raise AfishaError(f"даты из разных месяцев: {raw!r}")
            month = int(m.group(2))
            days.append(int(m.group(1)))
        if month not in GEN_BY_NUM:
            raise AfishaError(f"нет такого месяца: {raw!r}")
        joined = " и ".join(str(d) for d in days)
        return ParsedDate(month, days, f"{joined} {GEN_BY_NUM[month]}")
    raise AfishaError(f"непонятная дата: {raw!r}")


@dataclass
class Event:
    book: str
    author: str
    club: str
    contact: str
    year: int
    when: ParsedDate
    is_vote: bool = False


def load_events(csv_text):
    events = []
    for i, raw_row in enumerate(csv.DictReader(io.StringIO(csv_text)), start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items()}
        if not any(row.values()):
            continue
        year_key = next((k for k in row if k.lower().startswith("год")), "")
        try:
            year = int(row.get(year_key, ""))
            when = parse_date_field(row.get("Дата обсуждения", ""))
        except (AfishaError, ValueError) as exc:
            raise AfishaError(f"строка {i}: {exc}") from None
        book = row.get("Книга", "")
        is_vote = "голосован" in book.lower()
        events.append(Event(
            book="Книгу выберут голосованием" if is_vote else book,
            author=row.get("Автор", ""),
            club=row.get("В каком клубе обсуждают", ""),
            contact=row.get("Контакты клуба", ""),
            year=year, when=when, is_vote=is_vote))
    return events


def is_past(event, today):
    y, m = event.year, event.when.month
    if event.when.days:
        return date(y, m, max(event.when.days)) < today
    first_of_next = date(y + (m == 12), m % 12 + 1, 1)
    return first_of_next <= today


def split_events(events, today):
    upcoming = [e for e in events if not is_past(e, today)]
    past = [e for e in events if is_past(e, today) and not e.is_vote]
    return upcoming, past


def _sort_key(e):
    day = min(e.when.days) if e.when.days else 0
    return (e.year, e.when.month, day)


def group_schedule(upcoming, today):
    groups = []
    for e in sorted(upcoming, key=_sort_key):
        label = MONTH_TITLE[e.when.month]
        if e.year != today.year:
            label = f"{label} {e.year}"
        if not groups or groups[-1][0] != label:
            groups.append((label, []))
        groups[-1][1].append(e)
    return groups


def group_archive(past):
    years = []
    for e in sorted(past, key=_sort_key, reverse=True):
        if not years or years[-1][0] != e.year:
            years.append((e.year, []))
        months = years[-1][1]
        label = MONTH_TITLE[e.when.month]
        if not months or months[-1][0] != label:
            months.append((label, []))
        months[-1][1].append(e)
    return years
