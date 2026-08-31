# «Прочитано» (библиотека) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Раздел прочитанных книг: витрина-каталог `/bookclubs/library/` и страница на каждую книгу `/bookclubs/library/{slug}/` с обложкой, аннотацией и обсуждениями.

**Architecture:** Прошедшие события афиши группируются в «книги» новым модулем `library.py` (слаги-транслит, обложки по ссылке из таблицы с кешем в `static/covers/`, аннотации из markdown-файлов). `afisha.py` учится читать реальный CSV с строками-пояснениями и новыми колонками. Два новых шаблона; навигация возвращается.

**Tech Stack:** Python 3.9, Markdown, python-frontmatter==1.0.1, Jinja2, pytest — стек сайта без изменений.

**Spec:** `docs-project/specs/2026-08-31-prochitano-library-design.md`

## Global Constraints

- Корень: `/Users/xenitch/umkultura-site`; вызовы `.venv/bin/python`, `.venv/bin/pytest` из корня; Python 3.9.
- Тексты интерфейса, ровно так: навигация «Будущие чтения · Прочитано»; кикер «Прочитано»; блоки «О книге» и «Чтения и обсуждения»; «Рецензия клуба →»; «← Ко всем прочитанным книгам»; счётчик «{N} {книга|книги|книг} прочитано клубами с августа 2026».
- Палитра: бумага `#f7f2e6`, чернила `#26221c`, индиго `#2b3a67`, терракота `#a34a2e`, золото `#b08d3f`, приглушённый `#6d6152`; заглушки обложек: слива `#4a2b4d`, индиго `#2b3a67`, терракота `#a34a2e`, зелёный `#1f4a38`, чернильный `#4d3b28`.
- Jinja2 `autoescape=False` — все данные таблицы и frontmatter в шаблонах через `| e`; исключение — заранее отрендеренный markdown (`page.content`, `book.about`).
- Колонки таблицы ищутся по вхождению подстроки в название (регистронезависимо): обложка «обложк», резюме «резюме», рецензия «реценз», ссылка клуба «ссылка»+«клуб» либо «контакт».
- Голосования (`is_vote`) не попадают в книги.
- TDD: тесты → RED → реализация → GREEN; полный прогон `.venv/bin/pytest -q` как evidence. Сейчас 37 тестов.
- Коммиты небольшие, после каждого зелёного цикла.

---

### Task 1: afisha.py — реальный CSV: преамбула, строки-пояснения, sanity-check

**Files:**
- Modify: `afisha.py` (load_events, fetch_csv)
- Test: `tests/test_afisha.py` (добавить в конец)

**Interfaces:**
- Consumes: текущие `load_events(csv_text)`, `fetch_csv(cache_path, url, timeout)`.
- Produces: `load_events` понимает CSV, где шапка «Дата обсуждения…» — не первая строка (ищется в первых 10), а строки с пустыми «Дата обсуждения»+«Книга»+«год» молча пропускаются в любом месте. Номера строк в ошибках соответствуют реальному листу. `fetch_csv` ищет «Дата обсуждения» в первых 10 строках ответа.

- [ ] **Step 1: Падающие тесты (добавить в tests/test_afisha.py)**

```python
CSV_REAL = """,,,,,,"НЕОБЯЗАТЕЛЬНО! Для страницы «Прочитано»",,
Дата обсуждения,Книга,Автор,В каком клубе обсуждают,Ссылка на клуб,год (для определения архива),Ссылка на обложку,Резюме обсуждения,Ссылка на рецензию
,,,,,,ссылка на картинку,"краткий текст, до 300 символов",публикация клуба
11 августа,«Элегантность ёжика»,Мюриель Барбери,Это просто книжный клуб,https://vk.ru/prosto_book_club,2026,https://example.com/hedgehog.jpg,"Говорили о невидимых людях",https://vk.ru/wall-1_1
август,«Мартин Иден»,Джек Лондон,Клуб нескучных чтений,https://libertrino.ru,2026,,,
6 октября,будет голосование в группе клуба,,Это просто книжный клуб,https://vk.ru/prosto_book_club,2026,,,
"""


def test_преамбула_над_шапкой_не_мешает():
    events = afisha.load_events(CSV_REAL)
    assert len(events) == 3
    assert events[0].book == "«Элегантность ёжика»"


def test_строка_пояснений_под_шапкой_пропускается():
    events = afisha.load_events(CSV_REAL)
    assert all(e.club for e in events)  # пояснения не стали событием


def test_номер_строки_считается_от_реального_листа():
    bad = CSV_REAL + "потом,«Книга»,Автор,Клуб,https://example.com,2026,,,\n"
    with pytest.raises(AfishaError, match="строка 7"):
        afisha.load_events(bad)


def test_шапка_не_нашлась_в_10_строках():
    with pytest.raises(AfishaError, match="не нашлась шапка"):
        afisha.load_events("а,б\nв,г\n")


def test_fetch_принимает_csv_с_преамбулой(tmp_path, monkeypatch):
    monkeypatch.setattr(afisha.urllib.request, "urlopen",
                        lambda url, timeout: _FakeResponse(CSV_REAL.encode("utf-8")))
    cache = tmp_path / "afisha.csv"
    assert afisha.fetch_csv(cache) == CSV_REAL     # не принял за мусор
    assert cache.read_text(encoding="utf-8") == CSV_REAL
```

- [ ] **Step 2: RED**

Run: `cd /Users/xenitch/umkultura-site && .venv/bin/pytest -q`
Expected: `test_преамбула…`, `test_номер_строки…`, `test_шапка…`, `test_fetch_принимает…` падают (сейчас первая строка считается шапкой, а fetch отвергает такой CSV).

- [ ] **Step 3: Реализация**

В `load_events` перед `csv.DictReader` найти шапку, реиндексировать номера строк; добавить пропуск строк-пояснений. Заменить начало функции:

```python
def load_events(csv_text):
    lines = csv_text.splitlines(keepends=True)
    header_at = next((i for i, ln in enumerate(lines[:10])
                      if "Дата обсуждения" in ln), None)
    if header_at is None:
        raise AfishaError("не нашлась шапка «Дата обсуждения» в первых 10 строках")
    events = []
    ended = False  # первая пустая строка объявляет таблицу событий закрытой
    reader = csv.DictReader(io.StringIO("".join(lines[header_at:])))
    for i, raw_row in enumerate(reader, start=header_at + 2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items()}
        year_key = next((k for k in row if k.lower().startswith("год")), "")
        if not any(row.values()):
            ended = True
            continue
        if not (row.get("Дата обсуждения", "") or row.get("Книга", "")
                or row.get(year_key, "")):
            continue  # строка-пояснение для модераторов — не событие
        ...  # дальше без изменений (ветка ended, разбор события)
```

(остальное тело цикла не меняется). В `fetch_csv` заменить sanity-check:

```python
        head = "\n".join(text.split("\n")[:10])
        if "Дата обсуждения" not in head:
            raise ValueError("непохоже на CSV афиши")
```

- [ ] **Step 4: GREEN**

Run: `.venv/bin/pytest -q`
Expected: 42 passed

- [ ] **Step 5: Commit**

```bash
git add afisha.py tests/test_afisha.py
git commit -m "feat: разбор реального CSV — преамбула и строки-пояснения модераторов"
```

---

### Task 2: afisha.py — новые поля события (обложка, резюме, рецензия)

**Files:**
- Modify: `afisha.py` (Event, load_events)
- Test: `tests/test_afisha.py` (добавить в конец)

**Interfaces:**
- Consumes: `load_events`, `CSV_REAL` из Task 1.
- Produces: `Event` получает поля `cover_url: str = ""`, `summary: str = ""`, `review_url: str = ""`; хелпер `_find(row, *needles) -> str` — значение первой колонки, чьё имя (lower) содержит все подстроки; `contact` ищется как `_find(row, "ссылка", "клуб") or _find(row, "контакт")` (больше не путается с «Ссылкой на обложку»).

- [ ] **Step 1: Падающие тесты (добавить в tests/test_afisha.py)**

```python
def test_новые_поля_обсуждения():
    e = afisha.load_events(CSV_REAL)[0]
    assert e.cover_url == "https://example.com/hedgehog.jpg"
    assert e.summary == "Говорили о невидимых людях"
    assert e.review_url == "https://vk.ru/wall-1_1"
    assert e.contact == "https://vk.ru/prosto_book_club"   # не спутал с обложкой


def test_новые_поля_пустые_по_умолчанию():
    e = afisha.load_events(CSV_REAL)[1]
    assert (e.cover_url, e.summary, e.review_url) == ("", "", "")
```

- [ ] **Step 2: RED**

Run: `.venv/bin/pytest -q` — Expected: 2 новых FAIL (нет атрибута cover_url)

- [ ] **Step 3: Реализация**

В `afisha.py` добавить перед `load_events`:

```python
def _find(row, *needles):
    for k, v in row.items():
        kl = k.lower()
        if all(n in kl for n in needles):
            return v
    return ""
```

В dataclass `Event` добавить в конец полей:

```python
    cover_url: str = ""
    summary: str = ""
    review_url: str = ""
```

В `load_events` заменить `contact=next((...))` и дополнить конструктор:

```python
            contact=_find(row, "ссылка", "клуб") or _find(row, "контакт"),
            cover_url=_find(row, "обложк"),
            summary=_find(row, "резюме"),
            review_url=_find(row, "реценз"),
```

- [ ] **Step 4: GREEN**

Run: `.venv/bin/pytest -q` — Expected: 44 passed

- [ ] **Step 5: Commit**

```bash
git add afisha.py tests/test_afisha.py
git commit -m "feat: события несут обложку, резюме и рецензию из новых колонок"
```

---

### Task 3: library.py — нормализация названий и слаги

**Files:**
- Create: `library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Produces: `normalize_title(title: str) -> str` (без кавычек, нижний регистр, е вместо ё, схлопнутые пробелы); `slugify(title: str) -> str` (транслит, дефисы); `placeholder_style(slug: str) -> str` — один из `"plum" | "indigo" | "terra" | "green" | "ink"`, детерминированно по crc32 слага.

- [ ] **Step 1: Падающие тесты**

`tests/test_library.py`:
```python
import pytest

import library


def test_normalize_убирает_кавычки_и_регистр():
    assert library.normalize_title("«Элегантность Ёжика»") == "элегантность ежика"
    assert library.normalize_title(" Мартин   Иден ") == "мартин иден"


def test_одинаковые_книги_совпадают():
    assert (library.normalize_title("«Мартин Иден»")
            == library.normalize_title("Мартин Иден"))


def test_slugify_транслит():
    assert library.slugify("«Элегантность ёжика»") == "elegantnost-ezhika"
    assert library.slugify("«Отверженные», том 1") == "otverzhennye-tom-1"
    assert library.slugify("«Кваzи» и «КайноZой»") == "kvazi-i-kaynozoy"


def test_placeholder_style_детерминирован():
    s = library.placeholder_style("elegantnost-ezhika")
    assert s in ("plum", "indigo", "terra", "green", "ink")
    assert s == library.placeholder_style("elegantnost-ezhika")
```

- [ ] **Step 2: RED**

Run: `.venv/bin/pytest -q` — Expected: ошибка импорта `library`

- [ ] **Step 3: Реализация**

`library.py`:
```python
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
    s = re.sub(r'[«»"„“]', "", title)
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
```

- [ ] **Step 4: GREEN**

Run: `.venv/bin/pytest -q` — Expected: 48 passed

- [ ] **Step 5: Commit**

```bash
git add library.py tests/test_library.py
git commit -m "feat: library — нормализация названий, слаги, стиль заглушки"
```

---

### Task 4: library.py — книги из событий, витринные группы, подписи

**Files:**
- Modify: `library.py` (добавить в конец)
- Test: `tests/test_library.py` (добавить в конец)

**Interfaces:**
- Consumes: `Event` (Task 2), `normalize_title`, `slugify`, `placeholder_style`, `_sort_key`, `MONTH_TITLE`.
- Produces:
  - `Book` dataclass: `title, author, slug, cover_url: str; discussions: list; style: str; cover_file: str = ""; about: str = ""; clubs_caption: str = ""`;
  - `group_books(past_events) -> list[Book]` — по нормализованному названию, обсуждения внутри книги старые→новые, книги отсортированы по последнему обсуждению (свежие первыми), обложка — первая непустая, коллизия слагов разных книг → `AfishaError`;
  - `group_showcase(books, today) -> list[(label, [Book])]` — группы по месяцу последнего обсуждения («Август» / «Январь 2027»);
  - `ru_plural(n, one, few, many) -> str`;
  - `clubs_caption(book) -> str` — имя клуба или «N клуба/клубов»;
  - `discussion_date(event) -> str` — «11 августа 2026», для месяца без дат «август 2026»;
  - `counter_text(n) -> str` — «8 книг прочитано клубами с августа 2026».

- [ ] **Step 1: Падающие тесты (добавить в tests/test_library.py)**

```python
from datetime import date

import afisha
from afisha import AfishaError


def _ev(book, raw, club="Клуб", author="Автор", year=2026, cover=""):
    return afisha.Event(book=book, author=author, club=club, contact="https://x",
                        year=year, when=afisha.parse_date_field(raw),
                        cover_url=cover)


def test_group_books_объединяет_обсуждения():
    events = [_ev("«Ёжик»", "3 октября", club="Час души"),
              _ev("Ёжик", "11 августа", club="Это просто книжный клуб",
                  cover="https://example.com/c.jpg")]
    books = library.group_books(events)
    assert len(books) == 1
    b = books[0]
    assert [d.when.display for d in b.discussions] == ["11 августа", "3 октября"]
    assert b.cover_url == "https://example.com/c.jpg"   # первая непустая
    assert b.title == "Ёжик"   # титул — из первого обсуждения по хронологии
    assert b.slug == "ezhik"


def test_books_сортируются_по_последнему_обсуждению():
    books = library.group_books([_ev("А", "11 августа"), _ev("Б", "5 сентября")])
    assert [b.title for b in books] == ["Б", "А"]


def test_showcase_группы_по_месяцам():
    books = library.group_books([_ev("А", "11 августа"), _ev("Б", "5 сентября"),
                                 _ev("В", "январь", year=2027)])
    groups = library.group_showcase(books, date(2026, 10, 1))
    assert [g[0] for g in groups] == ["Январь 2027", "Сентябрь", "Август"]


def test_ru_plural():
    p = lambda n: library.ru_plural(n, "книга", "книги", "книг")
    assert (p(1), p(2), p(5), p(11), p(21)) == (
        "книга", "книги", "книг", "книг", "книга")


def test_clubs_caption():
    one = library.group_books([_ev("А", "11 августа", club="Час души")])[0]
    two = library.group_books([_ev("Б", "11 августа", club="Час души"),
                               _ev("Б", "5 сентября", club="Между строк")])[0]
    assert library.clubs_caption(one) == "Час души"
    assert library.clubs_caption(two) == "2 клуба"


def test_discussion_date():
    assert library.discussion_date(_ev("А", "11 августа")) == "11 августа 2026"
    assert library.discussion_date(_ev("А", "август")) == "август 2026"


def test_counter_text():
    assert library.counter_text(8) == "8 книг прочитано клубами с августа 2026"
```

- [ ] **Step 2: RED**

Run: `.venv/bin/pytest -q` — Expected: новые FAIL (`group_books` не определена)

- [ ] **Step 3: Реализация (добавить в library.py)**

```python
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
```

- [ ] **Step 4: GREEN**

Run: `.venv/bin/pytest -q` — Expected: 55 passed

- [ ] **Step 5: Commit**

```bash
git add library.py tests/test_library.py
git commit -m "feat: группировка прочитанных книг и витринные подписи"
```

---

### Task 5: library.py — скачивание обложек с кешем

**Files:**
- Modify: `library.py` (добавить в конец)
- Test: `tests/test_library.py` (добавить в конец)

**Interfaces:**
- Produces: `fetch_cover(url: str, slug: str, covers_dir: Path, timeout=20) -> Path | None` — если в `covers_dir` уже есть `{slug}.*`, возвращает его не скачивая; пустой url → None; скачивает, расширение по Content-Type (`image/jpeg→jpg, image/png→png, image/webp→webp`), другой тип или сетевая ошибка → предупреждение в stderr и None (сборка не падает).

- [ ] **Step 1: Падающие тесты (добавить в tests/test_library.py)**

```python
import io as _io


class _Resp(_io.BytesIO):
    def __init__(self, data, ctype="image/jpeg"):
        super().__init__(data)
        self._ctype = ctype

    @property
    def headers(self):
        class H:
            def __init__(self, ct): self._ct = ct
            def get_content_type(self): return self._ct
        return H(self._ctype)

    def __enter__(self): return self

    def __exit__(self, *a): pass


def test_fetch_cover_скачивает_и_кеширует(tmp_path, monkeypatch):
    calls = []
    def fake(url, timeout):
        calls.append(url)
        return _Resp(b"JPEG", "image/jpeg")
    monkeypatch.setattr(library.urllib.request, "urlopen", fake)
    p = library.fetch_cover("https://x/c.jpg", "ezhik", tmp_path)
    assert p.name == "ezhik.jpg" and p.read_bytes() == b"JPEG"
    p2 = library.fetch_cover("https://x/c.jpg", "ezhik", tmp_path)
    assert p2 == p and calls == ["https://x/c.jpg"]   # второй раз не качал


def test_fetch_cover_без_ссылки():
    assert library.fetch_cover("", "ezhik", Path("/nonexistent")) is None


def test_fetch_cover_плохой_тип_и_сеть(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(library.urllib.request, "urlopen",
                        lambda url, timeout: _Resp(b"<html>", "text/html"))
    assert library.fetch_cover("https://x/page", "a", tmp_path) is None
    def boom(url, timeout):
        raise OSError("нет сети")
    monkeypatch.setattr(library.urllib.request, "urlopen", boom)
    assert library.fetch_cover("https://x/c.jpg", "b", tmp_path) is None
    err = capsys.readouterr().err
    assert "обложка" in err
```

- [ ] **Step 2: RED**

Run: `.venv/bin/pytest -q` — Expected: 3 новых FAIL

- [ ] **Step 3: Реализация (добавить в library.py)**

```python
COVER_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def fetch_cover(url, slug, covers_dir, timeout=20):
    covers_dir = Path(covers_dir)
    for existing in sorted(covers_dir.glob(f"{slug}.*")):
        return existing
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            ext = COVER_TYPES.get(resp.headers.get_content_type())
            if not ext:
                print(f"⚠ обложка {slug}: неожиданный тип содержимого ({url})",
                      file=sys.stderr)
                return None
            data = resp.read()
    except OSError:
        print(f"⚠ обложка {slug}: не скачалась ({url})", file=sys.stderr)
        return None
    covers_dir.mkdir(parents=True, exist_ok=True)
    path = covers_dir / f"{slug}.{ext}"
    path.write_bytes(data)
    return path
```

- [ ] **Step 4: GREEN**

Run: `.venv/bin/pytest -q` — Expected: 58 passed

- [ ] **Step 5: Commit**

```bash
git add library.py tests/test_library.py
git commit -m "feat: скачивание обложек с кешем в static/covers"
```

---

### Task 6: Шаблоны, CSS, навигация, сборка раздела

**Files:**
- Create: `templates/library.html`, `templates/book.html`, `content/bookclubs/library/index.md`
- Modify: `build.py`, `templates/base.html`, `static/style.css`
- Delete: `templates/archive.html`, `drafts/bookclubs-archive.md`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: всё из Tasks 1–5.
- Produces: `build.build(root, today=None, fetch=afisha.fetch_csv)` дополнительно рендерит `/bookclubs/library/` и `/bookclubs/library/{slug}/`. Аннотации: `content/bookclubs/library/{slug}.md` (frontmatter `title`, `author`; тело — markdown «О книге») исключаются из обычного цикла страниц; их frontmatter переопределяет титул/автора книги. Обсуждения передаются в шаблон списком словарей `{"date", "club", "contact", "summary", "review_url"}`.

- [ ] **Step 1: Обновить tests/test_build.py (падающие тесты)**

Заменить содержимое `tests/test_build.py` целиком:

```python
from datetime import date
from pathlib import Path
import shutil

import build
from test_afisha import CSV_REAL

ROOT = Path(__file__).resolve().parent.parent


def _make_project(tmp_path):
    for name in ("content", "templates", "static"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return tmp_path


def test_полная_сборка(tmp_path):
    root = _make_project(tmp_path)
    ann = root / "content/bookclubs/library/elegantnost-ezhika.md"
    ann.write_text("---\ntitle: «Элегантность ёжика»\nauthor: Мюриель Барбери\n---\n"
                   "Роман о консьержке-философе.\n", encoding="utf-8")
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL)
    out = root / "docs"
    for page in ("", "bookclubs", "bookclubs/library",
                 "bookclubs/library/elegantnost-ezhika",
                 "bookclubs/library/martin-iden"):
        assert (out / page / "index.html").exists(), page
    assert not (out / "bookclubs/archive").exists()
    assert (out / "CNAME").read_text(encoding="utf-8") == "umkultura.ru"

    home = (out / "index.html").read_text(encoding="utf-8")
    assert "site-nav" not in home                        # заглавная — без навигации

    schedule = (out / "bookclubs/index.html").read_text(encoding="utf-8")
    assert "Прочитано</a>" in schedule                   # навигация вернулась
    assert "Книгу выберут голосованием" in schedule

    lib = (out / "bookclubs/library/index.html").read_text(encoding="utf-8")
    assert "2 книги прочитано клубами с августа 2026" in lib
    assert "cover-ph" in lib                             # заглушка (обложки не качаем)
    assert "elegantnost-ezhika" in lib

    bookpage = (out / "bookclubs/library/elegantnost-ezhika/index.html").read_text(encoding="utf-8")
    assert "О книге" in bookpage and "консьержке-философе" in bookpage
    assert "Чтения и обсуждения" in bookpage
    assert "11 августа 2026" in bookpage
    assert "Говорили о невидимых людях" in bookpage
    assert "Рецензия клуба" in bookpage
    assert "← Ко всем прочитанным книгам" in bookpage

    martin = (out / "bookclubs/library/martin-iden/index.html").read_text(encoding="utf-8")
    assert "О книге" not in martin                       # нет аннотации — нет блока
    assert "август 2026" in martin


def test_голосования_не_в_библиотеке(tmp_path):
    root = _make_project(tmp_path)
    build.build(root, today=date(2027, 1, 1), fetch=lambda cache: CSV_REAL)
    lib = (root / "docs/bookclubs/library/index.html").read_text(encoding="utf-8")
    assert "Книгу выберут голосованием" not in lib


def test_обложки_не_скачиваются_в_тестах_и_кеш_работает(tmp_path):
    root = _make_project(tmp_path)
    covers = root / "static/covers"
    covers.mkdir()
    (covers / "elegantnost-ezhika.jpg").write_bytes(b"JPEG")   # кеш вместо сети
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL)
    lib = (root / "docs/bookclubs/library/index.html").read_text(encoding="utf-8")
    assert "/static/covers/elegantnost-ezhika.jpg" in lib
    assert (root / "docs/static/covers/elegantnost-ezhika.jpg").exists()


def test_пересборка_убирает_устаревшее(tmp_path):
    root = _make_project(tmp_path)
    stale = root / "docs" / "старое" / "index.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("устарело", encoding="utf-8")
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL)
    assert not stale.exists()
```

Примечание: в CSV_REAL у «Элегантности ёжика» есть cover_url → в `test_полная_сборка` сеть НЕ должна дёргаться. Для этого в `build.build` скачивание обложек выполняется через параметр `cover_fetch=library.fetch_cover`, а тест передаёт... НЕТ — проще: тест полной сборки полагается на то, что `fetch_cover` при недоступной сети вернёт None с предупреждением (обложка станет заглушкой). Чтобы тест был герметичным и быстрым, добавить `build.build(..., cover_fetch=...)` с дефолтом `library.fetch_cover` и передавать в тестах `cover_fetch=lambda url, slug, d: None` — КРОМЕ `test_обложки_не_скачиваются…`, где передать настоящий `library.fetch_cover` (сработает кеш, сеть не нужна). Обновить вызовы в тестах соответственно:

```python
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL,
                cover_fetch=lambda url, slug, d: None)
```
(во всех тестах, кроме `test_обложки_…`, где `cover_fetch=library.fetch_cover`; добавить `import library` в шапку test_build.py).

- [ ] **Step 2: RED**

Run: `.venv/bin/pytest -q` — Expected: test_build падает (нет library.html и т.д.)

- [ ] **Step 3: Шаблоны и контент**

`templates/library.html`:
```html
{% extends "base.html" %}
{% block content %}
<article class="prose">
  <header class="page-header">
    <p class="kicker">{{ page.meta.kicker | e }}</p>
    <h1>{{ page.meta.title | e }}</h1>
  </header>
  {{ page.content }}
  <p class="lib-counter">{{ library_counter | e }}</p>
</article>
<section class="showcase">
  {% for label, books in showcase_groups %}
  <h2 class="toc-month">{{ label }}</h2>
  <div class="shelf-grid">
    {% for b in books %}
    <a class="shelf-cell" href="/bookclubs/library/{{ b.slug }}/">
      {% if b.cover_file %}<img class="cover-img" src="{{ b.cover_file }}" alt="{{ b.title | e }}">
      {% else %}<span class="cover-ph ph-{{ b.style }}"><span class="ph-t">{{ b.title | e }}</span>
        {% if b.author %}<span class="ph-a">{{ b.author | e }}</span>{% endif %}
        <span class="ph-orn">❦</span></span>{% endif %}
      <span class="cell-title">{{ b.title | e }}</span>
      <span class="cell-club">{{ b.clubs_caption | e }}</span>
    </a>
    {% endfor %}
  </div>
  {% endfor %}
  <p class="fleuron">❦</p>
</section>
{% endblock %}
```

`templates/book.html`:
```html
{% extends "base.html" %}
{% block content %}
<article class="prose book">
  <header class="page-header">
    <p class="kicker">Прочитано</p>
    <h1>{{ book.title | e }}</h1>
    {% if book.author %}<p class="book-author">{{ book.author | e }}</p>{% endif %}
  </header>
  <div class="spread">
    <div class="spread-cover">
      {% if book.cover_file %}<img class="cover-img" src="{{ book.cover_file }}" alt="{{ book.title | e }}">
      {% else %}<span class="cover-ph ph-{{ book.style }}"><span class="ph-t">{{ book.title | e }}</span>
        {% if book.author %}<span class="ph-a">{{ book.author | e }}</span>{% endif %}
        <span class="ph-orn">❦</span></span>{% endif %}
    </div>
    <div class="spread-body">
      {% if book.about %}
      <h2 class="sect">О книге</h2>
      <div class="about">{{ book.about }}</div>
      {% endif %}
      <h2 class="sect">Чтения и обсуждения</h2>
      {% for d in discussions %}
      <div class="disc">
        <p class="disc-head"><span class="disc-date">{{ d.date | e }}</span> · <a href="{{ d.contact | e }}">{{ d.club | e }}</a></p>
        {% if d.summary %}<p class="disc-summary">{{ d.summary | e }}</p>{% endif %}
        {% if d.review_url %}<p class="disc-review"><a href="{{ d.review_url | e }}">Рецензия клуба →</a></p>{% endif %}
      </div>
      {% endfor %}
    </div>
  </div>
  <p class="backlink"><a href="/bookclubs/library/">← Ко всем прочитанным книгам</a></p>
  <p class="fleuron">❦</p>
</article>
{% endblock %}
```

`content/bookclubs/library/index.md`:
```markdown
---
title: Что прочитал Кемерово
kicker: Прочитано
template: library.html
description: Книги, которые уже обсудили книжные клубы Кемерова, — с обложками, резюме встреч и рецензиями клубов.
---
Каждая книга здесь — прошедшая встреча одного из клубов города.
Нажмите на обложку, чтобы узнать, кто и когда её обсуждал.
```

`templates/base.html` — заменить закомментированный блок навигации на:
```html
    <nav class="site-nav">
      <a href="/bookclubs/"{% if page.url == '/bookclubs/' %} class="current"{% endif %}>Будущие чтения</a> ·
      <a href="/bookclubs/library/"{% if page.url.startswith('/bookclubs/library/') %} class="current"{% endif %}>Прочитано</a>
    </nav>
```

Удалить `templates/archive.html` и `drafts/bookclubs-archive.md` (`git rm`).

- [ ] **Step 4: CSS (добавить в конец static/style.css)**

```css
/* «Прочитано»: витрина */
.lib-counter { color: var(--muted); font-size: 0.9em; }
.shelf-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
  gap: 1.4rem 1rem; margin: 1rem 0 2rem; }
.shelf-cell { display: block; text-decoration: none; color: inherit; }
.cover-img { width: 100%; aspect-ratio: 2/3; object-fit: cover;
  border-radius: 2px 5px 5px 2px;
  box-shadow: inset 6px 0 8px -6px rgba(0,0,0,.45), 2px 3px 6px rgba(43,33,24,.25); }
.cover-ph { width: 100%; aspect-ratio: 2/3; border-radius: 2px 5px 5px 2px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 8% 9%; box-sizing: border-box; position: relative;
  box-shadow: inset 6px 0 8px -6px rgba(0,0,0,.45), 2px 3px 6px rgba(43,33,24,.25); }
.cover-ph::before { content: ""; position: absolute; inset: 5% 6%;
  border: 1px solid rgba(176,141,63,.75); pointer-events: none; }
.ph-plum { background: linear-gradient(105deg, #4a2b4d, #3a2140); }
.ph-indigo { background: linear-gradient(105deg, #2b3a67, #1f2b50); }
.ph-terra { background: linear-gradient(105deg, #a34a2e, #7c3722); }
.ph-green { background: linear-gradient(105deg, #1f4a38, #143327); }
.ph-ink { background: linear-gradient(105deg, #4d3b28, #362818); }
.cover-ph .ph-t { font-family: "Old Standard TT", serif; font-weight: 700;
  font-size: 0.85rem; line-height: 1.25; color: #f0e6c8; }
.cover-ph .ph-a { font-family: "Old Standard TT", serif; font-style: italic;
  font-size: 0.7rem; color: rgba(240,230,200,.75); margin-top: 0.4em; }
.cover-ph .ph-orn { color: var(--gold); font-size: 0.8rem; margin-top: 0.5em; }
.cell-title { display: block; font-family: "Old Standard TT", serif; font-weight: 700;
  font-size: 0.85rem; line-height: 1.2; margin-top: 0.5em; }
.cell-club { display: block; font-size: 0.75rem; color: var(--muted); font-style: italic; }

/* «Прочитано»: страница книги */
.book-author { font-family: "Old Standard TT", serif; font-style: italic;
  color: var(--muted); font-size: 1.15rem; margin: 0.2em 0 0; }
.spread { display: flex; gap: 1.5rem; margin-top: 1.2rem; }
.spread-cover { width: 30%; flex-shrink: 0; }
.spread-body { flex: 1; min-width: 0; }
.sect { font-variant-caps: all-small-caps; letter-spacing: 0.12em; color: var(--terra);
  font-size: 1rem; font-weight: 400; margin: 1.2em 0 0.4em; }
.spread-body .sect:first-child { margin-top: 0; }
.about > p:first-of-type::first-letter { font-family: "Old Standard TT", serif;
  font-size: 2.6em; float: left; line-height: 0.85; padding: 0.05em 0.1em 0 0;
  color: var(--indigo); }
.disc { border-top: 1px solid rgba(176,141,63,.45); padding: 0.6em 0 0.4em; }
.disc-head { margin: 0; }
.disc-date { color: var(--indigo); font-variant-caps: all-small-caps; }
.disc-head a { color: var(--muted); }
.disc-summary { margin: 0.3em 0; }
.disc-review { margin: 0.2em 0; font-size: 0.9em; }
@media (max-width: 40rem) {
  .spread { flex-direction: column; }
  .spread-cover { width: 60%; margin: 0 auto; }
}
```

- [ ] **Step 5: build.py — интеграция**

Заменить `build()` (и добавить `import library` в шапку):

```python
def build(root: Path, today=None, fetch=afisha.fetch_csv,
          cover_fetch=None) -> None:
    if cover_fetch is None:
        cover_fetch = library.fetch_cover
    today = today or date.today()
    content_dir, out = root / "content", root / "docs"
    lib_dir = content_dir / "bookclubs" / "library"

    events = afisha.load_events(fetch(root / "data" / "afisha.csv"))
    upcoming, past = afisha.split_events(events, today)
    books = library.group_books(past)
    for b in books:
        cover = cover_fetch(b.cover_url, b.slug, root / "static" / "covers")
        b.cover_file = f"/static/covers/{cover.name}" if cover else ""
        b.clubs_caption = library.clubs_caption(b)
        ann = lib_dir / f"{b.slug}.md"
        if ann.exists():
            post = frontmatter.load(ann)
            b.title = post.metadata.get("title", b.title)
            b.author = post.metadata.get("author", b.author)
            b.about = render_md(post.content)
        else:
            print(f"⚠ нет аннотации: {b.slug}", file=sys.stderr)

    ctx = {
        "site": SITE,
        "schedule_groups": afisha.group_schedule(upcoming, today),
        "showcase_groups": library.group_showcase(books, today),
        "library_counter": library.counter_text(len(books)),
    }

    env = Environment(loader=FileSystemLoader(root / "templates"), autoescape=False)
    pages = [load_page(p, content_dir) for p in sorted(content_dir.rglob("*.md"))
             if not (p.parent == lib_dir and p.name != "index.md")]

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

    for b in books:
        page = {"url": f"/bookclubs/library/{b.slug}/",
                "meta": {"title": b.title,
                         "description": f"{b.title} — обсуждения в книжных клубах Кемерова"},
                "content": ""}
        discussions = [{"date": library.discussion_date(d), "club": d.club,
                        "contact": d.contact, "summary": d.summary,
                        "review_url": d.review_url} for d in b.discussions]
        html = env.get_template("book.html").render(
            page=page, book=b, discussions=discussions, **ctx)
        dest = out / page["url"].strip("/") / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
```

Добавить `import sys` в шапку build.py (для предупреждений).

- [ ] **Step 6: GREEN**

Run: `.venv/bin/pytest -q` — Expected: 60 passed (58 + 4 в test_build вместо 2 старых)

- [ ] **Step 7: Commit**

```bash
git rm -q templates/archive.html drafts/bookclubs-archive.md
git add build.py templates content static/style.css tests/test_build.py
git commit -m "feat: раздел «Прочитано» — витрина, страницы книг, навигация"
```

---

### Task 7: Аннотации прочитанных книг и первая сборка

**Files:**
- Create: `content/bookclubs/library/{slug}.md` — по файлу на прочитанную книгу

**Interfaces:**
- Consumes: сборка из Task 6; формат аннотации: frontmatter `title` (красивое название с «ёлочками»), `author`; тело — 2–4 фразы.

- [ ] **Step 1: Выяснить актуальный список прочитанных книг**

Run: `cd /Users/xenitch/umkultura-site && .venv/bin/python build.py 2>&1 | grep "нет аннотации" || true`
Каждая строка «⚠ нет аннотации: {slug}» — книга, которой нужен файл.

- [ ] **Step 2: Создать аннотации (тексты готовы)**

`content/bookclubs/library/elegantnost-ezhika.md`:
```markdown
---
title: «Элегантность ёжика»
author: Мюриель Барбери
---
Консьержка парижского дома Рене прячет от жильцов свою любовь к философии
и русской литературе, а двенадцатилетняя Палома — решимость не жить по
правилам взрослых. Роман о том, как два одиноких ума узнают друг друга.
Бестселлер 2006 года, переведённый на десятки языков.
```

`content/bookclubs/library/gordost-i-predubezhdenie.md`:
```markdown
---
title: «Гордость и предубеждение»
author: Джейн Остин
---
Элизабет Беннет и мистер Дарси проходят путь от взаимной неприязни
к пониманию — через гордость, предубеждение и пять сестёр на выданье.
Самый известный роман Джейн Остин (1813) и одна из самых любимых
историй английской литературы.
```

`content/bookclubs/library/martin-iden.md`:
```markdown
---
title: «Мартин Иден»
author: Джек Лондон
---
Моряк Мартин Иден влюбляется в девушку из буржуазной семьи и решает
стать писателем. История о самообразовании, упорстве и цене успеха —
во многом автобиографичный роман Джека Лондона (1909).
```

`content/bookclubs/library/otverzhennye-tom-1.md`:
```markdown
---
title: «Отверженные», том 1
author: Виктор Гюго
---
Каторжник Жан Вальжан получает второй шанс и всю жизнь бежит от прошлого
и инспектора Жавера. Первый том эпопеи Виктора Гюго (1862) — о милосердии,
законе и справедливости на фоне Франции начала XIX века.
```

`content/bookclubs/library/voskresenie.md`:
```markdown
---
title: «Воскресение»
author: Лев Толстой
---
Князь Нехлюдов узнаёт в подсудимой Катюшу Маслову, которую когда-то
соблазнил и оставил, — и решает искупить вину. Последний роман
Льва Толстого (1899), беспощадный к суду, церкви и самому герою.
```

`content/bookclubs/library/kvazi-i-kaynozoy.md`:
```markdown
---
title: «Кваzи» и «КайноZой»
author: Сергей Лукьяненко
---
Мир после восстания мёртвых: человечество уживается с кваzи — разумными
и вполне цивилизованными бывшими людьми. Полицейский Денис Симонов
расследует дела на границе двух миров. Фантастическая дилогия (2016–2018)
о том, что делает человека человеком.
```
(в таблице автор указан «Андрей Лукьяненко» — это опечатка модератора,
автор дилогии Сергей Лукьяненко; frontmatter поправляет отображение,
таблицу не трогаем.)

Для «Забвения Фернана» (Ольга Ашмарова) достоверной информации может не быть
в свободном доступе: поискать в интернете (WebSearch) «Забвение Фернана
Ольга Ашмарова книга»; если находится внятное описание — написать 2 фразы
своими словами тем же форматом файла (`zabvenie-fernana.md`); если нет —
файл НЕ создавать, предупреждение при сборке допустимо (спека это разрешает).
Если Step 1 показал другие слаги (новые прочитанные книги) — по возможности
дописать аннотации им же по тому же рецепту; для незнакомых книг без
надёжных источников файл не создавать.

- [ ] **Step 3: Сборка и проверка**

Run: `.venv/bin/python build.py && .venv/bin/pytest -q`
Expected: «Собрано в docs/», тесты зелёные; предупреждений «нет аннотации»
не осталось (кроме сознательно пропущенных книг); в
`docs/bookclubs/library/index.html` есть все книги; страницы книг рендерятся.

Посмотреть глазами: `cd docs && python3 -m http.server 8899` →
http://localhost:8899/bookclubs/library/ (витрина, заглушки, страницы книг),
затем остановить сервер.

- [ ] **Step 4: Commit**

```bash
git add content data docs static
git commit -m "feat: аннотации прочитанных книг и первая сборка «Прочитано»"
```

Публикация (push в main) — на этапе финиша ветки, после финального ревью.
