from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path


UPDATE_RE = re.compile(
    r"<update\s+id=\"(?P<id>[^\"]+)\"><!\[CDATA\[(?P<body>.*?)\]\]></update>",
    re.DOTALL,
)
OPTION_RE = re.compile(
    r"<option\s+value=\"(?P<value>[^\"]*)\">(?P<label>.*?)</option>",
    re.DOTALL,
)
COURT_RE = re.compile(r"<p\b[^>]*>(?P<label>.*?)</p>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class RegionItem:
    region_id: str
    name: str


def normalize_space(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split())


def strip_tags(value: str) -> str:
    return normalize_space(TAG_RE.sub("", value))


def parse_updates(raw_text: str) -> dict[str, str]:
    return {match.group("id"): match.group("body") for match in UPDATE_RE.finditer(raw_text)}


def find_update_body(raw_text: str, suffix: str) -> str:
    updates = parse_updates(raw_text)
    for update_id, body in updates.items():
        if update_id.endswith(suffix):
            return body
    raise ValueError(f"Не найден блок update с окончанием '{suffix}'.")


def parse_regions_response(raw_text: str) -> list[RegionItem]:
    panel_body = find_update_body(raw_text, "regionsPanel")
    items: list[RegionItem] = []
    for match in OPTION_RE.finditer(panel_body):
        region_id = normalize_space(match.group("value"))
        name = strip_tags(match.group("label"))
        if not region_id or not name or name == "-- Выберите --":
            continue
        items.append(RegionItem(region_id=region_id, name=name))
    return items


def parse_courts_response(raw_text: str) -> list[str]:
    list_body = find_update_body(raw_text, "condinates-list")
    courts: list[str] = []
    seen: set[str] = set()
    for match in COURT_RE.finditer(list_body):
        label = strip_tags(match.group("label"))
        if not label or label in seen:
            continue
        seen.add(label)
        courts.append(label)
    return courts


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_region_response_path(responses_dir: Path, region_id: str) -> Path | None:
    exact = responses_dir / f"{region_id}.xml"
    if exact.exists():
        return exact

    candidates = sorted(responses_dir.glob(f"{region_id}*"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def command_regions(input_path: Path) -> int:
    regions = parse_regions_response(read_text(input_path))
    print(json.dumps([item.__dict__ for item in regions], ensure_ascii=False, indent=2))
    return 0


def command_courts(input_path: Path) -> int:
    courts = parse_courts_response(read_text(input_path))
    print(json.dumps(courts, ensure_ascii=False, indent=2))
    return 0


def command_build(regions_path: Path, responses_dir: Path, output_path: Path) -> int:
    regions = parse_regions_response(read_text(regions_path))
    result: dict[str, list[str]] = {}
    missing: list[dict[str, str]] = []

    for region in regions:
        response_path = find_region_response_path(responses_dir, region.region_id)
        if response_path is None:
            missing.append({"id": region.region_id, "name": region.name})
            continue
        result[region.name] = parse_courts_response(read_text(response_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "regions": result,
        "missingResponses": missing,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Сохранено: {output_path}")
    print(f"Областей обработано: {len(result)}")
    print(f"Не хватает ответов: {len(missing)}")
    if missing:
        print(json.dumps(missing, ensure_ascii=False, indent=2))
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Парсер ответов JSF partial-response для справочника судов office.sud.kz/gis."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    regions_parser = subparsers.add_parser("regions", help="Показать список областей из ответа после выбора 'Суды'.")
    regions_parser.add_argument("--input", type=Path, required=True, help="Путь к raw XML/HTML-ответу.")

    courts_parser = subparsers.add_parser("courts", help="Показать список судов из ответа выбранной области.")
    courts_parser.add_argument("--input", type=Path, required=True, help="Путь к raw XML/HTML-ответу.")

    build_parser = subparsers.add_parser("build", help="Собрать итоговый JSON область -> суды.")
    build_parser.add_argument("--regions", type=Path, required=True, help="Файл ответа после выбора 'Суды'.")
    build_parser.add_argument(
        "--responses-dir",
        type=Path,
        required=True,
        help="Папка с raw-ответами по областям. Имена файлов: <id>.xml или <id>_*.xml.",
    )
    build_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/courts_by_region.json"),
        help="Куда сохранить итоговый JSON.",
    )

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command == "regions":
        return command_regions(args.input)
    if args.command == "courts":
        return command_courts(args.input)
    if args.command == "build":
        return command_build(args.regions, args.responses_dir, args.output)

    parser.error("Неизвестная команда.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
