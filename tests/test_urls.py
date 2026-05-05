from linkedin_jobs.urls import build_jobs_search_url, normalize_linkedin_job_url


def test_normalize_linkedin_job_url_strips_tracking_params():
    assert normalize_linkedin_job_url(
        "https://www.linkedin.com/jobs/view/1234567890/?refId=abc&trackingId=def"
    ) == ("1234567890", "https://www.linkedin.com/jobs/view/1234567890/")


def test_normalize_linkedin_job_url_handles_current_job_id():
    assert normalize_linkedin_job_url(
        "https://www.linkedin.com/jobs/search/?currentJobId=987654321"
    ) == ("987654321", "https://www.linkedin.com/jobs/view/987654321/")


def test_build_jobs_search_url_uses_last_24_hours_filter_by_default():
    url = build_jobs_search_url(keywords="software engineer", location="Czechia", start=25)

    assert "keywords=software+engineer" in url
    assert "location=Czechia" in url
    assert "f_TPR=r86400" in url
    assert "start=25" in url


def test_build_jobs_search_url_accepts_custom_posted_window_seconds():
    url = build_jobs_search_url(
        keywords="software engineer",
        location="Czechia",
        start=25,
        seconds=604800,
    )

    assert "f_TPR=r604800" in url
