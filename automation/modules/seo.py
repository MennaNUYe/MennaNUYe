"""Module 4b: broken-link scanning, sitemap generation, and search engine pings."""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, tostring

from bs4 import BeautifulSoup

from automation.core.config import AutomationConfig, require_env
from automation.core.http import build_session
from automation.core.logging_config import configure_logging

logger = configure_logging()


def crawl_site(base_url: str, max_pages: int = 500) -> tuple[set[str], list[tuple[str, int]]]:
    session = build_session()
    base_host = urlparse(base_url).netloc
    queue: deque[str] = deque([base_url])
    visited: set[str] = set()
    broken: list[tuple[str, int]] = []
    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            response = session.get(url, timeout=20)
            if response.status_code >= 400:
                broken.append((url, response.status_code))
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.select("a[href]"):
                href = urldefrag(urljoin(url, anchor["href"]))[0]
                parsed = urlparse(href)
                if parsed.scheme in {"http", "https"} and parsed.netloc == base_host and href not in visited:
                    queue.append(href)
        except Exception as exc:
            logger.warning("Broken/unreachable link %s: %s", url, exc)
            broken.append((url, 0))
    return visited, broken


def write_sitemap(urls: set[str], output: Path) -> None:
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for url in sorted(urls):
        item = SubElement(urlset, "url")
        SubElement(item, "loc").text = url
    output.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(urlset, encoding="utf-8"))
    logger.info("Wrote sitemap with %s URLs: %s", len(urls), output)


def ping_search_engines(sitemap_url: str) -> None:
    session = build_session()
    endpoints = [
        f"https://www.google.com/ping?sitemap={sitemap_url}",
        f"https://www.bing.com/ping?sitemap={sitemap_url}",
    ]
    for endpoint in endpoints:
        try:
            response = session.get(endpoint, timeout=15)
            logger.info("Pinged %s with status %s", endpoint, response.status_code)
        except Exception as exc:
            logger.warning("Search ping failed for %s: %s", endpoint, exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan SEO health and generate sitemap.xml.")
    parser.add_argument("--output", default="sitemap.xml")
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--ping", action="store_true")
    args = parser.parse_args()
    require_env(["WEBSITE_URL"])
    config = AutomationConfig()
    urls, broken = crawl_site(config.website_url, args.max_pages)
    for url, status in broken:
        logger.error("Broken link detected: %s status=%s", url, status)
    write_sitemap(urls, Path(args.output))
    if args.ping:
        ping_search_engines(f"{config.website_url.rstrip('/')}/{args.output}")


if __name__ == "__main__":
    main()
