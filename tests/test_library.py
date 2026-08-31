import pytest

from pathlib import Path

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


def test_normalize_убирает_фигурные_кавычки():
    assert library.normalize_title("\u201cЁжик\u201e") == "ежик"
    assert library.normalize_title("\u201dЁжик\u201d") == "ежик"

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


def test_пустой_слаг_даёт_ошибку():
    with pytest.raises(AfishaError):
        library.group_books([_ev("???", "11 августа")])


def test_fetch_cover_не_http_ссылка(tmp_path, capsys):
    assert library.fetch_cover("file:///etc/hosts", "x", tmp_path) is None
    assert "обложка" in capsys.readouterr().err
