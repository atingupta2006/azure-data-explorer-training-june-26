"""Fetch and parse Microsoft Learn pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

LEARN_HOST = "learn.microsoft.com"
USER_AGENT = "ADX-TCS-Training-DocCrawler/1.0 (maintainer; educational indexing)"


@dataclass
class PageDocument:
    url: str
    title: str
    topic: str
    text: str
    outbound_links: list[str]


def normalize_learn_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.fragment:
        parsed = parsed._replace(fragment="")
    # Drop query for stable dedup (view= params still work without them on many pages)
    path = parsed.path.rstrip("/") or parsed.path
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


def is_allowed_learn_path(path: str, prefixes: list[str]) -> bool:
    for prefix in prefixes:
        if path.startswith(prefix):
            return True
    return False


def extract_links(html: str, base_url: str, prefixes: list[str]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#"):
            continue
        absolute = normalize_learn_url(urljoin(base_url, href))
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != LEARN_HOST:
            continue
        if is_allowed_learn_path(parsed.path, prefixes):
            links.add(absolute)
    return sorted(links)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body
    if not main:
        return unescape(soup.get_text("\n", strip=True))
    return unescape(main.get_text("\n", strip=True))


def fetch_page(url: str, topic: str = "general", timeout: float = 45.0) -> PageDocument:
    url = normalize_learn_url(url)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url
    title = re.sub(r"\s+\|\s+Microsoft Learn\s*$", "", title)
    text = html_to_text(html)
    prefixes = [
        "/en-us/azure/data-explorer/",
        "/en-us/kusto/",
        "/en-us/training/modules/",
    ]
    return PageDocument(
        url=url,
        title=title,
        topic=topic,
        text=text,
        outbound_links=extract_links(html, url, prefixes),
    )


def crawl_from_seeds(
    seed_pairs: list[tuple[str, str]],
    *,
    max_depth: int = 1,
    prefixes: list[str] | None = None,
    max_pages: int = 120,
) -> list[PageDocument]:
    """BFS crawl from seeds within allowed Learn paths."""
    prefixes = prefixes or [
        "/en-us/azure/data-explorer/",
        "/en-us/kusto/",
        "/en-us/training/modules/",
    ]
    seen: set[str] = set()
    queue: list[tuple[str, str, int]] = [(topic, normalize_learn_url(url), 0) for topic, url in seed_pairs]
    docs: list[PageDocument] = []

    while queue and len(docs) < max_pages:
        topic, url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            doc = fetch_page(url, topic=topic)
        except Exception as exc:  # noqa: BLE001 — collect failures, continue crawl
            docs.append(
                PageDocument(
                    url=url,
                    title=f"FETCH_FAILED: {exc}",
                    topic=topic,
                    text="",
                    outbound_links=[],
                )
            )
            continue
        docs.append(doc)
        if depth < max_depth:
            for link in doc.outbound_links:
                if link not in seen:
                    queue.append((topic, link, depth + 1))
    return docs
