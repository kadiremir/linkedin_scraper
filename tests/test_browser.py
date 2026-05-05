from linkedin_jobs.browser import (
    extract_detail_title,
    infer_job_details_from_html,
    infer_title_from_html,
    extract_location,
    extract_posted_at,
    extract_workplace_type,
    has_reposted_label,
    infer_company_from_card_text,
)


def test_infer_company_from_card_text_uses_first_non_title_location_line():
    assert infer_company_from_card_text(
        card_text="""
Software Engineer
Example Ltd
Prague, Czechia
2 days ago
""",
        title="Software Engineer",
        location="Prague, Czechia",
    ) == "Example Ltd"


def test_has_reposted_label_detects_reposted_card_text():
    assert has_reposted_label("Software Engineer\nExample Ltd\nReposted 7 hours ago")


def test_has_reposted_label_ignores_normal_posted_time():
    assert not has_reposted_label("Software Engineer\nExample Ltd\n7 hours ago")


def test_detail_text_extracts_location_posted_at_and_workplace_type():
    detail_text = """
Pure Storage
Software Engineer (Containers)
Prague, Prague, Czechia · Reposted 2 days ago · 37 people clicked apply
On-site
Full-time
"""

    assert extract_location(detail_text) == "Prague, Prague, Czechia"
    assert extract_posted_at(detail_text) == "Reposted 2 days ago"
    assert extract_workplace_type(detail_text) == "On-site"


def test_detail_text_extracts_segments_with_normal_bullet_separator():
    detail_text = (
        "Prague, Prague, Czechia \u00b7 Reposted 2 days ago "
        "\u00b7 37 people clicked apply"
    )

    assert extract_location(detail_text) == "Prague, Prague, Czechia"
    assert extract_posted_at(detail_text) == "Reposted 2 days ago"


def test_extract_detail_title_skips_global_notification_heading():
    detail_text = """
Pure Storage
Software Engineer (Containers)
Prague, Prague, Czechia Â· Reposted 2 days ago Â· 37 people clicked apply
On-site
Full-time
"""

    assert extract_detail_title("0 notifications", detail_text, company="Pure Storage") == (
        "Software Engineer (Containers)"
    )


def test_infer_title_from_html_reads_linkedin_paragraph_title():
    html = """
<div>
  <p class="_9e348bbd _4a336686 _33a19d00 e17582ce c0283d7f a2b3a7bc _5ed4d071 cb8df2cc _4fb23d32 _98fdec3a">
    DevOps Engineer (Azure) - Hybrid, Madrid + RELOCATION
  </p>
</div>
"""

    assert infer_title_from_html(html) == (
        "DevOps Engineer (Azure) - Hybrid, Madrid + RELOCATION"
    )


def test_infer_job_details_from_html_reads_new_linkedin_top_block():
    html = """
<div>
  <div aria-label="Company, UST Espa\u00f1a &amp; Latam.">
    <p><a href="https://www.linkedin.com/company/ustespana/life/">UST Espa\u00f1a &amp; Latam</a></p>
  </div>
  <p>DevOps Engineer (Azure) - Hybrid, Madrid + RELOCATION</p>
  <p>
    <span>European Union</span>
    <span> </span>\u00b7<span> </span>
    <span><strong>16 hours ago</strong></span>
    <span> </span>\u00b7<span> </span>
    <span>37 applicants</span>
  </p>
  <a href="https://www.linkedin.com/jobs/view/4408676574/"><span>Remote</span></a>
  <a href="https://www.linkedin.com/jobs/view/4408676574/"><span>Full-time</span></a>
</div>
"""

    details = infer_job_details_from_html(html)

    assert details.company == "UST Espa\u00f1a & Latam"
    assert details.title == "DevOps Engineer (Azure) - Hybrid, Madrid + RELOCATION"
    assert details.location == "European Union"
    assert details.posted_at == "16 hours ago"
    assert details.workplace_type == "Remote"


def test_extract_detail_title_rejects_home_navigation_text():
    detail_text = """
Pure Storage
Software Engineer (Containers)
Prague, Prague, Czechia \u00b7 Reposted 2 days ago \u00b7 37 people clicked apply
"""

    assert extract_detail_title("Home", detail_text, company="Pure Storage") == (
        "Software Engineer (Containers)"
    )
