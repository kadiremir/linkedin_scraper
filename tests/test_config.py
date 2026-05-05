from pathlib import Path

from linkedin_jobs.config import load_config, posted_within_seconds
from linkedin_jobs.models import SearchTarget


def test_load_config_reads_countries_and_job_titles():
    config = load_config(Path("tests/fixtures/search_config.yaml"))

    assert config.countries == ["Czechia", "Germany"]
    assert config.job_titles == ["software engineer", "backend developer"]
    assert config.max_pages == 3
    assert config.filter_reposted is True
    assert config.posted_within == "last_7_days"
    assert config.headless is True
    assert config.search_targets == [
        SearchTarget(country="Czechia", job_title="software engineer"),
        SearchTarget(country="Czechia", job_title="backend developer"),
        SearchTarget(country="Germany", job_title="software engineer"),
        SearchTarget(country="Germany", job_title="backend developer"),
    ]


def test_load_config_allows_missing_max_pages():
    config = load_config(Path("tests/fixtures/search_config_without_max_pages.yaml"))

    assert config.max_pages is None
    assert config.filter_reposted is False
    assert config.posted_within == "last_24_hours"
    assert config.headless is False


def test_posted_within_seconds_maps_supported_windows():
    assert posted_within_seconds("last_24_hours") == 86400
    assert posted_within_seconds("last_7_days") == 604800
    assert posted_within_seconds("last_month") == 2592000
