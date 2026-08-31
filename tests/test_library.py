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
