# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

After implementing any new feature or config option, update README.md to reflect the change.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scraper (first run opens browser for manual login)
python main.py

# Run with options
python main.py --config config.yaml --headless --max-pages 5
python main.py --keywords "backend engineer" --location Germany --page-pause-seconds 1.0

# Run tests
pytest

# Run a single test file
pytest tests/test_browser.py

# Run a single test
pytest tests/test_browser.py::test_extract_job_links
```

## Architecture

The tool uses Playwright to drive a persistent Chrome profile, so LinkedIn login state is preserved across runs. First run requires manual login via the opened browser window.

**Flow:**
```
main.py → cli.main() → collect_jobs_for_targets_from_linkedin()
  └── Playwright persistent context (.browser-profile/)
      ├── ensure_logged_in()  — checks feed; prompts manual login if needed
      └── for each SearchTarget (country × job_title from config):
          ├── scrape_search_results() — pagination loop, builds URLs, extracts job links
          └── scrape_job_details()   — visits each job page, extracts structured metadata
```

**Key modules:**
- `linkedin_jobs/browser.py` — 979 lines, the core scraping engine. Contains all Playwright automation, HTML parsing, and text extraction. LinkedIn's layout changes frequently; there are multiple CSS selector fallbacks and two layout paths (2025 SDUI + legacy).
- `linkedin_jobs/config.py` — Loads and validates `config.yaml`. The `AppConfig` frozen dataclass holds all settings.
- `linkedin_jobs/urls.py` — Builds LinkedIn search URLs, normalizes job URLs to a canonical form with a stable `job_id`, and loads `applied_jobs.yaml` via `load_applied_job_ids()`.
- `linkedin_jobs/models.py` — Three frozen dataclasses: `JobLink`, `JobPosting`, `SearchTarget`.
- `linkedin_jobs/profiles.py` — Resolves which Chrome profile path to use (dedicated automation profile, Windows default, or custom).
- `linkedin_jobs/cli.py` — Argument parsing, console output formatting, and Excel export (`write_jobs_to_excel()` writes `output.xlsx` after every run).

`main_2.py` is an abandoned prototype that used `requests`+`BeautifulSoup` against LinkedIn's guest API — it is not part of the active flow.

## Configuration

`config.yaml` controls search targets and behavior:

```yaml
countries: [Czechia, Germany]
job_titles: [DevOps Engineer, Software Engineer]
max_pages: 10                    # optional; scrapes until no new jobs if omitted
filter_reposted: true
posted_within: last_24_hours     # last_24_hours | last_7_days | last_month
headless: true
exclude_title_words: [Intern]    # optional; skips jobs whose title contains any of these words (case-insensitive)
exclude_company_names: [Infosys] # optional; skips jobs whose company name contains any of these strings (case-insensitive)
applied_jobs_file: applied_jobs.yaml  # optional; defaults to applied_jobs.yaml
```

After each run, results are also written to `output.xlsx` (columns: URL, Country, Company, Title, Location, Workplace Type, Posted At). The file is overwritten on every run.

`applied_jobs.yaml` (gitignored, created manually) lists jobs already applied to so they are excluded from future runs. The filter fires before any page is visited. Format:

```yaml
urls_applied:
  - https://www.linkedin.com/jobs/view/4408404420/
  # optional comment / note
  - https://www.linkedin.com/jobs/view/1234567890/
```

## HTML Parsing Notes

LinkedIn frequently changes its DOM structure. `browser.py` uses:
- `JobDetailHtmlParser` (stdlib `html.parser`) to extract text from specific tags and aria-labels
- `CandidateTextParser` for filtering text from target elements
- `infer_job_details_from_html()` as the primary extraction path with multiple selector fallbacks
- `extract_structured_job_details_from_page()` as a wrapper that calls both Playwright selectors and the custom parsers

When adding or fixing selectors, check both the 2025 SDUI layout and legacy layout code paths in `browser.py`.

## Browser Profile

The scraper stores its Chrome profile in `.browser-profile/` (gitignored). Delete this directory to force a fresh login. Use `--use-default-chrome-profile` or `--chrome-user-data-dir` / `--chrome-profile-directory` to reuse an existing Chrome profile instead.
