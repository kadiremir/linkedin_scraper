from linkedin_jobs.cli import print_job_group
from linkedin_jobs.models import JobPosting


def test_print_job_group_prints_all_job_details(capsys):
    job = JobPosting(
        job_id="123",
        url="https://www.linkedin.com/jobs/view/123/",
        title="Software Engineer",
        company="Example Ltd",
        location="Prague, Czechia",
        workplace_type="Hybrid",
        posted_at="Posted 3 hours ago",
    )

    print_job_group("Czechia", ["software engineer"], [job])

    output = capsys.readouterr().out
    assert "Searched for the roles: software engineer at: Czechia" in output
    assert "Found: 1" in output
    assert "Example Ltd - Software Engineer" in output
    assert "link: https://www.linkedin.com/jobs/view/123/" in output
    assert "company: Example Ltd" in output
    assert "title: Software Engineer" in output
    assert "location: Prague, Czechia" in output
    assert "workplace_type: Hybrid" in output
    assert "posted_at: Posted 3 hours ago" in output
    assert " at Example Ltd" not in output
