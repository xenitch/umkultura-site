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
        if not 1 <= day <= 31:
            raise AfishaError(f"нет такого дня: {raw!r}")
        return ParsedDate(MONTHS_GEN[m.group(2)], [day], f"{day} {m.group(2)}")
    # Несколько дней со словом-месяцем: «17,19 сентября» → «17 и 19 сентября»
    m = re.fullmatch(r"(\d{1,2}(?: ?[,и] ?\d{1,2})+) ([а-я]+)", s)
    if m and m.group(2) in MONTHS_GEN:
        days = [int(d) for d in re.findall(r"\d{1,2}", m.group(1))]
        if any(not 1 <= d <= 31 for d in days):
            raise AfishaError(f"нет такого дня: {raw!r}")
        joined = " и ".join(str(d) for d in days)
        return ParsedDate(MONTHS_GEN[m.group(2)], days, f"{joined} {m.group(2)}")
    # Диапазоны: «с 1 по 20 сентября» и «1—31 августа»
    m = (re.fullmatch(r"с (\d{1,2}) по (\d{1,2}) ([а-я]+)", s)
         or re.fullmatch(r"(\d{1,2}) ?[—–-] ?(\d{1,2}) ([а-я]+)", s))
    if m and m.group(3) in MONTHS_GEN:
        first, last = int(m.group(1)), int(m.group(2))
        if not (1 <= first <= 31 and 1 <= last <= 31):
            raise AfishaError(f"нет такого дня: {raw!r}")
        return ParsedDate(MONTHS_GEN[m.group(3)], [first, last], re.sub(r" ?[—–-] ?", "—", s))
    if re.fullmatch(r"[\d., ;]+", s):
        days, month = [], None
        for part in re.split(r"[,;] *", s):
            m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.?", part)
            if not m:
                raise AfishaError(f"непонятная дата: {raw!r}")
            day = int(m.group(1))
            if not 1 <= day <= 31:
                raise AfishaError(f"нет такого дня: {raw!r}")
            if month is not None and int(m.group(2)) != month:
                raise AfishaError(f"даты из разных месяцев: {raw!r}")
            month = int(m.group(2))
            days.append(day)
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
    ended = False  # первая пустая строка объявляет таблицу событий закрытой
    for i, raw_row in enumerate(csv.DictReader(io.StringIO(csv_text)), start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items()}
        year_key = next((k for k in row if k.lower().startswith("год")), "")
        if not any(row.values()):
            ended = True
            continue
        if ended:
            # Хвост листа после первой пустой строки: в реальной таблице
            # там справочник клубов — у него всегда пуст год. Если год
            # заполнен, это похоже на событие, забытое под пустой строкой —
            # тихо его не проглатываем, а падаем с номером строки.
            if row.get(year_key, ""):
                raise AfishaError(
                    f"строка {i}: похоже на событие после пустой строки — "
                    "таблица событий уже закончилась (первая пустая строка "
                    "считается её концом)")
            continue
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
            contact=next((v for k, v in row.items()
                          if k.lower().startswith(("контакт", "ссылка"))), ""),
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


def fetch_csv(cache_path, url=CSV_URL, timeout=20):
    cache_path = Path(cache_path)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
        first_line = text.split("\n", 1)[0]
        if "Дата обсуждения" not in first_line:
            raise ValueError("непохоже на CSV афиши")
    except (OSError, UnicodeDecodeError, ValueError):
        if cache_path.exists():
            print("⚠ таблица недоступна, собираю из data/afisha.csv",
                  file=sys.stderr)
            return cache_path.read_text(encoding="utf-8")
        raise SystemExit(
            "Афиша: Google-таблица недоступна, и запасной копии "
            "data/afisha.csv тоже нет — собрать нечего.")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text
