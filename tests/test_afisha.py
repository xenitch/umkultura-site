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
