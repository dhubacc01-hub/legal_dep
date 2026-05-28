from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

DEFAULT_COUNTRY = "kz"
SUPPORTED_COUNTRIES = ("kz", "uz")

CATEGORIES = [
    "Новый",
    "Готовим иск",
    "Иск подан",
    "Иск закрыт",
    "Оплата по претензии",
    "Клиент частично оплачивает",
    "Ожидаем ответа по претензии",
    "Возврат в работу Юр. Отдела",
    "Долг закрыт",
    "Неподсудно",
    "Прошел срок исковой давности",
    "Маленькая сумма долга",
    "Закрытая компания",
    "Не должник",
    "Требуется проверка решения в кабинете",
    "Передать на ЧСИ",
]

COMPANIES = [
    'TOO "Vip Events (Вип Ивентс)"',
    'TOO "Alma Swiss"',
    'TOO "Harbour Island"',
    'TOO "Ayna Sales"',
    'ТОО "AJ-store"',
    'ТОО "Tervis"',
    'ТОО "SMstore"',
    'ТОО "Silk-A"',
    'ТОО "Seda store"',
    'ТОО "Lyazza (Лязза)"',
    'ТОО "Akdeer"',
    'ТОО "AiSap (АйСап)"',
    'ТОО "Sap-store"',
    "\u0422\u041e\u041e \u00abBoggner\u00bb",
    'ТОО "Токит Казахстан"',
]

KAZAKHSTAN_COMPANIES = COMPANIES

UZBEKISTAN_COMPANIES = [
    "LLP SCM GROUP",
    "ООО «RRS RETAIL CITY»",
    "ООО «Concept Evolution»",
]

DECISIONS = [
    "Удовлетворить",
    "Частично",
    "По соглашению сторон",
    "Отказ в иске",
    "Возврат иска",
]

KAZAKHSTAN_CITIES = sorted(
    {
        "Абай",
        "Акколь",
        "Аксай",
        "Аксу",
        "Актау",
        "Актобе",
        "Алатау",
        "Алга",
        "Алматы",
        "Алтай",
        "Аральск",
        "Аркалык",
        "Арыс",
        "Астана",
        "Атасу",
        "Атбасар",
        "Атырау",
        "Аягоз",
        "Балхаш",
        "Байконур",
        "Булаево",
        "Державинск",
        "Ерейментау",
        "Есик",
        "Есиль",
        "Жанаозен",
        "Жанатас",
        "Жаркент",
        "Жезказган",
        "Жем",
        "Жетысай",
        "Житикара",
        "Зайсан",
        "Кандыагаш",
        "Караганда",
        "Каражал",
        "Каратау",
        "Каркаралинск",
        "Каскелен",
        "Кентау",
        "Кокшетау",
        "Конаев",
        "Косшы",
        "Костанай",
        "Кульсары",
        "Курчатов",
        "Кызылорда",
        "Ленгер",
        "Лисаковск",
        "Макинск",
        "Мамлютка",
        "Павлодар",
        "Петропавловск",
        "Приозерск",
        "Риддер",
        "Рудный",
        "Сарань",
        "Сарканд",
        "Сарыагаш",
        "Сатпаев",
        "Семей",
        "Сергеевка",
        "Серебрянск",
        "Степногорск",
        "Степняк",
        "Тайынша",
        "Талгар",
        "Талдыкорган",
        "Тараз",
        "Текели",
        "Темир",
        "Темиртау",
        "Тобыл",
        "Туран",
        "Туркестан",
        "Уральск",
        "Усть-Каменогорск",
        "Ушарал",
        "Уштобе",
        "Форт-Шевченко",
        "Хромтау",
        "Шалкар",
        "Шар",
        "Шардара",
        "Шахтинск",
        "Шемонаиха",
        "Шу",
        "Шымкент",
        "Щучинск",
        "Экибастуз",
        "Эмба",
    }
)

_COURT_PAIRS = [
    ("Астана", "Суд города Астаны"),
    ("Астана", "Межрайонный суд по гражданским делам города Астаны"),
    ("Астана", "Специализированный межрайонный экономический суд города Астаны"),
    ("Астана", "Алматинский районный суд города Астаны"),
    ("Астана", "Байконырский районный суд города Астаны"),
    ("Астана", "Есильский районный суд города Астаны"),
    ("Астана", "Нуринский районный суд города Астаны"),
    ("Астана", "Сарыаркинский районный суд города Астаны"),
    ("Алматы", "Алматинский городской суд"),
    ("Алматы", "Специализированный межрайонный экономический суд города Алматы"),
    ("Алматы", "Алмалинский районный суд города Алматы"),
    ("Алматы", "Ауэзовский районный суд города Алматы"),
    ("Алматы", "Бостандыкский районный суд города Алматы"),
    ("Алматы", "Жетысуский районный суд города Алматы"),
    ("Алматы", "Медеуский районный суд города Алматы"),
    ("Алматы", "Наурызбайский районный суд города Алматы"),
    ("Алматы", "Турксибский районный суд города Алматы"),
    ("Шымкент", "Суд города Шымкента"),
    ("Шымкент", "Межрайонный суд по гражданским делам города Шымкента"),
    ("Шымкент", "Специализированный межрайонный экономический суд города Шымкента"),
    ("Шымкент", "Абайский районный суд города Шымкента"),
    ("Шымкент", "Аль-Фарабийский районный суд города Шымкента"),
    ("Шымкент", "Енбекшинский районный суд города Шымкента"),
    ("Шымкент", "Каратауский районный суд города Шымкента"),
    ("Кокшетау", "Акмолинский областной суд"),
    ("Конаев", "Алматинский областной суд"),
    ("Актобе", "Актюбинский областной суд"),
    ("Атырау", "Атырауский областной суд"),
    ("Усть-Каменогорск", "Восточно-Казахстанский областной суд"),
    ("Тараз", "Жамбылский областной суд"),
    ("Талдыкорган", "Суд области Жетысу"),
    ("Уральск", "Западно-Казахстанский областной суд"),
    ("Караганда", "Карагандинский областной суд"),
    ("Костанай", "Костанайский областной суд"),
    ("Кызылорда", "Кызылординский областной суд"),
    ("Актау", "Мангистауский областной суд"),
    ("Павлодар", "Павлодарский областной суд"),
    ("Петропавловск", "Северо-Казахстанский областной суд"),
    ("Туркестан", "Туркестанский областной суд"),
    ("Семей", "Суд области Абай"),
    ("Жезказган", "Суд области Улытау"),
    ("Косшы", "Суд города Косшы"),
    ("Конаев", "Суд города Конаева"),
    ("Талдыкорган", "Суд города Талдыкоргана"),
    ("Семей", "Суд №2 города Семей"),
    ("Павлодар", "Суд города Павлодара"),
    ("Караганда", "Суд района имени Казыбек би города Караганды"),
    ("Караганда", "Суд района имени Алихана Бокейхана города Караганды"),
    ("Костанай", "Суд города Костаная"),
    ("Актобе", "Суд №2 города Актобе"),
    ("Атырау", "Суд №2 города Атырау"),
    ("Тараз", "Суд №2 города Тараза"),
    ("Уральск", "Суд №2 города Уральска"),
    ("Кызылорда", "Суд №2 города Кызылорды"),
    ("Актау", "Суд №2 города Актау"),
]


def build_courts_by_city() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for city, court in _COURT_PAIRS:
        mapping[city].append(court)

    for city in KAZAKHSTAN_CITIES:
        if city not in mapping:
            mapping[city].append(f"Суд по месту подсудности ({city})")

    return {city: sorted(courts) for city, courts in mapping.items()}


COURTS_BY_CITY = build_courts_by_city()

UZBEKISTAN_REGIONS_WITH_CITIES = {
    "г. Ташкент": [
        "Ташкент",
    ],
    "Республика Каракалпакстан": [
        "Нукус",
        "Беруни",
        "Бустон",
        "Кунград",
        "Мангит",
        "Тахиаташ",
        "Турткуль",
        "Ходжейли",
        "Чимбай",
    ],
    "Андижанская область": [
        "Андижан",
        "Асака",
        "Карасу",
        "Кургантепа",
        "Пайтуг",
        "Ханабад",
        "Ходжаабад",
        "Шахрихан",
    ],
    "Бухарская область": [
        "Бухара",
        "Каган",
        "Гиждуван",
        "Галаасия",
        "Вабкент",
    ],
    "Джизакская область": [
        "Джизак",
        "Гагарин",
        "Галлаарал",
        "Дустлик",
        "Пахтакор",
    ],
    "Кашкадарьинская область": [
        "Карши",
        "Шахрисабз",
        "Гузар",
        "Китаб",
        "Мубарек",
        "Талимарджан",
        "Яккабаг",
    ],
    "Навоийская область": [
        "Навои",
        "Зарафшан",
        "Кармана",
        "Нурата",
        "Учкудук",
    ],
    "Наманганская область": [
        "Наманган",
        "Касансай",
        "Пап",
        "Туракурган",
        "Учкурган",
        "Чартак",
        "Чуст",
    ],
    "Самаркандская область": [
        "Самарканд",
        "Акташ",
        "Булунгур",
        "Джамбай",
        "Каттакурган",
        "Ургут",
    ],
    "Сурхандарьинская область": [
        "Термез",
        "Байсун",
        "Денау",
        "Джаркурган",
        "Шерабад",
        "Шурчи",
    ],
    "Сырдарьинская область": [
        "Гулистан",
        "Бахт",
        "Сайхунабад",
        "Ширин",
        "Янгиер",
    ],
    "Ташкентская область": [
        "Нурафшан",
        "Алмалык",
        "Ангрен",
        "Ахангаран",
        "Бекабад",
        "Газалкент",
        "Келес",
        "Паркент",
        "Чиназ",
        "Чирчик",
        "Янгиюль",
    ],
    "Ферганская область": [
        "Фергана",
        "Коканд",
        "Кувасай",
        "Маргилан",
        "Риштан",
        "Ташлак",
    ],
    "Хорезмская область": [
        "Ургенч",
        "Дружба",
        "Питнак",
        "Хазарасп",
        "Хива",
        "Янгиарык",
    ],
}

UZBEKISTAN_CITIES = sorted(
    {city for cities in UZBEKISTAN_REGIONS_WITH_CITIES.values() for city in cities}
)

COUNTRY_COMPANIES = {
    "kz": KAZAKHSTAN_COMPANIES,
    "uz": UZBEKISTAN_COMPANIES,
}

COUNTRY_LABELS = {
    "kz": {"ru": "KZ Казахстан", "pl": "KZ Kazachstan", "en": "KZ Kazakhstan", "uk": "KZ Казахстан", "kk": "KZ Қазақстан"},
    "uz": {"ru": "UZ Узбекистан", "pl": "UZ Uzbekistan", "en": "UZ Uzbekistan", "uk": "UZ Узбекистан", "kk": "UZ Өзбекстан"},
}

UZ_COURT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "uz_courts_catalog.json"


def build_static_country_catalog(
    regions_with_cities: dict[str, list[str]],
    courts_by_city: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    normalized_regions = sorted(regions_with_cities)
    city_region_map: dict[str, str] = {}
    cities_by_region: dict[str, list[str]] = {}
    all_cities: set[str] = set()

    for region, cities in regions_with_cities.items():
        unique_cities = sorted({city.strip() for city in cities if city and city.strip()})
        cities_by_region[region] = unique_cities
        for city in unique_cities:
            city_region_map[city] = region
            all_cities.add(city)

    court_city_map: dict[str, str] = {}
    court_region_map: dict[str, str] = {}
    courts_by_region: dict[str, list[str]] = defaultdict(list)
    normalized_courts_by_city: dict[str, list[str]] = {}

    for city in sorted(all_cities):
        city_courts = sorted({court.strip() for court in (courts_by_city or {}).get(city, []) if court and court.strip()})
        normalized_courts_by_city[city] = city_courts
        for court in city_courts:
            court_city_map[court] = city
            region = city_region_map.get(city, "")
            if region:
                court_region_map[court] = region
                courts_by_region[region].append(court)

    return {
        "regions": normalized_regions,
        "cities": sorted(all_cities),
        "courtsByCity": normalized_courts_by_city,
        "courtsByRegion": {region: sorted(set(items)) for region, items in courts_by_region.items()},
        "courtCityMap": court_city_map,
        "courtRegionMap": court_region_map,
        "cityRegionMap": city_region_map,
        "citiesByRegion": cities_by_region,
    }

def load_uzbekistan_court_catalog() -> dict[str, object]:
    if UZ_COURT_CATALOG_PATH.exists():
        try:
            return json.loads(UZ_COURT_CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return build_static_country_catalog(UZBEKISTAN_REGIONS_WITH_CITIES)


UZBEKISTAN_COURT_CATALOG = load_uzbekistan_court_catalog()


def get_companies_by_country(country: str) -> list[str]:
    return list(COUNTRY_COMPANIES.get(country, KAZAKHSTAN_COMPANIES))


def get_country_label(country: str, language: str = "ru") -> str:
    labels = COUNTRY_LABELS.get(country, COUNTRY_LABELS[DEFAULT_COUNTRY])
    return labels.get(language, labels["ru"])
