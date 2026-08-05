# umkultura.ru Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Статический сайт umkultura.ru: главная-заглушка, каталог книжных клубов, афиша «Будущие чтения» и архив «Библиотека», собираемые из Google-таблицы.

**Architecture:** Генератор по образцу xenitch.ru: `build.py` рендерит markdown+frontmatter из `content/` через Jinja2-шаблоны в `docs/` (раздаёт GitHub Pages, репозиторий `xenitch/umkultura-site` уже создан и настроен). Новый модуль `afisha.py` скачивает CSV Google-таблицы (с офлайн-копией `data/afisha.csv`), разбирает даты и делит события на будущие/прошедшие.

**Tech Stack:** Python 3.9, Markdown, python-frontmatter==1.0.1, Jinja2, pytest. Без JavaScript.

Спека: `docs-project/specs/2026-08-05-umkultura-site-design.md`.

## Global Constraints

- Корень проекта: `/Users/xenitch/umkultura-site` (venv: `.venv/`, вызовы `.venv/bin/python`, `.venv/bin/pytest`).
- Python 3.9 → пин `python-frontmatter==1.0.1`.
- `docs/` — результат сборки, коммитится, полностью пересоздаётся при сборке; `data/afisha.csv` — коммитится.
- Палитра: бумага `#f7f2e6`, чернила `#26221c`, индиго `#2b3a67`, терракота `#a34a2e`, золото `#b08d3f`, приглушённый `#6d6152`.
- Шрифты: Old Standard TT (заголовки/названия книг/навигация) + Literata (текст), self-hosted woff2, сабсеты cyrillic+latin.
- Jinja2 `autoescape=False`; весь frontmatter и данные таблицы в шаблонах — через `| e`.
- Тексты интерфейса: «Клубы · Будущие чтения · Библиотека», кикеры «Будущие чтения»/«Библиотека», подвал «Клуб книжных клубов · Кемерово», голосования — «Книгу выберут голосованием», месяц без даты — «в течение месяца».
- ID таблицы: `1yqYAs1A-pI7IkMz7w2l2GKv09PjGg-RzbxI2Ng-AWaA`.
- Коммиты — небольшие, после каждого зелёного цикла тестов.

---

### Task 1: Каркас репозитория и окружение

**Files:**
- Create: `.gitignore`, `requirements.txt`, каталоги `content/bookclubs/`, `templates/`, `static/fonts/`, `data/`, `tests/`

**Interfaces:**
- Produces: рабочий venv `.venv/` с зависимостями; структура каталогов для всех последующих задач.

- [ ] **Step 1: venv и зависимости**

```bash
cd /Users/xenitch/umkultura-site
python3 -m venv .venv
.venv/bin/pip install --quiet markdown "python-frontmatter==1.0.1" jinja2 pytest
.venv/bin/pip freeze | grep -iE "^(markdown|python-frontmatter|jinja2|pytest)=" > requirements.txt
```

- [ ] **Step 2: .gitignore и каталоги**

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
.DS_Store
```

```bash
mkdir -p content/bookclubs templates static/fonts data tests
```

- [ ] **Step 3: Проверка и коммит**

Run: `.venv/bin/python -c "import markdown, frontmatter, jinja2; print('ok')"`
Expected: `ok`

```bash
git add .gitignore requirements.txt
git commit -m "chore: окружение и каркас каталогов"
```

---

### Task 2: afisha.py — разбор поля даты

**Files:**
- Create: `afisha.py`
- Test: `tests/test_afisha.py`

**Interfaces:**
- Produces: `afisha.parse_date_field(raw: str) -> ParsedDate`; `ParsedDate(month: int, days: list, display: str)` (`days == []` — известен только месяц); исключение `afisha.AfishaError(ValueError)`; словари `MONTHS_NOM`, `MONTHS_GEN`, `MONTH_TITLE`, `GEN_BY_NUM`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_afisha.py`:
```python
from datetime import date

import pytest

import afisha
from afisha import AfishaError, parse_date_field


def test_день_и_месяц():
    pd = parse_date_field("10 августа")
    assert (pd.month, pd.days, pd.display) == (8, [10], "10 августа")


def test_только_месяц():
    pd = parse_date_field("август")
    assert (pd.month, pd.days, pd.display) == (8, [], "в течение месяца")


def test_несколько_числовых_дат():
    pd = parse_date_field("13.08, 15.08")
    assert (pd.month, pd.days, pd.display) == (8, [13, 15], "13 и 15 августа")


def test_одна_числовая_дата():
    assert parse_date_field("10.08").display == "10 августа"


def test_лишние_пробелы_и_регистр():
    assert parse_date_field(" Сентябрь ").month == 9


def test_ерунда_даёт_ошибку():
    with pytest.raises(AfishaError):
        parse_date_field("когда-нибудь")


def test_даты_из_разных_месяцев_даёт_ошибку():
    with pytest.raises(AfishaError):
        parse_date_field("13.08, 15.09")
```

Чтобы `import afisha` / `import build` в тестах работали, в корень проекта добавить `pytest.ini`:
```ini
[pytest]
testpaths = tests
```
и **пустой** `conftest.py` (в корень, рядом с afisha.py) — pytest добавляет каталог conftest в `sys.path`, так модули из корня становятся импортируемыми. Запускать pytest из корня проекта.

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd /Users/xenitch/umkultura-site && .venv/bin/pytest -q`
Expected: FAIL / ошибка импорта `afisha`

- [ ] **Step 3: Реализация**

`afisha.py`:
```python
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
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/bin/pytest -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add afisha.py tests/test_afisha.py pytest.ini conftest.py
git commit -m "feat: разбор поля даты афиши"
```

---

### Task 3: afisha.py — чтение CSV и события

**Files:**
- Modify: `afisha.py` (добавить в конец)
- Test: `tests/test_afisha.py` (добавить в конец)

**Interfaces:**
- Consumes: `parse_date_field`, `ParsedDate`, `AfishaError` (Task 2).
- Produces: `Event(book, author, club, contact: str, year: int, when: ParsedDate, is_vote: bool)`; `load_events(csv_text: str) -> list[Event]`. Колонки CSV: «Дата обсуждения», «Книга», «Автор», «В каком клубе обсуждают», «Контакты клуба», колонка года ищется по префиксу «год». Строка-голосование: в «Книге» есть «голосован» → `is_vote=True`, `book="Книгу выберут голосованием"`.

- [ ] **Step 1: Падающие тесты (добавить в tests/test_afisha.py)**

```python
CSV = """Дата обсуждения,Книга,Автор,В каком клубе обсуждают,Контакты клуба,год (для определения архива)
10 августа,«Элегантность ёжика»,Мюриель Барбери,Это просто книжный клуб,https://vk.ru/prosto_book_club,2026
август,«Мартин Иден»,Джек Лондон,Клуб нескучных чтений,https://t.me/ReadingClubLibrary,2026
6 октября,будет голосование в группе клуба,,Это просто книжный клуб,https://vk.ru/prosto_book_club,2026
"""


def test_load_events_читает_строки():
    events = afisha.load_events(CSV)
    assert len(events) == 3
    e = events[0]
    assert (e.book, e.author, e.club) == (
        "«Элегантность ёжика»", "Мюриель Барбери", "Это просто книжный клуб")
    assert e.contact == "https://vk.ru/prosto_book_club"
    assert e.year == 2026 and e.when.month == 8


def test_строка_голосования():
    e = afisha.load_events(CSV)[2]
    assert e.is_vote is True
    assert e.book == "Книгу выберут голосованием"
    assert e.author == ""


def test_пустые_строки_пропускаются():
    events = afisha.load_events(CSV + ",,,,,\n")
    assert len(events) == 3


def test_ошибка_с_номером_строки():
    bad = CSV + "потом,«Книга»,Автор,Клуб,https://example.com,2026\n"
    with pytest.raises(AfishaError, match="строка 5"):
        afisha.load_events(bad)
```

- [ ] **Step 2: Убедиться, что падают**

Run: `.venv/bin/pytest -q`
Expected: 4 новых FAIL (`load_events` не определена)

- [ ] **Step 3: Реализация (добавить в afisha.py)**

```python
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
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/bin/pytest -q`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add afisha.py tests/test_afisha.py
git commit -m "feat: чтение CSV афиши в события"
```

---

### Task 4: afisha.py — деление будущее/прошлое и группировка

**Files:**
- Modify: `afisha.py` (добавить в конец)
- Test: `tests/test_afisha.py` (добавить в конец)

**Interfaces:**
- Consumes: `Event`, `ParsedDate`, `load_events`, `MONTH_TITLE`.
- Produces:
  - `is_past(event: Event, today: date) -> bool` — точная дата в прошлом со следующего дня (по последней из дат), «только месяц» — с 1-го числа следующего месяца;
  - `split_events(events, today) -> (upcoming, past)` — прошедшие голосования отбрасываются;
  - `group_schedule(upcoming, today) -> list[(label: str, [Event])]` — хронологически, «Август» или «Январь 2027» (год ≠ текущему), внутри месяца события «только месяц» первыми;
  - `group_archive(past) -> list[(year: int, [(month_label: str, [Event])])]` — свежие сверху.

- [ ] **Step 1: Падающие тесты (добавить в tests/test_afisha.py)**

```python
def _ev(raw, year=2026):
    return afisha.Event(book="К", author="А", club="Клуб", contact="",
                        year=year, when=parse_date_field(raw))


def test_точная_дата_в_архив_со_следующего_дня():
    e = _ev("10 августа")
    assert afisha.is_past(e, date(2026, 8, 10)) is False
    assert afisha.is_past(e, date(2026, 8, 11)) is True


def test_месяц_в_архив_с_первого_числа_следующего():
    e = _ev("август")
    assert afisha.is_past(e, date(2026, 8, 31)) is False
    assert afisha.is_past(e, date(2026, 9, 1)) is True


def test_декабрь_переходит_через_год():
    e = _ev("декабрь")
    assert afisha.is_past(e, date(2026, 12, 31)) is False
    assert afisha.is_past(e, date(2027, 1, 1)) is True


def test_несколько_дат_по_последней():
    e = _ev("13.08, 15.08")
    assert afisha.is_past(e, date(2026, 8, 14)) is False
    assert afisha.is_past(e, date(2026, 8, 16)) is True


def test_прошедшее_голосование_не_попадает_в_архив():
    up, past = afisha.split_events(afisha.load_events(CSV), date(2027, 1, 1))
    assert up == []
    assert all(not e.is_vote for e in past)
    assert len(past) == 2


def test_группировка_оглавления():
    up, _ = afisha.split_events(afisha.load_events(CSV), date(2026, 8, 1))
    groups = afisha.group_schedule(up, date(2026, 8, 1))
    assert [g[0] for g in groups] == ["Август", "Октябрь"]
    август = groups[0][1]
    assert август[0].when.display == "в течение месяца"   # месяц-без-даты первым
    assert август[1].when.display == "10 августа"


def test_метка_месяца_другого_года():
    groups = afisha.group_schedule([_ev("январь", year=2027)], date(2026, 8, 1))
    assert groups[0][0] == "Январь 2027"


def test_группировка_архива_свежие_сверху():
    past = [_ev("10 августа"), _ev("сентябрь"), _ev("май", year=2025)]
    years = afisha.group_archive(past)
    assert [y for y, _ in years] == [2026, 2025]
    assert [m for m, _ in years[0][1]] == ["Сентябрь", "Август"]
```

- [ ] **Step 2: Убедиться, что падают**

Run: `.venv/bin/pytest -q`
Expected: новые FAIL (`is_past` не определена)

- [ ] **Step 3: Реализация (добавить в afisha.py)**

```python
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
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/bin/pytest -q`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add afisha.py tests/test_afisha.py
git commit -m "feat: деление будущее/прошлое и группировка по месяцам"
```

---

### Task 5: afisha.py — скачивание с офлайн-копией

**Files:**
- Modify: `afisha.py` (добавить в конец)
- Test: `tests/test_afisha.py` (добавить в конец)

**Interfaces:**
- Consumes: `CSV_URL`.
- Produces: `fetch_csv(cache_path: Path, url: str = CSV_URL, timeout: int = 20) -> str` — при успехе пишет копию в `cache_path`; при сетевой ошибке читает `cache_path` с предупреждением в stderr; если копии нет — `SystemExit` с понятным текстом.

- [ ] **Step 1: Падающие тесты (добавить в tests/test_afisha.py)**

```python
import io as _io


class _FakeResponse(_io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_fetch_сохраняет_копию(tmp_path, monkeypatch):
    monkeypatch.setattr(afisha.urllib.request, "urlopen",
                        lambda url, timeout: _FakeResponse(CSV.encode("utf-8")))
    cache = tmp_path / "data" / "afisha.csv"
    assert afisha.fetch_csv(cache) == CSV
    assert cache.read_text(encoding="utf-8") == CSV


def test_фолбэк_на_копию_без_сети(tmp_path, monkeypatch, capsys):
    def boom(url, timeout):
        raise OSError("нет сети")
    monkeypatch.setattr(afisha.urllib.request, "urlopen", boom)
    cache = tmp_path / "afisha.csv"
    cache.write_text(CSV, encoding="utf-8")
    assert afisha.fetch_csv(cache) == CSV
    assert "data/afisha.csv" in capsys.readouterr().err


def test_без_сети_и_без_копии_понятная_ошибка(tmp_path, monkeypatch):
    def boom(url, timeout):
        raise OSError("нет сети")
    monkeypatch.setattr(afisha.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit, match="запасной копии"):
        afisha.fetch_csv(tmp_path / "нет.csv")
```

- [ ] **Step 2: Убедиться, что падают**

Run: `.venv/bin/pytest -q`
Expected: 3 новых FAIL

- [ ] **Step 3: Реализация (добавить в afisha.py)**

```python
def fetch_csv(cache_path, url=CSV_URL, timeout=20):
    cache_path = Path(cache_path)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
    except OSError:
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
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/bin/pytest -q`
Expected: 22 passed

- [ ] **Step 5: Commit**

```bash
git add afisha.py tests/test_afisha.py
git commit -m "feat: скачивание афиши с офлайн-копией data/afisha.csv"
```

---

### Task 6: Шрифты и style.css

**Files:**
- Create: `static/fonts/*.woff2` (6 файлов), `static/style.css`

**Interfaces:**
- Produces: дизайн-система для шаблонов Task 7 — классы `site-header`, `site-nav`, `current`, `logo-book`, `prose`, `kicker`, `page-header`, `toc`, `toc-month`, `toc-year`, `toc-row`, `toc-item`, `toc-book`, `toc-author`, `toc-dots`, `toc-date`, `toc-club`, `toc-club-right`, `fleuron`, `club`, `site-footer`, `home-main`, `home-phrase`, `home-orn`.

- [ ] **Step 1: Скачать шрифты**

```bash
cd /Users/xenitch/umkultura-site
curl -sL "https://gwfh.mranftl.com/api/fonts/old-standard-tt?download=zip&subsets=cyrillic,latin&formats=woff2&variants=regular,italic,700" -o ost.zip
curl -sL "https://gwfh.mranftl.com/api/fonts/literata?download=zip&subsets=cyrillic,latin&formats=woff2&variants=regular,italic,700" -o lit.zip
unzip -o ost.zip -d static/fonts && unzip -o lit.zip -d static/fonts
rm ost.zip lit.zip && ls static/fonts
```
Expected: 6 woff2-файлов. Если API вернул ошибку по variants — запросить `https://gwfh.mranftl.com/api/fonts/old-standard-tt` без параметров, посмотреть доступные `variants` и скорректировать (у Old Standard TT жирное начертание может называться `700` или `bold`).

- [ ] **Step 2: Написать static/style.css**

Сверить имена файлов в `@font-face` с реально скачанными (версия `v…` в имени).

```css
/* Палитра: бумага/чернила/индиго/терракота/золото */
:root {
  --paper: #f7f2e6; --ink: #26221c; --indigo: #2b3a67; --terra: #a34a2e;
  --gold: #b08d3f; --muted: #6d6152;
}
@font-face { font-family: "Old Standard TT"; src: url(/static/fonts/old-standard-tt-v25-cyrillic_latin-regular.woff2) format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Old Standard TT"; src: url(/static/fonts/old-standard-tt-v25-cyrillic_latin-700.woff2) format("woff2"); font-weight: 700; font-display: swap; }
@font-face { font-family: "Old Standard TT"; src: url(/static/fonts/old-standard-tt-v25-cyrillic_latin-italic.woff2) format("woff2"); font-style: italic; font-display: swap; }
@font-face { font-family: "Literata"; src: url(/static/fonts/literata-v40-cyrillic_latin-regular.woff2) format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Literata"; src: url(/static/fonts/literata-v40-cyrillic_latin-700.woff2) format("woff2"); font-weight: 700; font-display: swap; }
@font-face { font-family: "Literata"; src: url(/static/fonts/literata-v40-cyrillic_latin-italic.woff2) format("woff2"); font-style: italic; font-display: swap; }

html { background: var(--paper); color: var(--ink); }
body {
  margin: 0 auto; padding: 2.5rem 1.25rem 4rem; max-width: 42rem;
  font: 400 1.125rem/1.65 "Literata", "PT Serif", Georgia, serif;
  hyphens: auto; font-feature-settings: "onum" 1;
}
h1, h2, h3 { font-family: "Old Standard TT", Georgia, serif; line-height: 1.2; font-weight: 700; }
h1 { font-size: 2.1rem; margin: 0.4em 0; }
a { color: var(--indigo); text-decoration-color: rgba(176, 141, 63, 0.6); text-underline-offset: 3px; }
a:hover { color: var(--terra); }
.kicker, .site-nav a { font-family: "Old Standard TT", serif;
  font-variant-caps: all-small-caps; letter-spacing: 0.08em; }
.kicker { color: var(--terra); margin: 0; }

.site-header { display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  border-bottom: 1px solid var(--gold); padding-bottom: 0.75rem; margin-bottom: 2.5rem; }
.logo-book { width: 4.5rem; height: auto; display: block; }
.site-nav a { text-decoration: none; color: var(--ink); }
.site-nav a.current, .site-nav a:hover { color: var(--terra); }

.page-header { margin-bottom: 1.5rem; }

/* Оглавление сезона и библиотека */
.toc-month { font-family: "Old Standard TT", serif; font-variant-caps: all-small-caps;
  letter-spacing: 0.12em; text-align: center; color: var(--terra);
  font-size: 1.05rem; font-weight: 400; margin: 1.6em 0 0.5em; }
.toc-month::before, .toc-month::after { content: " ·· "; color: var(--gold); }
.toc-year { font-family: "Old Standard TT", serif; text-align: center;
  font-size: 1.5rem; margin: 1.4em 0 0.2em; }
.toc-row { display: flex; align-items: baseline; margin: 0.6em 0 0; }
.toc-book { font-family: "Old Standard TT", serif; font-weight: 700; }
.toc-author { font-style: italic; color: var(--muted); }
.toc-dots { flex: 1; border-bottom: 2px dotted rgba(176, 141, 63, 0.7);
  margin: 0 0.4em 0.3em; min-width: 1.5rem; }
.toc-date { color: var(--indigo); font-variant-caps: all-small-caps; white-space: nowrap; }
.toc-club { font-size: 0.8em; color: var(--muted); margin: 0.1em 0 0.4em; }
.toc-club a { color: var(--muted); }
.toc-club-right { white-space: nowrap; font-size: 0.9em; }
.fleuron { text-align: center; color: var(--gold); margin: 2em 0 0; }
hr { border: 0; text-align: center; margin: 2.5em 0; }
hr::after { content: "❦"; color: var(--gold); font-size: 1.1em; }
blockquote { margin: 1.5em 0; padding-left: 1.25em; border-left: 2px solid var(--gold);
  font-style: italic; color: var(--muted); }

/* Каталог клубов */
.club { border-top: 1px solid rgba(176, 141, 63, 0.45); padding: 0.8em 0 0.6em; }
.club h3 { margin: 0; }
.club p { margin: 0.2em 0; }
.club .contact { font-size: 0.85em; }

.site-footer { margin-top: 4rem; border-top: 1px solid var(--gold); padding-top: 1rem;
  color: var(--muted); font-size: 0.9em; }

/* Главная-заглушка */
.home-main { min-height: 70vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center; }
.home-main .logo-book { width: 6rem; }
.home-phrase { font-family: "Old Standard TT", serif; font-size: 1.6rem;
  line-height: 1.35; max-width: 26rem; margin: 1.2em 0 0; }
.home-orn { color: var(--gold); margin-top: 1.2em; font-size: 1.1em; }
```

- [ ] **Step 3: Commit**

```bash
git add static
git commit -m "feat: шрифты Old Standard TT + Literata и дизайн-система"
```

---

### Task 7: Шаблоны, контент, build.py и тест полной сборки

**Files:**
- Create: `templates/skeleton.html`, `templates/base.html`, `templates/_logo.html`, `templates/home.html`, `templates/page.html`, `templates/schedule.html`, `templates/archive.html`, `content/index.md`, `content/bookclubs/index.md`, `content/bookclubs/schedule.md`, `content/bookclubs/archive.md`, `build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `afisha.fetch_csv`, `afisha.load_events`, `afisha.split_events`, `afisha.group_schedule`, `afisha.group_archive` (Tasks 3–5); классы CSS (Task 6).
- Produces: `build.build(root: Path, today: date = None, fetch=afisha.fetch_csv) -> None` — собирает сайт в `root/docs`; `fetch` подменяется в тестах (принимает `cache_path`, возвращает текст CSV). URL: `/`, `/bookclubs/`, `/bookclubs/schedule/`, `/bookclubs/archive/`.

- [ ] **Step 1: Падающий тест сборки**

`tests/test_build.py`:
```python
from datetime import date
from pathlib import Path
import shutil

import build
from test_afisha import CSV

ROOT = Path(__file__).resolve().parent.parent


def _make_project(tmp_path):
    for name in ("content", "templates", "static"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return tmp_path


def test_полная_сборка(tmp_path):
    root = _make_project(tmp_path)
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV)
    out = root / "docs"
    for page in ("", "bookclubs", "bookclubs/schedule", "bookclubs/archive"):
        assert (out / page / "index.html").exists(), page
    assert (out / "CNAME").read_text(encoding="utf-8") == "umkultura.ru"
    assert (out / ".nojekyll").exists()
    assert (out / "static" / "style.css").exists()

    home = (out / "index.html").read_text(encoding="utf-8")
    assert "Пространство развития умственной" in home
    assert "site-nav" not in home                       # заглушка без навигации

    schedule = (out / "bookclubs/schedule/index.html").read_text(encoding="utf-8")
    assert "Книгу выберут голосованием" in schedule     # будущая строка-голосование
    assert "«Элегантность ёжика»" not in schedule       # 10 августа уже прошло

    archive = (out / "bookclubs/archive/index.html").read_text(encoding="utf-8")
    assert "«Элегантность ёжика»" in archive
    assert "Книгу выберут голосованием" not in archive  # голосования не архивируются


def test_пересборка_убирает_устаревшее(tmp_path):
    root = _make_project(tmp_path)
    stale = root / "docs" / "старое" / "index.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("устарело", encoding="utf-8")
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV)
    assert not stale.exists()
```

- [ ] **Step 2: Убедиться, что падает**

Run: `.venv/bin/pytest tests/test_build.py -q`
Expected: ошибка импорта `build` / отсутствуют шаблоны

- [ ] **Step 3: Шаблоны**

`templates/skeleton.html`:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% if page.meta.title and page.url != '/' %}{{ page.meta.title | e }} — {{ site.name | e }}{% else %}{{ site.name | e }}{% endif %}</title>
  <meta name="description" content="{{ (page.meta.description or site.description) | e }}">
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
{% block body %}{% endblock %}
</body>
</html>
```

`templates/_logo.html` (времянка до картинки Ксении; заменить = переписать этот файл):
```html
<svg class="logo-book" viewBox="0 0 64 48" fill="none" stroke="#2b3a67" stroke-width="1.8" stroke-linecap="round" role="img" aria-label="Раскрытая книга">
  <path d="M32 12 C 26 5, 13 4, 5 8 L5 33 C 13 29, 26 30, 32 37"/>
  <path d="M32 12 C 38 5, 51 4, 59 8 L59 33 C 51 29, 38 30, 32 37"/>
  <path d="M32 12 L32 37"/>
  <path d="M32 15 C 28 10, 19 9, 12 11 M32 15 C 36 10, 45 9, 52 11" stroke="#b08d3f" stroke-width="1"/>
  <path d="M36 14 L36 44 L40 40 L44 44 L44 13" stroke="#a34a2e" stroke-width="1.5" fill="#a34a2e" fill-opacity="0.15"/>
</svg>
```

`templates/base.html`:
```html
{% extends "skeleton.html" %}
{% block body %}
  <header class="site-header">
    <a href="/bookclubs/" aria-label="Книжные клубы Кемерова">{% include "_logo.html" %}</a>
    <nav class="site-nav">
      <a href="/bookclubs/"{% if page.url == '/bookclubs/' %} class="current"{% endif %}>Клубы</a> ·
      <a href="/bookclubs/schedule/"{% if page.url == '/bookclubs/schedule/' %} class="current"{% endif %}>Будущие чтения</a> ·
      <a href="/bookclubs/archive/"{% if page.url == '/bookclubs/archive/' %} class="current"{% endif %}>Библиотека</a>
    </nav>
  </header>
  <main>{% block content %}{% endblock %}</main>
  <footer class="site-footer">
    <p>Клуб книжных клубов · Кемерово</p>
  </footer>
{% endblock %}
```

`templates/home.html`:
```html
{% extends "skeleton.html" %}
{% block body %}
  <main class="home-main">
    {% include "_logo.html" %}
    <p class="home-phrase">{{ page.meta.phrase | e }}</p>
    <p class="home-orn">❦</p>
  </main>
{% endblock %}
```

`templates/page.html`:
```html
{% extends "base.html" %}
{% block content %}
<article class="prose">
  <header class="page-header">
    {% if page.meta.kicker %}<p class="kicker">{{ page.meta.kicker | e }}</p>{% endif %}
    {% if page.meta.title %}<h1>{{ page.meta.title | e }}</h1>{% endif %}
  </header>
  {{ page.content }}
</article>
{% endblock %}
```

`templates/schedule.html`:
```html
{% extends "base.html" %}
{% block content %}
<article class="prose">
  <header class="page-header">
    <p class="kicker">{{ page.meta.kicker | e }}</p>
    <h1>{{ page.meta.title | e }}</h1>
  </header>
  {{ page.content }}
</article>
<section class="toc">
  {% for label, events in schedule_groups %}
  <h2 class="toc-month">{{ label }}</h2>
    {% for e in events %}
  <div class="toc-row">
    <span class="toc-item"><span class="toc-book">{{ e.book | e }}</span>
      {% if e.author %} <span class="toc-author">{{ e.author | e }}</span>{% endif %}</span>
    <span class="toc-dots"></span>
    <span class="toc-date">{{ e.when.display }}</span>
  </div>
  <p class="toc-club"><a href="{{ e.contact | e }}">{{ e.club | e }}</a></p>
    {% endfor %}
  {% endfor %}
  <p class="fleuron">❦</p>
</section>
{% endblock %}
```

`templates/archive.html`:
```html
{% extends "base.html" %}
{% block content %}
<article class="prose">
  <header class="page-header">
    <p class="kicker">{{ page.meta.kicker | e }}</p>
    <h1>{{ page.meta.title | e }}</h1>
  </header>
  {{ page.content }}
</article>
<section class="toc">
  {% for year, months in archive_years %}
  <h2 class="toc-year">{{ year }}</h2>
    {% for label, events in months %}
  <h3 class="toc-month">{{ label }}</h3>
      {% for e in events %}
  <div class="toc-row">
    <span class="toc-item"><span class="toc-book">{{ e.book | e }}</span>
      {% if e.author %} <span class="toc-author">{{ e.author | e }}</span>{% endif %}</span>
    <span class="toc-dots"></span>
    <span class="toc-club-right"><a href="{{ e.contact | e }}">{{ e.club | e }}</a></span>
  </div>
      {% endfor %}
    {% endfor %}
  {% endfor %}
  <p class="fleuron">❦</p>
</section>
{% endblock %}
```

- [ ] **Step 4: Контент**

`content/index.md`:
```markdown
---
title: Пространство развития умственной культуры
template: home.html
phrase: Пространство развития умственной культуры
---
```

`content/bookclubs/index.md` (контакты — из таблицы афиши; описания добавятся позже от координаторов):
```markdown
---
title: Книжные клубы города
kicker: Клуб книжных клубов · Кемерово
description: Каталог книжных клубов Кемерова — выбирайте клуб по духу и приходите читать вместе.
---
Читательские сообщества Кемерова объединились, чтобы вести общую
афишу. Выбирайте клуб по духу — и приходите читать вместе.

<div class="club">
<h3>Это просто книжный клуб</h3>
<p class="contact"><a href="https://vk.ru/prosto_book_club">vk.ru/prosto_book_club</a></p>
</div>

<div class="club">
<h3>Клуб нескучных чтений</h3>
<p class="contact"><a href="https://t.me/ReadingClubLibrary">t.me/ReadingClubLibrary</a></p>
</div>

<div class="club">
<h3>Читательский клуб Кемерово</h3>
<p class="contact"><a href="https://t.me/club_forreading">t.me/club_forreading</a></p>
</div>

<div class="club">
<h3>Строки с любовью</h3>
<p class="contact"><a href="https://t.me/LineswithLove">t.me/LineswithLove</a></p>
</div>

<div class="club">
<h3>Час души</h3>
<p class="contact"><a href="https://telegram.me/olgakushnir">telegram.me/olgakushnir</a></p>
</div>

<div class="club">
<h3>Лаборатория органических медиа</h3>
<p class="contact"><a href="https://t.me/organic_media">t.me/organic_media</a></p>
</div>
```

`content/bookclubs/schedule.md`:
```markdown
---
title: Оглавление сезона
kicker: Будущие чтения
template: schedule.html
description: Что обсуждают книжные клубы Кемерова в ближайшие месяцы.
---
Что обсуждают книжные клубы Кемерова в ближайшие месяцы.
Даты уточняйте у клуба — ссылки ведут в их сообщества.
```

`content/bookclubs/archive.md`:
```markdown
---
title: Что город уже прочитал
kicker: Библиотека
template: archive.html
description: Архив прошедших обсуждений книжных клубов Кемерова.
---
Прошедшие обсуждения — общая читательская память города.
Страница пополняется сама, когда встреча остаётся позади.
```

- [ ] **Step 5: build.py**

```python
#!/usr/bin/env python3
"""Сборка сайта: content/ + templates/ + афиша -> docs/."""
from datetime import date
from pathlib import Path, PurePosixPath
import shutil

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader

import afisha

SITE = {
    "name": "Пространство развития умственной культуры",
    "domain": "umkultura.ru",
    "author": "Ксения Костюченко",
    "description": ("Городская афиша книжных клубов Кемерова: "
                    "будущие чтения и библиотека прошедших обсуждений."),
}


def page_url(rel: PurePosixPath) -> str:
    parts = rel.parent.parts if rel.name == "index.md" else rel.parent.parts + (rel.stem,)
    return "/" + "/".join(parts) + "/" if parts else "/"


def render_md(text: str) -> str:
    return markdown.markdown(text, extensions=["extra"])


def load_page(path: Path, content_dir: Path) -> dict:
    post = frontmatter.load(path)
    rel = PurePosixPath(path.relative_to(content_dir).as_posix())
    return {"url": page_url(rel), "meta": post.metadata,
            "content": render_md(post.content)}


def build(root: Path, today=None, fetch=afisha.fetch_csv) -> None:
    today = today or date.today()
    content_dir, out = root / "content", root / "docs"

    events = afisha.load_events(fetch(root / "data" / "afisha.csv"))
    upcoming, past = afisha.split_events(events, today)
    ctx = {
        "site": SITE,
        "schedule_groups": afisha.group_schedule(upcoming, today),
        "archive_years": afisha.group_archive(past),
    }

    env = Environment(loader=FileSystemLoader(root / "templates"), autoescape=False)
    pages = [load_page(p, content_dir) for p in sorted(content_dir.rglob("*.md"))]

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(root / "static", out / "static")
    (out / "CNAME").write_text(SITE["domain"], encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    for page in pages:
        tpl = page["meta"].get("template") or "page.html"
        html = env.get_template(tpl).render(page=page, **ctx)
        dest = out / page["url"].strip("/") / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).parent)
    print("Собрано в docs/")
```

- [ ] **Step 6: Все тесты зелёные**

Run: `.venv/bin/pytest -q`
Expected: 24 passed

- [ ] **Step 7: Commit**

```bash
git add templates content build.py tests/test_build.py
git commit -m "feat: генератор, шаблоны и контент четырёх страниц"
```

---

### Task 8: Первая настоящая сборка и публикация

**Files:**
- Create: `data/afisha.csv` (появится при сборке), `docs/**` (пересоздастся)
- Modify: `README.md`

**Interfaces:**
- Consumes: всё из Tasks 1–7.
- Produces: живой сайт на umkultura.ru (после пропагации DNS).

- [ ] **Step 1: Собрать с настоящей таблицей**

Run: `cd /Users/xenitch/umkultura-site && .venv/bin/python build.py`
Expected: `Собрано в docs/`, появился `data/afisha.csv` с текущей афишей.

- [ ] **Step 2: Локальное превью**

```bash
cd docs && python3 -m http.server 8899
```
Открыть http://localhost:8899 — проверить все четыре страницы глазами (шрифты, отточия, навигация, заглушка), затем остановить сервер.

- [ ] **Step 3: README**

Заменить содержимое `README.md`:
```markdown
# umkultura.ru

Пространство развития умственной культуры (Кемерово): каталог книжных
клубов, афиша «Будущие чтения» и «Библиотека» прошедших обсуждений.

Источник афиши — Google-таблица клуба книжных клубов; при сборке она
скачивается и сохраняется в `data/afisha.csv` (офлайн-копия).

## Как обновить сайт

    .venv/bin/python build.py && .venv/bin/pytest -q
    git add -A && git commit -m "Обновление афиши" && git push

Через минуту-две изменения на https://umkultura.ru.
Документация проекта: `docs-project/` (спека и план).
```

- [ ] **Step 4: Тесты и публикация**

Run: `.venv/bin/pytest -q` — Expected: 24 passed

```bash
git add -A
git commit -m "feat: первая сборка сайта"
git push
```

- [ ] **Step 5: Проверить публикацию**

Через ~2 минуты: `curl -s https://xenitch.github.io/umkultura-site/ -o /dev/null -w "%{http_code} %{redirect_url}\n"`
Expected: `301 http://umkultura.ru/` (редирект на custom domain — значит Pages собрал новую версию).

---

### Task 9: DNS, сертификат, HTTPS

**Files:** нет (внешняя инфраструктура)

**Interfaces:**
- Consumes: A-записи и CNAME внесены в reg.ru 2026-08-05 (TTL старой записи 6 ч).

- [ ] **Step 1: Проверить пропагацию**

```bash
curl -s "https://dns.google/resolve?name=umkultura.ru&type=A" | python3 -c "import json,sys; print([a['data'] for a in json.load(sys.stdin).get('Answer',[])])"
```
Expected: четыре адреса `185.199.108–111.153`. Если всё ещё `95.163.244.138` — подождать (до 6 ч от смены записей) и повторить.

- [ ] **Step 2: Статус сертификата**

```bash
TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
curl -s -H "Authorization: token $TOKEN" https://api.github.com/repos/xenitch/umkultura-site/pages | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status'), d.get('https_certificate', {}).get('state'))"
```
Expected: состояние сертификата `approved`/`issued`. Если завис в `pending` дольше пары часов после пропагации — в настройках Pages снять и заново указать домен (PUT c `"cname": null`, затем c `"cname": "umkultura.ru"`).

- [ ] **Step 3: Включить Enforce HTTPS**

```bash
curl -s -X PUT -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  https://api.github.com/repos/xenitch/umkultura-site/pages \
  -d '{"https_enforced": true, "cname": "umkultura.ru", "source": {"branch": "main", "path": "/docs"}}' -o /dev/null -w "%{http_code}\n"
```
Expected: `204`

- [ ] **Step 4: Финальная проверка**

```bash
for u in https://umkultura.ru/ https://umkultura.ru/bookclubs/ https://umkultura.ru/bookclubs/schedule/ https://umkultura.ru/bookclubs/archive/ https://www.umkultura.ru/; do
  echo "$u: $(curl -s -o /dev/null -w '%{http_code}' -L "$u")"
done
```
Expected: везде `200`.
