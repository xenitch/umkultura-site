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
