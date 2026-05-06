import asyncio
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from linkedin_jobs.models import JobLink, JobPosting, SearchTarget
from linkedin_jobs.urls import build_jobs_search_url, normalize_linkedin_job_url


JOB_CARD_SELECTORS = [
    "li[data-occludable-job-id]",
    "li.jobs-search-results__list-item",
    "div.job-card-container",
]
TITLE_SELECTORS = [
    # SDUI layout (2025+): title <p> is the first sibling after the company section
    "xpath=//div[@aria-label[starts-with(., 'Company,')]]/ancestor::div[@data-display-contents][1]/parent::div/following-sibling::div[1]//p[1]",
    # legacy selectors
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title",
    ".top-card-layout__title",
    "[data-test-job-title]",
]
TITLE_HTML_CONTAINERS = [
    # SDUI layout (2025+)
    "[data-sdui-screen='com.linkedin.sdui.flagshipnav.jobs.JobDetails']",
    # legacy selectors
    ".job-details-jobs-unified-top-card",
    ".jobs-unified-top-card",
    ".jobs-search__job-details--container",
    ".jobs-details",
    ".job-view-layout",
    "[data-job-id]",
]
DETAIL_HTML_CONTAINERS = TITLE_HTML_CONTAINERS
COMPANY_SELECTORS = [
    "[aria-label^='Company,']",
    ".job-details-jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name a",
    "[data-test-job-card-company-name]",
    "a[href*='/company/'][href*='/life/']",
    "a[href*='/company/']",
]
JOB_DETAILS_SELECTORS = [
    # SDUI layout (2025+)
    "main#workspace",
    "[data-sdui-screen='com.linkedin.sdui.flagshipnav.jobs.JobDetails']",
    # legacy selectors
    ".jobs-search__job-details--container",
    ".jobs-details",
    ".job-view-layout",
    "[data-job-id]",
    "body",
]
WORKPLACE_TYPES = ("Remote", "Hybrid", "On-site", "Onsite")
NAVIGATION_TIMEOUT_MS = 30_000
DETAIL_SEPARATOR = "\u00b7"
MOJIBAKE_DETAIL_SEPARATORS = ("\u00c3\u201a\u00c2\u00b7", "\u00c2\u00b7")


@dataclass(frozen=True)
class ParsedJobDetails:
    company: str | None = None
    title: str | None = None
    location: str | None = None
    workplace_type: str | None = None
    posted_at: str | None = None


def collect_jobs_from_linkedin(
    user_data_dir: Path,
    chrome_profile_directory: str | None,
    pause_on_start: bool,
    keywords: str,
    location: str,
    max_pages: int | None,
    filter_reposted: bool,
    posted_within_seconds: int,
    headless: bool,
    page_pause_seconds: float,
) -> list[JobPosting]:
    results = collect_jobs_for_targets_from_linkedin(
        user_data_dir=user_data_dir,
        chrome_profile_directory=chrome_profile_directory,
        pause_on_start=pause_on_start,
        targets=[SearchTarget(country=location, job_title=keywords)],
        max_pages=max_pages,
        filter_reposted=filter_reposted,
        posted_within_seconds=posted_within_seconds,
        headless=headless,
        page_pause_seconds=page_pause_seconds,
    )
    return results[0][1] if results else []


def collect_jobs_for_targets_from_linkedin(
    user_data_dir: Path,
    chrome_profile_directory: str | None,
    pause_on_start: bool,
    targets: list[SearchTarget],
    max_pages: int | None,
    filter_reposted: bool,
    posted_within_seconds: int,
    headless: bool,
    page_pause_seconds: float,
    exclude_title_words: list[str] | None = None,
    exclude_company_names: list[str] | None = None,
) -> list[tuple[SearchTarget, list[JobPosting]]]:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    user_data_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(
        collect_target_jobs_with_persistent_context(
            playwright_factory=async_playwright,
            user_data_dir=user_data_dir,
            chrome_profile_directory=chrome_profile_directory,
            pause_on_start=pause_on_start,
            targets=targets,
            max_pages=max_pages,
            filter_reposted=filter_reposted,
            posted_within_seconds=posted_within_seconds,
            headless=headless,
            page_pause_seconds=page_pause_seconds,
            exclude_title_words=exclude_title_words or [],
            exclude_company_names=exclude_company_names or [],
            timeout_error_type=PlaywrightTimeoutError,
            playwright_error_type=PlaywrightError,
        )
    )


async def collect_target_jobs_with_persistent_context(
    playwright_factory,
    user_data_dir: Path,
    chrome_profile_directory: str | None,
    pause_on_start: bool,
    targets: list[SearchTarget],
    max_pages: int | None,
    filter_reposted: bool,
    posted_within_seconds: int,
    headless: bool,
    page_pause_seconds: float,
    exclude_title_words: list[str],
    exclude_company_names: list[str],
    timeout_error_type,
    playwright_error_type,
) -> list[tuple[SearchTarget, list[JobPosting]]]:
    launch_args = []
    if chrome_profile_directory:
        launch_args.append(f"--profile-directory={chrome_profile_directory}")

    async with playwright_factory() as playwright:
        try:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                channel="chrome",
                headless=headless,
                viewport={"width": 1365, "height": 900},
                args=launch_args,
            )
        except playwright_error_type as exc:
            raise RuntimeError(
                "Chrome could not start with that profile. If you are using your "
                "personal Chrome profile, fully close all Chrome windows first, "
                "then run the command again."
            ) from exc

        try:
            page = await new_controlled_page(context)
            if pause_on_start:
                print("Chrome is open. If needed, navigate this tab manually, then press Enter here.")
                input()
            await ensure_logged_in(page, context, timeout_error_type, headless=headless)

            results: list[tuple[SearchTarget, list[JobPosting]]] = []
            for target in targets:
                print(f"Searching '{target.job_title}' in {target.country}")
                jobs = await scrape_search_results(
                    page=page,
                    keywords=target.job_title,
                    location=target.country,
                    max_pages=max_pages,
                    filter_reposted=filter_reposted,
                    posted_within_seconds=posted_within_seconds,
                    page_pause_seconds=page_pause_seconds,
                    exclude_title_words=exclude_title_words,
                    exclude_company_names=exclude_company_names,
                    timeout_error_type=timeout_error_type,
                )
                results.append((target, jobs))
            return results
        finally:
            await context.close()


async def new_controlled_page(context):
    page = await context.new_page()
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    await page.bring_to_front()

    for existing_page in context.pages:
        if existing_page == page:
            continue
        if existing_page.url == "about:blank":
            try:
                await existing_page.close()
            except Exception:
                pass

    return page


async def ensure_logged_in(page, context, timeout_error_type, headless: bool) -> None:
    await navigate(page, "https://www.linkedin.com/feed/", timeout_error_type)
    if await has_linkedin_session(context):
        return

    if headless:
        raise RuntimeError(
            "Headless mode requires an existing LinkedIn session in the selected Chrome profile. "
            "Run once with headless: false, log in manually, then run headless again."
        )

    await navigate(page, "https://www.linkedin.com/login", timeout_error_type)
    print("LinkedIn login is required in the Chrome window.")
    print("Complete login, MFA, or CAPTCHA manually, then press Enter here.")
    input()

    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except timeout_error_type:
        pass

    if not await has_linkedin_session(context):
        raise RuntimeError("LinkedIn session cookie was not found after login.")


async def navigate(page, url: str, timeout_error_type) -> None:
    print(f"Opening: {url}")
    for attempt in range(1, 3):
        if await navigate_with_goto(page, url, timeout_error_type):
            return
        if await navigate_with_address_bar(page, url):
            return
        if attempt < 2:
            await page.wait_for_timeout(1_000)

    raise RuntimeError(
        f"Chrome stayed on an empty page while opening {url}. Fully close all "
        "Chrome windows from Task Manager and run the same command again."
    )


async def navigate_with_goto(page, url: str, timeout_error_type) -> bool:
    try:
        await page.bring_to_front()
        await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    except timeout_error_type:
        return page.url not in {"about:blank", ""}
    return page.url not in {"about:blank", ""}


async def navigate_with_address_bar(page, url: str) -> bool:
    try:
        print("Standard navigation stayed blank; trying Chrome address bar.")
        await page.bring_to_front()
        await page.keyboard.press("Control+L")
        await page.keyboard.type(url, delay=5)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
    except Exception:
        return page.url not in {"about:blank", ""}
    return page.url not in {"about:blank", ""}


async def has_linkedin_session(context) -> bool:
    cookies = await context.cookies("https://www.linkedin.com")
    return any(cookie["name"] == "li_at" for cookie in cookies)


async def scrape_search_results(
    page,
    keywords: str,
    location: str,
    max_pages: int | None,
    filter_reposted: bool,
    posted_within_seconds: int,
    page_pause_seconds: float,
    exclude_title_words: list[str],
    exclude_company_names: list[str],
    timeout_error_type,
) -> list[JobPosting]:
    links_by_id: dict[str, JobLink] = {}
    empty_pages = 0

    page_index = 0
    while max_pages is None or page_index < max_pages:
        start = page_index * 25
        page_index += 1
        await navigate(
            page,
            build_jobs_search_url(
                keywords=keywords,
                location=location,
                start=start,
                seconds=posted_within_seconds,
            ),
            timeout_error_type,
        )

        try:
            await page.wait_for_selector(
                "a[href*='/jobs/view/'], a[href*='currentJobId=']",
                timeout=15_000,
            )
        except timeout_error_type:
            empty_pages += 1
            if empty_pages >= 2:
                break
            continue

        await scroll_results(page)
        page_links = await extract_job_links_from_page(page)
        if not page_links:
            empty_pages += 1
            if empty_pages >= 2:
                break
        else:
            empty_pages = 0

        before_count = len(links_by_id)
        had_previous_jobs = before_count > 0
        for job_link in page_links:
            links_by_id.setdefault(job_link.job_id, job_link)

        if had_previous_jobs and len(links_by_id) == before_count:
            break

        await asyncio.sleep(page_pause_seconds)

    return await scrape_job_details(
        page=page,
        job_links=list(links_by_id.values()),
        filter_reposted=filter_reposted,
        page_pause_seconds=page_pause_seconds,
        exclude_title_words=exclude_title_words,
        exclude_company_names=exclude_company_names,
        timeout_error_type=timeout_error_type,
    )


async def scrape_job_details(
    page,
    job_links: list[JobLink],
    filter_reposted: bool,
    page_pause_seconds: float,
    exclude_title_words: list[str],
    exclude_company_names: list[str],
    timeout_error_type,
) -> list[JobPosting]:
    if not job_links:
        return []

    print(f"Opening {len(job_links)} job detail pages one at a time.")
    postings: list[JobPosting] = []
    for job_link in job_links:
        posting = await scrape_job_detail(
            page=page,
            job_link=job_link,
            filter_reposted=filter_reposted,
            exclude_title_words=exclude_title_words,
            exclude_company_names=exclude_company_names,
            timeout_error_type=timeout_error_type,
        )
        if posting is not None:
            postings.append(posting)
        await asyncio.sleep(page_pause_seconds)
    return postings


async def scroll_results(page) -> None:
    for _ in range(4):
        await page.mouse.wheel(0, 1800)
        await page.wait_for_timeout(700)


async def extract_job_links_from_page(page) -> list[JobLink]:
    links: list[JobLink] = []
    seen_ids: set[str] = set()

    for card in await find_job_cards(page):
        link = await first_job_link(card)
        normalized = normalize_linkedin_job_url(link)
        if normalized is None:
            continue

        job_id, url = normalized
        if job_id in seen_ids:
            continue

        links.append(JobLink(job_id=job_id, url=url))
        seen_ids.add(job_id)

    if links:
        return links

    return await extract_job_links_from_links(page)


async def scrape_job_detail(page, job_link: JobLink, filter_reposted: bool, exclude_title_words: list[str], exclude_company_names: list[str], timeout_error_type) -> JobPosting | None:
    await navigate(page, job_link.url, timeout_error_type)
    await wait_for_detail_page_loaded(page, timeout_error_type)
    try:
        await page.wait_for_selector("body", timeout=15_000)
    except timeout_error_type:
        pass

    parsed_details = await extract_structured_job_details_from_page(page)
    detail_text = await get_job_detail_text(page)
    posted_at = parsed_details.posted_at or extract_posted_at(detail_text)
    if filter_reposted and posted_at and "reposted" in posted_at.lower():
        return None

    company = parsed_details.company or await extract_detail_company(page, detail_text)
    if company and exclude_company_names:
        company_lower = company.lower()
        if any(name.lower() in company_lower for name in exclude_company_names):
            return None
    selected_title = parsed_details.title or await extract_detail_title_from_page(page)
    title = extract_detail_title(selected_title, detail_text, company=company)
    if title and exclude_title_words:
        title_lower = title.lower()
        if any(word.lower() in title_lower for word in exclude_title_words):
            return None
    location = parsed_details.location or extract_location(detail_text)
    workplace_type = parsed_details.workplace_type or extract_workplace_type(detail_text)

    return JobPosting(
        job_id=job_link.job_id,
        url=job_link.url,
        title=title,
        company=company,
        location=location,
        workplace_type=workplace_type,
        posted_at=posted_at,
    )


async def wait_for_detail_page_loaded(page, timeout_error_type) -> None:
    try:
        await page.wait_for_load_state("load", timeout=NAVIGATION_TIMEOUT_MS)
    except timeout_error_type:
        pass

    try:
        await page.wait_for_selector(", ".join(JOB_DETAILS_SELECTORS), timeout=15_000)
    except timeout_error_type:
        pass


async def find_job_cards(page):
    for selector in JOB_CARD_SELECTORS:
        cards = page.locator(selector)
        if await cards.count() > 0:
            return await cards.all()
    return []


async def find_job_details_panels(page):
    panels = []
    for selector in JOB_DETAILS_SELECTORS:
        matches = page.locator(selector)
        try:
            if await matches.count() > 0:
                panels.extend(await matches.all())
        except Exception:
            continue
    return panels


def has_reposted_label(card_text: str | None) -> bool:
    if not card_text:
        return False
    return any(
        clean_text(line).lower().startswith("reposted")
        for line in card_text.splitlines()
        if clean_text(line)
    )


async def get_job_detail_text(page) -> str | None:
    texts = [await safe_inner_text(panel) for panel in await find_job_details_panels(page)]
    return "\n".join(text for text in texts if text)


async def extract_structured_job_details_from_page(page) -> ParsedJobDetails:
    return infer_job_details_from_htmls(await get_detail_container_html(page))


async def get_detail_container_html(page) -> list[str]:
    html_fragments: list[str] = []
    for selector in DETAIL_HTML_CONTAINERS:
        matches = page.locator(selector)
        try:
            count = await matches.count()
        except Exception:
            continue

        for index in range(min(count, 3)):
            html = await safe_inner_html(matches.nth(index))
            if html:
                html_fragments.append(html)
    return html_fragments


def infer_job_details_from_htmls(html_fragments: list[str]) -> ParsedJobDetails:
    combined = ParsedJobDetails()
    for html in html_fragments:
        details = infer_job_details_from_html(html)
        combined = ParsedJobDetails(
            company=combined.company or details.company,
            title=combined.title or details.title,
            location=combined.location or details.location,
            workplace_type=combined.workplace_type or details.workplace_type,
            posted_at=combined.posted_at or details.posted_at,
        )
        if all(
            [
                combined.company,
                combined.title,
                combined.location,
                combined.workplace_type,
                combined.posted_at,
            ]
        ):
            break
    return combined


def infer_job_details_from_html(html: str | None) -> ParsedJobDetails:
    if not html:
        return ParsedJobDetails()

    parser = JobDetailHtmlParser()
    parser.feed(html)

    company = infer_company_from_html_parser(parser)
    title = infer_title_from_html_parser(parser, company=company)
    location, posted_at = infer_location_and_posted_at_from_html_parser(parser)
    workplace_type = infer_workplace_type_from_html_parser(parser)

    return ParsedJobDetails(
        company=company,
        title=title,
        location=location,
        workplace_type=workplace_type,
        posted_at=posted_at,
    )


def infer_company_from_html_parser(parser: "JobDetailHtmlParser") -> str | None:
    for label in parser.aria_labels:
        company = company_from_aria_label_text(label)
        if company:
            return company

    for element in parser.elements:
        href = element.attrs.get("href", "")
        if element.tag == "a" and "/company/" in href:
            company = clean_text(element.text)
            if company:
                return company

    return None


def infer_title_from_html_parser(
    parser: "JobDetailHtmlParser",
    company: str | None = None,
) -> str | None:
    ignored = {company.lower()} if company else set()
    for element in parser.elements:
        if element.tag not in {"h1", "h2", "p"}:
            continue

        candidate = clean_text(element.text)
        if not candidate or candidate.lower() in ignored:
            continue
        if looks_like_job_title(candidate):
            return candidate

    return None


def infer_location_and_posted_at_from_html_parser(
    parser: "JobDetailHtmlParser",
) -> tuple[str | None, str | None]:
    for element in parser.elements:
        if element.tag != "p":
            continue

        segments = split_detail_segments(element.text)
        if len(segments) < 2:
            continue

        posted_at = next(
            (
                segment
                for segment in segments
                if segment.lower().startswith("reposted") or " ago" in segment.lower()
            ),
            None,
        )
        if not posted_at:
            continue

        location = next(
            (segment for segment in segments if not is_noise_detail_segment(segment)),
            None,
        )
        return location, posted_at

    return None, None


def infer_workplace_type_from_html_parser(parser: "JobDetailHtmlParser") -> str | None:
    for text in parser.texts:
        for workplace_type in WORKPLACE_TYPES:
            if text.lower() == workplace_type.lower():
                return "On-site" if workplace_type == "Onsite" else workplace_type
    return None


async def extract_detail_title_from_page(page) -> str | None:
    selected_title = clean_text(await first_text(page, TITLE_SELECTORS))
    if selected_title and not is_bad_title(selected_title):
        return selected_title

    for html in await get_title_container_html(page):
        title = infer_title_from_html(html)
        if title:
            return title

    return selected_title


async def get_title_container_html(page) -> list[str]:
    html_fragments: list[str] = []
    for selector in TITLE_HTML_CONTAINERS:
        matches = page.locator(selector)
        try:
            count = await matches.count()
        except Exception:
            continue

        for index in range(min(count, 3)):
            html = await safe_inner_html(matches.nth(index))
            if html:
                html_fragments.append(html)
    return html_fragments


def infer_title_from_html(html: str | None) -> str | None:
    if not html:
        return None

    parser = CandidateTextParser(target_tags={"h1", "h2", "p"})
    parser.feed(html)
    for text in parser.texts:
        candidate = clean_text(text)
        if candidate and looks_like_job_title(candidate):
            return candidate
    return None


def extract_detail_title(
    selected_title: str | None,
    detail_text: str | None,
    company: str | None = None,
) -> str | None:
    if selected_title and not is_bad_title(selected_title):
        return selected_title
    return infer_title_from_detail_text(detail_text, company=company)


async def extract_detail_company(page, detail_text: str | None) -> str | None:
    company = await company_from_aria_label(page)
    if company:
        return company

    company = clean_text(await first_text(page, COMPANY_SELECTORS))
    if company:
        return company

    lines = meaningful_lines(detail_text)
    return lines[1] if len(lines) > 1 else None


def infer_title_from_detail_text(detail_text: str | None, company: str | None = None) -> str | None:
    ignored = {company.lower()} if company else set()
    for line in meaningful_lines(detail_text):
        normalized = line.lower()
        if normalized in ignored:
            continue
        if not looks_like_job_title(line):
            continue
        if len(split_detail_segments(line)) > 1:
            continue
        if "·" in line or "Â·" in line:
            continue
        if normalized in {workplace_type.lower() for workplace_type in WORKPLACE_TYPES}:
            continue
        if normalized == "full-time":
            continue
        return line
    return None


_BAD_TITLES = {
    "home", "jobs", "linkedin", "my network", "messaging", "me",
    "for business", "premium", "post a job",
}

def is_bad_title(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        "notification" in normalized
        or normalized in _BAD_TITLES
        or normalized.startswith("skip to")
    )


def looks_like_job_title(value: str) -> bool:
    normalized = value.strip().lower()
    if is_bad_title(value):
        return False
    if len(normalized) < 3 or len(normalized) > 180:
        return False
    if len(split_detail_segments(value)) > 1:
        return False
    if normalized in {workplace_type.lower() for workplace_type in WORKPLACE_TYPES}:
        return False
    if normalized in {"full-time", "part-time", "contract", "temporary", "internship"}:
        return False
    if any(marker in normalized for marker in (" ago", "people clicked apply")):
        return False
    return True


async def company_from_aria_label(page) -> str | None:
    company_elements = page.locator("[aria-label^='Company,']")
    try:
        if await company_elements.count() == 0:
            return None
        label = await company_elements.first.get_attribute("aria-label")
    except Exception:
        return None
    if not label:
        return None
    return company_from_aria_label_text(label)


def company_from_aria_label_text(label: str) -> str | None:
    if not label.startswith("Company,"):
        return None
    return clean_text(label.removeprefix("Company,").rstrip("."))


def extract_location(detail_text: str | None) -> str | None:
    for line in meaningful_lines(detail_text):
        segments = split_detail_segments(line)
        if len(segments) < 2:
            continue
        first_segment = segments[0]
        if not is_noise_detail_segment(first_segment):
            return first_segment
    return None


def extract_workplace_type(detail_text: str | None) -> str | None:
    lines = meaningful_lines(detail_text)
    for workplace_type in WORKPLACE_TYPES:
        if any(line.lower() == workplace_type.lower() for line in lines):
            return "On-site" if workplace_type == "Onsite" else workplace_type
    return None


def extract_posted_at(detail_text: str | None) -> str | None:
    for line in meaningful_lines(detail_text):
        for segment in split_detail_segments(line):
            normalized = segment.lower()
            if normalized.startswith("reposted") or " ago" in normalized:
                return segment
    return None


def split_detail_segments(line: str) -> list[str]:
    normalized = line
    for separator in MOJIBAKE_DETAIL_SEPARATORS:
        normalized = normalized.replace(separator, DETAIL_SEPARATOR)
    return [segment.strip() for segment in normalized.split(DETAIL_SEPARATOR) if segment.strip()]
    normalized = line.replace("Â·", "·")
    return [segment.strip() for segment in normalized.split("·") if segment.strip()]


def is_noise_detail_segment(segment: str) -> bool:
    lowered = segment.lower()
    return any(marker in lowered for marker in ("reposted", " ago", "people clicked apply"))


def meaningful_lines(text: str | None) -> list[str]:
    if not text:
        return []
    return [line for line in (clean_text(raw_line) for raw_line in text.splitlines()) if line]


async def first_job_link(locator) -> str | None:
    links = locator.locator("a[href*='/jobs/view/'], a[href*='currentJobId=']")
    if await links.count() == 0:
        return None
    return await links.first.get_attribute("href")


async def first_text(locator, selectors: list[str]) -> str | None:
    for selector in selectors:
        matches = locator.locator(selector)
        if await matches.count() > 0:
            return await safe_inner_text(matches.first)
    return None


async def safe_inner_text(locator) -> str | None:
    try:
        return await locator.inner_text(timeout=2_000)
    except Exception:
        return None


async def safe_inner_html(locator) -> str | None:
    try:
        return await locator.inner_html(timeout=2_000)
    except Exception:
        return None


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def infer_company_from_card_text(
    card_text: str | None,
    title: str | None,
    location: str | None,
) -> str | None:
    if not card_text:
        return None

    ignored = {
        value.lower()
        for value in [title, location]
        if value
    }
    ignored_prefixes = (
        "promoted",
        "viewed",
        "applicants",
        "apply",
        "reposted",
        "actively recruiting",
    )

    for raw_line in card_text.splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        normalized = line.lower()
        if normalized in ignored:
            continue
        if any(normalized.startswith(prefix) for prefix in ignored_prefixes):
            continue
        if " ago" in normalized:
            continue
        return line

    return None


async def extract_job_links_from_links(page) -> list[JobLink]:
    job_links: list[JobLink] = []
    seen_ids: set[str] = set()

    link_elements = await page.locator("a[href*='/jobs/view/'], a[href*='currentJobId=']").all()
    for link in link_elements:
        normalized = normalize_linkedin_job_url(await link.get_attribute("href"))
        if normalized is None:
            continue

        job_id, url = normalized
        if job_id in seen_ids:
            continue

        job_links.append(JobLink(job_id=job_id, url=url))
        seen_ids.add(job_id)

    return job_links


class CandidateTextParser(HTMLParser):
    def __init__(self, target_tags: set[str]):
        super().__init__()
        self.target_tags = target_tags
        self.active_tag: str | None = None
        self.parts: list[str] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.target_tags and self.active_tag is None:
            self.active_tag = tag
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.active_tag is not None:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self.active_tag:
            return

        text = clean_text(" ".join(self.parts))
        if text:
            self.texts.append(text)
        self.active_tag = None
        self.parts = []


@dataclass
class ParsedHtmlElement:
    tag: str
    attrs: dict[str, str]
    parts: list[str]

    @property
    def text(self) -> str:
        return clean_text(" ".join(self.parts)) or ""


class JobDetailHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements: list[ParsedHtmlElement] = []
        self.active_elements: list[ParsedHtmlElement] = []
        self.aria_labels: list[str] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        aria_label = attrs_dict.get("aria-label")
        if aria_label:
            self.aria_labels.append(aria_label)

        if tag in {"h1", "h2", "p", "a", "span"}:
            self.active_elements.append(
                ParsedHtmlElement(tag=tag, attrs=attrs_dict, parts=[])
            )

    def handle_data(self, data: str) -> None:
        for element in self.active_elements:
            element.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.active_elements) - 1, -1, -1):
            element = self.active_elements[index]
            if element.tag != tag:
                continue

            completed = self.active_elements.pop(index)
            if completed.text:
                self.elements.append(completed)
                self.texts.append(completed.text)
            return
