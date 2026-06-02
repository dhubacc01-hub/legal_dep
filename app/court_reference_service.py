from __future__ import annotations

from typing import Any

from app.country_service import normalize_country_code
from app.court_catalog import merge_court_catalog
from app.reference_data import DEFAULT_COUNTRY, UZBEKISTAN_COURT_CATALOG


def _city_aliases(city: str) -> set[str]:
    value = str(city or "").strip()
    if not value:
        return set()

    aliases = {value}
    lowered = value.lower()
    if lowered.startswith("город "):
        aliases.add(value[6:].strip())
    if lowered.startswith("г. "):
        aliases.add(value[3:].strip())
    if lowered.startswith("г "):
        aliases.add(value[2:].strip())
    return {alias for alias in aliases if alias}


def _with_city_aliases(catalog: dict[str, Any]) -> dict[str, Any]:
    cities = set(catalog["cities"])
    courts_by_city = {city: list(items) for city, items in catalog["courtsByCity"].items()}
    courts_by_region = {region: list(items) for region, items in catalog["courtsByRegion"].items()}
    city_region_map = dict(catalog["cityRegionMap"])
    cities_by_region = {region: list(items) for region, items in catalog["citiesByRegion"].items()}

    for city, courts in list(courts_by_city.items()):
        region = city_region_map.get(city, "")
        for alias in _city_aliases(city):
            cities.add(alias)
            courts_by_city.setdefault(alias, list(courts))
            if region:
                city_region_map.setdefault(alias, region)
                cities_by_region.setdefault(region, [])
                if alias not in cities_by_region[region]:
                    cities_by_region[region].append(alias)

    for region, region_courts in list(courts_by_region.items()):
        cities.add(region)
        courts_by_city.setdefault(region, list(region_courts))
        lowered = str(region or "").strip().lower()
        if lowered.startswith("город "):
            alias = str(region)[6:].strip()
        elif lowered.startswith("г. "):
            alias = str(region)[3:].strip()
        elif lowered.startswith("г "):
            alias = str(region)[2:].strip()
        else:
            alias = ""

        if not alias:
            continue

        cities.add(alias)
        courts_by_city.setdefault(alias, list(region_courts))
        city_region_map.setdefault(alias, region)
        cities_by_region.setdefault(region, [])
        if alias not in cities_by_region[region]:
            cities_by_region[region].append(alias)

    return {
        "regions": list(catalog["regions"]),
        "cities": sorted(cities),
        "courtsByCity": {city: sorted(set(items)) for city, items in courts_by_city.items()},
        "courtsByRegion": {region: sorted(set(items)) for region, items in courts_by_region.items()},
        "courtCityMap": dict(catalog["courtCityMap"]),
        "courtRegionMap": dict(catalog["courtRegionMap"]),
        "cityRegionMap": city_region_map,
        "citiesByRegion": {region: sorted(set(items)) for region, items in cities_by_region.items()},
    }


def load_custom_courts(connection, country: str) -> list[dict[str, str]]:
    rows = connection.execute(
        """
        SELECT name, city, region
        FROM custom_courts
        WHERE COALESCE(country, ?) = ?
        ORDER BY name COLLATE NOCASE ASC
        """,
        (DEFAULT_COUNTRY, normalize_country_code(country)),
    ).fetchall()
    result: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        values = [str(item.get("name") or "").strip(), str(item.get("city") or "").strip(), str(item.get("region") or "").strip()]
        if not all(values):
            continue
        if any("?" in value for value in values):
            continue
        result.append(item)
    return result


def merge_static_court_catalog(
    base_catalog: dict[str, Any], custom_courts: list[dict[str, str]]
) -> dict[str, Any]:
    regions = list(base_catalog["regions"])
    cities = set(base_catalog["cities"])
    courts_by_city = {city: list(items) for city, items in base_catalog["courtsByCity"].items()}
    courts_by_region = {region: list(items) for region, items in base_catalog["courtsByRegion"].items()}
    court_city_map = dict(base_catalog["courtCityMap"])
    court_region_map = dict(base_catalog["courtRegionMap"])
    city_region_map = dict(base_catalog["cityRegionMap"])
    cities_by_region = {region: list(items) for region, items in base_catalog["citiesByRegion"].items()}

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


def build_reference_catalog(connection, country: str) -> dict[str, Any]:
    normalized_country = normalize_country_code(country)
    custom_courts = load_custom_courts(connection, normalized_country)
    if normalized_country == "uz":
        return _with_city_aliases(merge_static_court_catalog(UZBEKISTAN_COURT_CATALOG, custom_courts))
    return _with_city_aliases(merge_court_catalog(custom_courts))


def align_city_with_court(connection, country: str, city: str, court: str) -> tuple[str, str]:
    normalized_city = city.strip()
    normalized_court = court.strip()
    catalog = build_reference_catalog(connection, country)
    mapped_city = catalog["courtCityMap"].get(normalized_court)
    if mapped_city:
        return mapped_city, normalized_court
    return normalized_city, normalized_court
