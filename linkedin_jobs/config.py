from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from linkedin_jobs.models import SearchTarget


POSTED_WITHIN_SECONDS = {
    "last_24_hours": 24 * 60 * 60,
    "last_7_days": 7 * 24 * 60 * 60,
    "last_month": 30 * 24 * 60 * 60,
}
DEFAULT_POSTED_WITHIN = "last_24_hours"


@dataclass(frozen=True)
class AppConfig:
    countries: list[str]
    job_titles: list[str]
    max_pages: int | None = None
    filter_reposted: bool = False
    posted_within: str = DEFAULT_POSTED_WITHIN
    headless: bool = False
    exclude_title_words: list[str] = field(default_factory=list)
    exclude_company_names: list[str] = field(default_factory=list)

    @property
    def search_targets(self) -> list[SearchTarget]:
        return [
            SearchTarget(country=country, job_title=job_title)
            for country in self.countries
            for job_title in self.job_titles
        ]


def load_config(path: Path) -> AppConfig:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        data = parse_simple_yaml_lists(text)
    else:
        data = yaml.safe_load(text) or {}

    if not isinstance(data, dict):
        raise RuntimeError(f"Config file must contain a YAML object: {path}")

    countries = validate_string_list(data.get("countries"), "countries")
    job_titles = validate_string_list(data.get("job_titles"), "job_titles")
    max_pages = validate_optional_positive_int(data.get("max_pages"), "max_pages")
    filter_reposted = validate_optional_bool(data.get("filter_reposted"), "filter_reposted")
    posted_within = validate_posted_within(data.get("posted_within"))
    headless = validate_optional_bool(data.get("headless"), "headless")
    exclude_title_words = validate_optional_string_list(data.get("exclude_title_words"), "exclude_title_words")
    exclude_company_names = validate_optional_string_list(data.get("exclude_company_names"), "exclude_company_names")
    return AppConfig(
        countries=countries,
        job_titles=job_titles,
        max_pages=max_pages,
        filter_reposted=filter_reposted,
        posted_within=posted_within,
        headless=headless,
        exclude_title_words=exclude_title_words,
        exclude_company_names=exclude_company_names,
    )


def validate_optional_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    return validate_string_list(value, field_name)


def validate_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"Config field '{field_name}' must be a non-empty list.")

    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError(f"Config field '{field_name}' must contain only non-empty strings.")
        cleaned.append(item.strip())

    return cleaned


def validate_optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        raise RuntimeError(f"Config field '{field_name}' must be a positive integer when set.")
    return value


def validate_optional_bool(value: Any, field_name: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise RuntimeError(f"Config field '{field_name}' must be true or false when set.")
    return value


def validate_posted_within(value: Any) -> str:
    if value is None:
        return DEFAULT_POSTED_WITHIN
    if not isinstance(value, str) or value not in POSTED_WITHIN_SECONDS:
        allowed = ", ".join(sorted(POSTED_WITHIN_SECONDS))
        raise RuntimeError(f"Config field 'posted_within' must be one of: {allowed}.")
    return value


def posted_within_seconds(value: str) -> int:
    return POSTED_WITHIN_SECONDS[value]


def parse_simple_yaml_lists(text: str) -> dict[str, list[str]]:
    parsed: dict[str, Any] = {}
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        if not raw_line.startswith((" ", "\t")) and ":" in line:
            key, raw_value = line.split(":", 1)
            current_key = key.strip()
            value = raw_value.strip()
            if value:
                parsed[current_key] = parse_scalar(value)
                current_key = None
            else:
                parsed[current_key] = []
            continue

        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            parsed[current_key].append(stripped[2:].strip().strip("\"'"))
            continue

        raise RuntimeError(
            "Config YAML uses syntax that requires PyYAML. Install requirements.txt "
            "or keep config.yaml as simple top-level string lists."
        )

    return parsed


def parse_scalar(value: str) -> str | int | bool:
    cleaned = value.strip().strip("\"'")
    if cleaned.lower() == "true":
        return True
    if cleaned.lower() == "false":
        return False
    if cleaned.isdigit():
        return int(cleaned)
    return cleaned
