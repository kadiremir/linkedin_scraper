import requests
from bs4 import BeautifulSoup

url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

if __name__ == "__main__":
    start = 0
    total = 0

    while True:
        params = {
            "keywords": "Software Engineer",
            "location": "Czechia",
            "start": start,
            "f_TPR": "r86400",  # last 24 hours
        }
        response = requests.get(url, params=params, headers=headers)
        print(f"Page start={start} | Status: {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        job_cards = soup.find_all("li")

        if not job_cards:
            print("No more jobs found. Done.")
            break

        for card in job_cards:
            title = card.find("h3")
            company = card.find("h4")
            link_tag = card.find("a", href=True)
            job_url = link_tag["href"].split("?")[0] if link_tag else "N/A"
            if title or company:
                total += 1
                print(
                    (title.text.strip() if title else "N/A"),
                    "|",
                    (company.text.strip() if company else "N/A"),
                    "|",
                    job_url,
                )

        start += 25

    print(f"\nTotal jobs scraped: {total}")
