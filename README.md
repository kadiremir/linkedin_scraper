# LinkedIn Job Link Finder

This CLI opens LinkedIn Jobs in Chrome, searches configured LinkedIn job queries, opens each job link, and prints the job details it finds.

## Setup

```powershell
python -m pip install -r requirements.txt
```

Chrome must be installed because the app launches Playwright with `channel="chrome"`.

If the existing `.venv` does not run, recreate it with a working Python interpreter first:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

The default run reads `config.yaml`:

```yaml
countries:
  - Czechia
  - Germany

job_titles:
  - software engineer
  - backend developer

# Optional. If omitted, the scraper keeps going until LinkedIn stops returning jobs.
max_pages: 10

# Optional. false keeps reposted jobs; true skips cards labeled "Reposted".
filter_reposted: false

# Options: last_24_hours, last_7_days, last_month
posted_within: last_24_hours

# false opens Chrome visibly; true runs without a browser window after login is already saved.
headless: false

# Optional. Jobs whose title contains any of these words (case-insensitive) are skipped.
exclude_title_words:
  - Intern
  - Senior

# Optional. Jobs from companies whose name contains any of these strings (case-insensitive) are skipped.
exclude_company_names:
  - Staffing
  - Recruiting
```

The app searches every job title in every country and prints the parsed results at the end of the run.

On the first run, Chrome opens LinkedIn. Log in manually, complete MFA or CAPTCHA if LinkedIn asks, then press Enter in the terminal. Later runs reuse the same profile and should already be logged in.

By default the app uses `.browser-profile/`, a dedicated automation profile. To use your existing personal Chrome profile instead, fully close every Chrome window first, then run:

```powershell
python main.py --use-default-chrome-profile
```

If your personal Chrome profile is not `Default`, open `chrome://version` in normal Chrome and check `Profile Path`. The final folder is the profile directory, such as `Profile 1`.

```powershell
python main.py --use-default-chrome-profile --chrome-profile-directory "Profile 1"
```

You can also pass the Chrome user-data directory explicitly:

```powershell
python main.py --chrome-user-data-dir "$env:LOCALAPPDATA\Google\Chrome\User Data" --chrome-profile-directory "Default"
```

Useful options:

```powershell
python main.py --keywords "software engineer" --location "Czechia" --max-pages 10
python main.py --profile-dir .browser-profile
python main.py --config config.yaml
```

Pagination is no longer fixed. Without `max_pages`, each search continues through LinkedIn result pages until a page returns no jobs or no new job ids. Set `max_pages` in `config.yaml` or pass `--max-pages` to cap each country/title search.

Set `filter_reposted: true` in `config.yaml` to skip LinkedIn cards labeled `Reposted`.

Set `posted_within` to control LinkedIn's posted-date filter. Default is `last_24_hours`; supported values are `last_24_hours`, `last_7_days`, and `last_month`.

Set `headless: true` only after you have already logged in with the same Chrome profile. Headless mode cannot complete LinkedIn login, MFA, or CAPTCHA prompts.

Set `exclude_title_words` to a list of words to skip jobs whose title contains any of them (case-insensitive substring match). Useful for filtering out seniority levels or roles you are not interested in.

Set `exclude_company_names` to a list of strings to skip jobs from companies whose name contains any of them (case-insensitive substring match). Useful for filtering out staffing agencies or specific employers.

If Chrome opens the correct profile but the tab stays empty, try:

```powershell
python main.py --use-default-chrome-profile --pause-on-start
```

When Chrome opens, manually type `https://www.linkedin.com/feed/` in that tab if it is still blank, then press Enter in the terminal.

Search result pages are used only to collect LinkedIn job links. The app then opens each job link one at a time, waits for the page load, and reads company, title, location, workplace type, and posted/reposted text from the job detail page before printing.
