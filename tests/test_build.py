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
    build.build(root, today=date(2026, 8, 1), fetch=lambda cache: CSV)
    out = root / "docs"
    for page in ("", "bookclubs"):
        assert (out / page / "index.html").exists(), page
    assert not (out / "bookclubs/schedule").exists()    # афиша живёт на /bookclubs/
    assert not (out / "bookclubs/archive").exists()     # библиотека скрыта до 10 августа
    assert (out / "CNAME").read_text(encoding="utf-8") == "umkultura.ru"
    assert (out / ".nojekyll").exists()
    assert (out / "static" / "style.css").exists()

    home = (out / "index.html").read_text(encoding="utf-8")
    assert "Пространство развития умственной" in home
    assert "site-nav" not in home                       # заглушка без навигации

    schedule = (out / "bookclubs/index.html").read_text(encoding="utf-8")
    assert "Что читает Кемерово" in schedule
    assert "Книгу выберут голосованием" in schedule     # будущая строка-голосование
    assert "«Элегантность ёжика»</span>, <span" in schedule   # запятая между книгой и автором


def test_пересборка_убирает_устаревшее(tmp_path):
    root = _make_project(tmp_path)
    stale = root / "docs" / "старое" / "index.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("устарело", encoding="utf-8")
    build.build(root, today=date(2026, 8, 1), fetch=lambda cache: CSV)
    assert not stale.exists()
