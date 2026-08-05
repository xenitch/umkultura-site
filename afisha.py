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
