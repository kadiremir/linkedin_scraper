from dataclasses import dataclass


@dataclass(frozen=True)
class JobLink:
    job_id: str
    url: str


@dataclass(frozen=True)
class JobPosting:
    job_id: str
    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    posted_at: str | None = None


@dataclass(frozen=True)
class SearchTarget:
    country: str
    job_title: str
