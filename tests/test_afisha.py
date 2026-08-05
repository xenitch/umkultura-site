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
