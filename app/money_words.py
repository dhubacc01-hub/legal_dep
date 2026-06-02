from __future__ import annotations

UNITS_MALE = (
    "",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
)
UNITS_FEMALE = (
    "",
    "одна",
    "две",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
)
TEENS = (
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
)
TENS = (
    "",
    "",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
)
HUNDREDS = (
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
)
GROUP_FORMS = (
    ("", "", "", False),
    ("тысяча", "тысячи", "тысяч", True),
    ("миллион", "миллиона", "миллионов", False),
    ("миллиард", "миллиарда", "миллиардов", False),
)


def choose_plural(value: int, forms: tuple[str, str, str]) -> str:
    value = abs(value) % 100
    if 11 <= value <= 19:
        return forms[2]
    last_digit = value % 10
    if last_digit == 1:
        return forms[0]
    if 2 <= last_digit <= 4:
        return forms[1]
    return forms[2]


def triplet_to_words(value: int, *, female: bool) -> list[str]:
    words: list[str] = []
    words.append(HUNDREDS[value // 100])
    remainder = value % 100
    if 10 <= remainder <= 19:
        words.append(TEENS[remainder - 10])
    else:
        words.append(TENS[remainder // 10])
        units = UNITS_FEMALE if female else UNITS_MALE
        words.append(units[remainder % 10])
    return [word for word in words if word]


def number_to_words_ru(value: int) -> str:
    if value == 0:
        return "ноль"

    words: list[str] = []
    group_index = 0
    while value > 0:
        value, chunk = divmod(value, 1000)
        if chunk:
            forms = GROUP_FORMS[group_index] if group_index < len(GROUP_FORMS) else GROUP_FORMS[-1]
            words = triplet_to_words(chunk, female=forms[3]) + (
                [choose_plural(chunk, forms[:3])] if forms[0] else []
            ) + words
        group_index += 1
    return " ".join(words)


def money_to_words_ru(value: float | int | None) -> str:
    amount = round(float(value or 0), 2)
    integer_part = int(amount)
    decimal_part = int(round((amount - integer_part) * 100))
    tenge_words = choose_plural(integer_part, ("тенге", "тенге", "тенге"))
    if decimal_part:
        tiyn_words = choose_plural(decimal_part, ("тиын", "тиына", "тиын"))
        return f"{number_to_words_ru(integer_part)} {tenge_words} {decimal_part:02d} {tiyn_words}"
    return f"{number_to_words_ru(integer_part)} {tenge_words}"


def money_to_words_sum_ru(value: float | int | None) -> str:
    amount = round(float(value or 0), 2)
    integer_part = int(amount)
    decimal_part = int(round((amount - integer_part) * 100))
    sum_words = choose_plural(integer_part, ("сум", "сума", "сум"))
    if decimal_part:
        return f"{number_to_words_ru(integer_part)} {sum_words} {decimal_part:02d} тийин"
    return f"{number_to_words_ru(integer_part)} {sum_words}"
