from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache

from app.kz_courts_data import KZ_OFFICIAL_COURT_MAPPING_DATA
from app.reference_data import KAZAKHSTAN_CITIES

REGION_DEFAULT_CITY = {
    "город Астана": "Астана",
    "город Алматы": "Алматы",
    "город Шымкент": "Шымкент",
    "Акмолинская область": "Кокшетау",
    "Актюбинская область": "Актобе",
    "Алматинская область": "Конаев",
    "Атырауская область": "Атырау",
    "Восточно-Казахстанская область": "Усть-Каменогорск",
    "Жамбылская область": "Тараз",
    "Западно-Казахстанская область": "Уральск",
    "Карагандинская область": "Караганда",
    "Костанайская область": "Костанай",
    "Кызылординская область": "Кызылорда",
    "Мангистауская область": "Актау",
    "Павлодарская область": "Павлодар",
    "Северо-Казахстанская область": "Петропавловск",
    "Туркестанская область": "Туркестан",
    "Военный суд Республики Казахстан": "Астана",
    "Область Ұлытау": "Жезказган",
    "Область Абай": "Семей",
    "Область Жетісу": "Талдыкорган",
}

SPECIAL_CITY_ALIASES = {
    "астаны": "Астана",
    "алматы": "Алматы",
    "шымкента": "Шымкент",
    "кокшетау": "Кокшетау",
    "кокшетауского": "Кокшетау",
    "талдыкоргана": "Талдыкорган",
    "талдыкорганский": "Талдыкорган",
    "семея": "Семей",
    "суд города косшы": "Косшы",
    "конаева": "Конаев",
    "павлодара": "Павлодар",
    "тараза": "Тараз",
    "уральска": "Уральск",
    "кызылорды": "Кызылорда",
    "усть-каменогорска": "Усть-Каменогорск",
    "жезказгана": "Жезказган",
    "костаная": "Костанай",
    "актобе": "Актобе",
    "актау": "Актау",
    "атырау": "Атырау",
    "туркестана": "Туркестан",
    "алматинского гарнизона": "Алматы",
    "акмолинского гарнизона": "Астана",
    "семейского гарнизона": "Семей",
    "актюбинского гарнизона": "Актобе",
    "шымкентского гарнизона": "Шымкент",
    "мақаншы": "Мақаншы",
    "ақсуат": "Ақсуат",
}

CYRILLIC_WORD_RE = re.compile(r"[А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІіЁё\-]+")


def _build_city_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for city in KAZAKHSTAN_CITIES:
        lowered = city.lower()
        aliases[lowered] = city

        if city.endswith("а"):
            stem = city[:-1]
            for alias in (f"{stem}ы", f"{stem}е", f"{stem}у", f"{stem}ой"):
                aliases[alias.lower()] = city
        elif city.endswith("я"):
            stem = city[:-1]
            for alias in (f"{stem}и", f"{stem}е", f"{stem}ю"):
                aliases[alias.lower()] = city
        elif city.endswith("й"):
            stem = city[:-1]
            for alias in (f"{stem}я", f"{stem}ю", f"{stem}е"):
                aliases[alias.lower()] = city
        elif city.endswith("ь"):
            stem = city[:-1]
            for alias in (f"{stem}я", f"{stem}ю", f"{stem}е"):
                aliases[alias.lower()] = city
        elif city.endswith("ск") or city.endswith("рд"):
            for alias in (f"{city}а", f"{city}у", f"{city}е"):
                aliases[alias.lower()] = city
        elif city[-1].lower() not in {"а", "я", "й", "ь", "у", "ы", "и", "о", "е", "ю"}:
            for alias in (f"{city}а", f"{city}у", f"{city}е"):
                aliases[alias.lower()] = city

    aliases.update(SPECIAL_CITY_ALIASES)
    return aliases


CITY_ALIASES = _build_city_aliases()


def _load_pairs() -> list[dict[str, object]]:
    if not isinstance(KZ_OFFICIAL_COURT_MAPPING_DATA, dict):
        return []
    pairs = KZ_OFFICIAL_COURT_MAPPING_DATA.get("pairs", [])
    return pairs if isinstance(pairs, list) else []


def _extract_locality_from_court_name(court_name: str, region_name: str) -> str:
    lowered = court_name.lower()

    if "верховный суд республики казахстан" in lowered or "кассационный суд республики казахстан" in lowered:
        return "Астана"

    for alias in sorted(CITY_ALIASES, key=len, reverse=True):
        if alias and alias in lowered:
            return CITY_ALIASES[alias]

    district_match = re.search(r"суд района ([А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІіЁё\-]+)", court_name)
    if district_match:
        return district_match.group(1)

    words = CYRILLIC_WORD_RE.findall(court_name)
    for word in words:
        cleaned = word.strip("-")
        if cleaned in KAZAKHSTAN_CITIES:
            return cleaned

    if region_name.startswith("город "):
        return region_name.replace("город ", "", 1).strip()

    return REGION_DEFAULT_CITY.get(region_name, "")


@lru_cache(maxsize=1)
def load_official_court_catalog() -> dict[str, object]:
    pairs = _load_pairs()

    regions: list[str] = []
    cities = set(KAZAKHSTAN_CITIES)
    courts_by_city: dict[str, list[str]] = defaultdict(list)
    courts_by_region: dict[str, list[str]] = defaultdict(list)
    court_city_map: dict[str, str] = {}
    court_region_map: dict[str, str] = {}
    city_region_map: dict[str, str] = {}
    cities_by_region: dict[str, list[str]] = defaultdict(list)

    for pair in pairs:
        region_name = str(pair["regionName"])
        if region_name not in regions:
            regions.append(region_name)

        default_city = REGION_DEFAULT_CITY.get(region_name)
        if default_city:
            cities.add(default_city)
            city_region_map.setdefault(default_city, region_name)
            if default_city not in cities_by_region[region_name]:
                cities_by_region[region_name].append(default_city)

        for court_name in pair.get("courts", []):
            court = str(court_name).strip()
            if not court:
                continue

            city = _extract_locality_from_court_name(court, region_name) or default_city or "Без города"
            cities.add(city)
            court_city_map[court] = city
            court_region_map[court] = region_name
            city_region_map.setdefault(city, region_name)
            courts_by_city[city].append(court)
            courts_by_region[region_name].append(court)
            if city not in cities_by_region[region_name]:
                cities_by_region[region_name].append(city)

    return {
        "regions": regions,
        "cities": sorted(cities),
        "courtsByCity": {city: sorted(set(items)) for city, items in courts_by_city.items()},
        "courtsByRegion": {region: sorted(set(items)) for region, items in courts_by_region.items()},
        "courtCityMap": court_city_map,
        "courtRegionMap": court_region_map,
        "cityRegionMap": city_region_map,
        "citiesByRegion": {region: sorted(set(items)) for region, items in cities_by_region.items()},
    }


def merge_court_catalog(custom_courts: list[dict[str, str]]) -> dict[str, object]:
    base = load_official_court_catalog()

    regions = list(base["regions"])
    cities = set(base["cities"])
    courts_by_city = {city: list(items) for city, items in base["courtsByCity"].items()}
    courts_by_region = {region: list(items) for region, items in base["courtsByRegion"].items()}
    court_city_map = dict(base["courtCityMap"])
    court_region_map = dict(base["courtRegionMap"])
    city_region_map = dict(base["cityRegionMap"])
    cities_by_region = {region: list(items) for region, items in base["citiesByRegion"].items()}

    for item in custom_courts:
        name = str(item["name"]).strip()
        city = str(item["city"]).strip()
        region = str(item["region"]).strip()
        if not name or not city or not region:
            continue

        if region not in regions:
            regions.append(region)
        cities.add(city)
        court_city_map[name] = city
        court_region_map[name] = region
        city_region_map[city] = region
        courts_by_city.setdefault(city, [])
        if name not in courts_by_city[city]:
            courts_by_city[city].append(name)
        courts_by_region.setdefault(region, [])
        if name not in courts_by_region[region]:
            courts_by_region[region].append(name)
        cities_by_region.setdefault(region, [])
        if city not in cities_by_region[region]:
            cities_by_region[region].append(city)

    return {
        "regions": sorted(regions),
        "cities": sorted(cities),
        "courtsByCity": {city: sorted(set(items)) for city, items in courts_by_city.items()},
        "courtsByRegion": {region: sorted(set(items)) for region, items in courts_by_region.items()},
        "courtCityMap": court_city_map,
        "courtRegionMap": court_region_map,
        "cityRegionMap": city_region_map,
        "citiesByRegion": {region: sorted(set(items)) for region, items in cities_by_region.items()},
    }
