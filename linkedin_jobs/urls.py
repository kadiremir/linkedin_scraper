import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse


LINKEDIN_BASE_URL = "https://www.linkedin.com"
LAST_24_HOURS_SECONDS = 24 * 60 * 60


def build_jobs_search_url(
    keywords: str = "software engineer",
    location: str = "Czechia",
    start: int = 0,
    seconds: int = LAST_24_HOURS_SECONDS,
) -> str:
    query = urlencode(
        {
            "keywords": keywords,
            "location": location,
            "f_TPR": f"r{seconds}",
            "start": start,
        }
    )
    return f"{LINKEDIN_BASE_URL}/jobs/search/?{query}"


def normalize_linkedin_job_url(raw_href: str | None) -> tuple[str, str] | None:
    if not raw_href:
        return None

    parsed = urlparse(urljoin(LINKEDIN_BASE_URL, raw_href))
    if parsed.netloc and not parsed.netloc.endswith("linkedin.com"):
        return None

    path_match = re.search(r"/jobs/view/(\d+)", parsed.path)
    if path_match:
        job_id = path_match.group(1)
        return job_id, canonical_job_url(job_id)

    query = parse_qs(parsed.query)
    current_job_id = query.get("currentJobId", [None])[0]
    if current_job_id and current_job_id.isdigit():
        return current_job_id, canonical_job_url(current_job_id)

    return None


def canonical_job_url(job_id: str) -> str:
    return f"{LINKEDIN_BASE_URL}/jobs/view/{job_id}/"
