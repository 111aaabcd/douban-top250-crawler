"""Fetch Douban Top250 data for learning and portfolio use.

The script collects the fields used by the resume project: rank, movie title,
rating, and the quote text shown on the list page. Douban page structure and
access controls may change, so the crawler validates the final dataset instead
of silently writing a partial result.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://movie.douban.com/top250"
PAGE_SIZE = 25
EXPECTED_COUNT = 250
FIELDS = ["排名", "电影名", "评分", "短评"]
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://movie.douban.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def fetch_page(session: requests.Session, start: int, retries: int = 3, timeout: int = 15) -> str:
    """Request one Top250 page with bounded retries."""
    for attempt in range(retries):
        try:
            response = session.get(BASE_URL, params={"start": start}, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch page start={start}") from exc
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable retry state")


def parse_movies(html: str) -> list[dict[str, str]]:
    """Parse rank, title, rating and quote from one list page."""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for item in soup.select("ol.grid_view > li"):
        rank = item.select_one("em")
        title = item.select_one("span.title")
        rating = item.select_one("span.rating_num")
        quote = item.select_one("span.inq")
        if not (rank and title and rating):
            continue
        records.append(
            {
                "排名": rank.get_text(strip=True),
                "电影名": title.get_text(strip=True),
                "评分": rating.get_text(strip=True),
                "短评": quote.get_text(strip=True) if quote else "",
            }
        )
    return records


def crawl_top250(delay_seconds: float = 1.0) -> list[dict[str, str]]:
    """Fetch all ten list pages."""
    movies: list[dict[str, str]] = []
    with requests.Session() as session:
        for start in range(0, EXPECTED_COUNT, PAGE_SIZE):
            movies.extend(parse_movies(fetch_page(session, start)))
            print(f"fetched page {start // PAGE_SIZE + 1}")
            time.sleep(delay_seconds)
    return movies


def validate_records(records: list[dict[str, str]], expected_count: int = EXPECTED_COUNT) -> None:
    """Validate the portfolio CSV before writing it."""
    if len(records) != expected_count:
        raise ValueError(
            f"expected {expected_count} records, got {len(records)}; "
            "check whether Douban blocked the request or changed the page structure"
        )

    ranks: list[int] = []
    titles: set[str] = set()
    for index, record in enumerate(records, start=1):
        try:
            rank = int(record["排名"])
            rating = float(record["评分"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"invalid rank or rating at parsed row {index}: {record}") from exc
        if not record.get("电影名", "").strip():
            raise ValueError(f"missing movie title at parsed row {index}")
        if not 0 <= rating <= 10:
            raise ValueError(f"rating out of range at parsed row {index}: {rating}")
        ranks.append(rank)
        titles.add(record["电影名"])

    expected_ranks = list(range(1, expected_count + 1))
    if ranks != expected_ranks:
        raise ValueError("rank sequence is incomplete or out of order")
    if len(titles) != len(records):
        raise ValueError("duplicate movie titles found")


def save_to_csv(records: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"saved {len(records)} records to {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Douban Top250 movie records.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("douban_top250.csv"),
        help="CSV path to write. Defaults to douban_top250.csv in the current directory.",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between page requests.")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write CSV even if fewer than 250 records are fetched.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = crawl_top250(delay_seconds=args.delay)
    if not args.allow_partial:
        validate_records(data)
    save_to_csv(data, args.output)


if __name__ == "__main__":
    main()
