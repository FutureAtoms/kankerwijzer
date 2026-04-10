# kanker.nl

## What is this source?
The website https://www.kanker.nl is the Dutch national information platform for cancer patients, relatives, and healthcare professionals.  
It is initiated by KWF Kankerbestrijding, the Dutch Cancer Society (NFK), and IKNL.

The website provides:
- Patient-oriented medical information about cancer types
- Information about diagnostics, treatments, side effects, and aftercare
- Patient stories and experiences
- Practical guidance and support resources
<br><br>

## How can you access the data (for this hackathon)?
The website does **not** provide a public API. For the purpose of **hackathon prototyping only**, data can be accessed via **lightweight web scraping** of publicly available pages.

Do **not**:
- Scrape at scale
- Scrape personal stories, forums, or user-generated content
- Use the data for clinical decision-making or medical advice

A simple example on how to scrape a page:
```python
import requests
from bs4 import BeautifulSoup

url = "https://www.kanker.nl/kankersoorten/borstkanker/algemeen/wat-is-borstkanker"

results = {}
text = extract_page_text(url)
results[url] = text

results
```
<br>

## Ethical and legal considerations
- Always respect robots.txt: https://www.kanker.nl/robots.txt
- Attribute kanker.nl clearly when using the data
- Do not present extracted content as medical advice
- Use only for educational, demo, and prototype purposes
<br><br>

## Pre-generated dataset (recommended)
To save time during the hackathon, we already ran a **limited and controlled crawl** of public pages and stored the result as:

📁 `data/kanker_nl_pages_all.json`

This file contains:
- A dictionary mapping page URLs → extracted main text
- Only pages within `/kankersoorten/<KANKERSOORT>`
- No personal stories or forum content
- Text extracted from headings and paragraphs in the main content area

See the script we used below.
<br><br>

## Script we used
Running this script takes a while we don't recommend running it during the hackathon, it's shared here for clarity.

```python
from urllib.parse import urljoin, urlparse, urlunparse
import time
import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path

visited_global = set()
results = {}

def normalize(url):
        parsed = urlparse(url)
        return urlunparse(parsed._replace(query="", fragment="")).rstrip("/")

def path_belongs_to_kankersoort(url, kankersoort):
    parsed = urlparse(url)
    return parsed.path.startswith(f"/kankersoorten/{kankersoort}")

for kankersoort in kankersoorten_set:
    print(f"\n=== Crawling kankersoort: {kankersoort} ===")

    START_URL = f"https://www.kanker.nl/kankersoorten/{kankersoort}"
    ALLOWED_PREFIX = START_URL
    DELAY_SECONDS = 1.5

    visited_local = set()
    to_visit = [START_URL]

    while to_visit:
        url = normalize(to_visit.pop(0))

        # Skip if this URL was already seen in THIS crawl
        if url in visited_local:
            continue

        # Skip out-of-scope pages
        if not path_belongs_to_kankersoort(url, kankersoort):
            continue


        print(
            f"Scraping: {url}\n"
            f"Visited (local): {len(visited_local)} | Queue: {len(to_visit)} | "
            f"Visited (global): {len(visited_global)}"
        )

        try:
            response = requests.get(url, headers=HEADERS)
            soup = BeautifulSoup(response.text, "html.parser")

            # Store ONLY if never stored globally
            if url not in visited_global:
                results[url] = {
                    "kankersoort": kankersoort,
                    "text": extract_text_from_soup(soup)
                }
                visited_global.add(url)

            visited_local.add(url)

            # Discover links
            for a in soup.find_all("a", href=True):
                link = normalize(urljoin(url, a["href"]))
                if (
                    path_belongs_to_kankersoort(link, kankersoort)
                    and link not in visited_local
                    and link not in to_visit
                ):
                    to_visit.append(link)

            time.sleep(DELAY_SECONDS)

        except Exception as e:
            print(f"Failed: {url} ({e})")

Path("data").mkdir(exist_ok=True)

with open("data/kanker_nl_pages_all.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```