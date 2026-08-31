from datetime import date
from pathlib import Path
import shutil

import build
import library
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
    # martin-iden теперь и в реальном content/ имеет аннотацию (Task 7);
    # здесь он нарочно остаётся без неё — проверяем ветку «нет аннотации».
    (root / "content/bookclubs/library/martin-iden.md").unlink(missing_ok=True)
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL,
                cover_fetch=lambda url, slug, d: None)
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
    build.build(root, today=date(2027, 1, 1), fetch=lambda cache: CSV_REAL,
                cover_fetch=lambda url, slug, d: None)
    lib = (root / "docs/bookclubs/library/index.html").read_text(encoding="utf-8")
    assert "Книгу выберут голосованием" not in lib


def test_обложки_не_скачиваются_в_тестах_и_кеш_работает(tmp_path):
    root = _make_project(tmp_path)
    covers = root / "static/covers"
    covers.mkdir()
    (covers / "elegantnost-ezhika.jpg").write_bytes(b"JPEG")   # кеш вместо сети
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL,
                cover_fetch=library.fetch_cover)
    lib = (root / "docs/bookclubs/library/index.html").read_text(encoding="utf-8")
    assert "/static/covers/elegantnost-ezhika.jpg" in lib
    assert (root / "docs/static/covers/elegantnost-ezhika.jpg").exists()


def test_пересборка_убирает_устаревшее(tmp_path):
    root = _make_project(tmp_path)
    stale = root / "docs" / "старое" / "index.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("устарело", encoding="utf-8")
    build.build(root, today=date(2026, 9, 1), fetch=lambda cache: CSV_REAL,
                cover_fetch=lambda url, slug, d: None)
    assert not stale.exists()
