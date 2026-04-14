"""Engineering-oriented realtime geopolitical monitoring prototype.

Pipeline layers:
- Bronze: raw feed items (full payload fields)
- Silver: normalized + themed records
- Gold: deduplicated alert events
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as et

DEFAULT_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/worldNews",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
]

THEME_KEYWORDS: dict[str, list[str]] = {
    "trump": ["trump", "donald trump", "maga", "campaign"],
    "us_iran": ["iran", "tehran", "ofac", "sanction", "irgc", "hormuz", "u.s."],
    "military": ["strike", "missile", "drone", "navy", "attack", "retaliation"],
    "diplomacy": ["talks", "nuclear", "deal", "negotiation", "ceasefire"],
}

SOURCE_CREDIBILITY: dict[str, int] = {
    "whitehouse.gov": 95,
    "state.gov": 92,
    "home.treasury.gov": 92,
    "reuters.com": 90,
    "apnews.com": 88,
    "bbc.com": 86,
    "nytimes.com": 85,
    "aljazeera.com": 82,
}


@dataclass
class FeedItem:
    title: str
    link: str
    summary: str
    published_at: datetime
    source: str
    fetched_at: str


@dataclass
class SilverRecord:
    item_id: str
    title: str
    link: str
    source: str
    published_at: str
    themes: list[str]
    credibility_score: int
    summary: str


@dataclass
class Event:
    event_id: str
    title: str
    link: str
    published_at: str
    source: str
    themes: list[str]
    credibility_score: int
    impact_score: int
    urgency_level: str


class LayeredStore:
    """SQLite-backed bronze/silver/gold layered storage."""

    def __init__(self, db_path: str) -> None:
        self.conn: sqlite3.Connection = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bronze_raw_items (
                item_id TEXT PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                summary TEXT NOT NULL,
                published_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS silver_normalized_items (
                item_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                summary TEXT NOT NULL,
                published_at TEXT NOT NULL,
                themes TEXT NOT NULL,
                credibility_score INTEGER NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gold_events (
                event_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                published_at TEXT NOT NULL,
                themes TEXT NOT NULL,
                credibility_score INTEGER NOT NULL,
                impact_score INTEGER NOT NULL,
                urgency_level TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def write_bronze(self, item: FeedItem) -> str:
        item_id: str = sha1_text(f"{item.link}|{normalize_text(item.title)}")[:20]
        self.conn.execute(
            """
            INSERT OR REPLACE INTO bronze_raw_items
            (item_id, fetched_at, source, title, link, summary, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                item.fetched_at,
                item.source,
                item.title,
                item.link,
                item.summary,
                item.published_at.isoformat(),
            ),
        )
        return item_id

    def write_silver(self, record: SilverRecord) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO silver_normalized_items
            (item_id, processed_at, source, title, link, summary, published_at, themes, credibility_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.item_id,
                now_utc_iso(),
                record.source,
                record.title,
                record.link,
                record.summary,
                record.published_at,
                json.dumps(record.themes, ensure_ascii=False),
                record.credibility_score,
            ),
        )

    def write_gold(self, event: Event) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO gold_events
            (event_id, processed_at, source, title, link, published_at, themes, credibility_score, impact_score, urgency_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                now_utc_iso(),
                event.source,
                event.title,
                event.link,
                event.published_at,
                json.dumps(event.themes, ensure_ascii=False),
                event.credibility_score,
                event.impact_score,
                event.urgency_level,
            ),
        )

    def commit(self) -> None:
        self.conn.commit()

    def layer_stats(self) -> dict[str, int]:
        bronze: int = self.conn.execute("SELECT COUNT(*) FROM bronze_raw_items").fetchone()[0]
        silver: int = self.conn.execute("SELECT COUNT(*) FROM silver_normalized_items").fetchone()[0]
        gold: int = self.conn.execute("SELECT COUNT(*) FROM gold_events").fetchone()[0]
        return {"bronze": bronze, "silver": silver, "gold": gold}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_datetime(value: str) -> datetime:
    try:
        dt: datetime = parsedate_to_datetime(value)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def fetch_feed(url: str, timeout: int = 10) -> list[FeedItem]:
    request: Request = Request(url, headers={"User-Agent": "vnpy-monitor/0.2"})

    try:
        with urlopen(request, timeout=timeout) as response:
            payload: bytes = response.read()
    except URLError as exc:
        print(f"[WARN] fetch failed: {url} ({exc})", file=sys.stderr)
        return []

    try:
        root: et.Element = et.fromstring(payload)
    except et.ParseError as exc:
        print(f"[WARN] invalid xml: {url} ({exc})", file=sys.stderr)
        return []

    entries: list[FeedItem] = []
    source: str = urlparse(url).netloc.replace("www.", "")
    fetched_at: str = now_utc_iso()

    for node in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title: str = (node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        link: str = (node.findtext("link") or "").strip()

        if not link:
            atom_link_node: et.Element | None = node.find("{http://www.w3.org/2005/Atom}link")
            if atom_link_node is not None:
                link = atom_link_node.attrib.get("href", "").strip()

        summary: str = (
            node.findtext("description")
            or node.findtext("summary")
            or node.findtext("{http://www.w3.org/2005/Atom}summary")
            or ""
        ).strip()

        published_raw: str = (
            node.findtext("pubDate")
            or node.findtext("published")
            or node.findtext("updated")
            or node.findtext("{http://www.w3.org/2005/Atom}published")
            or node.findtext("{http://www.w3.org/2005/Atom}updated")
            or ""
        )

        if not title or not link:
            continue

        entries.append(
            FeedItem(
                title=title,
                link=link,
                summary=summary,
                published_at=parse_datetime(published_raw),
                source=source,
                fetched_at=fetched_at,
            )
        )

    return entries


def detect_themes(text: str) -> list[str]:
    normalized: str = normalize_text(text)
    themes: list[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            themes.append(theme)
    return themes


def source_credibility(link: str, fallback_source: str) -> int:
    host: str = urlparse(link).netloc.replace("www.", "")
    if host in SOURCE_CREDIBILITY:
        return SOURCE_CREDIBILITY[host]
    if fallback_source in SOURCE_CREDIBILITY:
        return SOURCE_CREDIBILITY[fallback_source]
    return 60


def impact_score(themes: list[str], credibility: int) -> int:
    score: int = 20
    if "us_iran" in themes:
        score += 20
    if "military" in themes:
        score += 30
    if "trump" in themes:
        score += 15
    if "diplomacy" in themes:
        score += 10
    score += int((credibility - 50) * 0.5)
    return max(0, min(100, score))


def urgency_level(score: int, credibility: int) -> str:
    if score >= 75 and credibility >= 80:
        return "P1"
    if score >= 55:
        return "P2"
    return "P3"


def to_silver(item_id: str, item: FeedItem) -> SilverRecord | None:
    themes: list[str] = detect_themes(f"{item.title} {item.summary}")
    if not themes:
        return None
    credibility: int = source_credibility(item.link, item.source)
    return SilverRecord(
        item_id=item_id,
        title=item.title,
        link=item.link,
        source=item.source,
        published_at=item.published_at.isoformat(),
        themes=themes,
        credibility_score=credibility,
        summary=item.summary,
    )


def to_gold(silver: SilverRecord) -> Event:
    fingerprint: str = normalize_text(silver.title)
    event_id: str = sha1_text(fingerprint)[:16]
    score: int = impact_score(silver.themes, silver.credibility_score)
    return Event(
        event_id=event_id,
        title=silver.title,
        link=silver.link,
        published_at=silver.published_at,
        source=silver.source,
        themes=silver.themes,
        credibility_score=silver.credibility_score,
        impact_score=score,
        urgency_level=urgency_level(score, silver.credibility_score),
    )


def run_once(feeds: list[str], store: LayeredStore) -> list[Event]:
    dedup_events: dict[str, Event] = {}

    for feed_url in feeds:
        for item in fetch_feed(feed_url):
            item_id: str = store.write_bronze(item)
            silver: SilverRecord | None = to_silver(item_id, item)
            if silver is None:
                continue
            store.write_silver(silver)
            event: Event = to_gold(silver)
            if event.event_id not in dedup_events or event.published_at > dedup_events[event.event_id].published_at:
                dedup_events[event.event_id] = event

    for event in dedup_events.values():
        store.write_gold(event)
    store.commit()

    return sorted(dedup_events.values(), key=lambda e: (e.urgency_level, e.published_at), reverse=True)


def print_events(events: list[Event], output: str) -> None:
    if output == "jsonl":
        for event in events:
            print(json.dumps(asdict(event), ensure_ascii=False))
        return

    for event in events:
        print(
            f"[{event.urgency_level}] {event.published_at} | {event.source} | "
            f"impact={event.impact_score} credibility={event.credibility_score}\n"
            f"  {event.title}\n"
            f"  {event.link}\n"
            f"  themes={','.join(event.themes)}\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realtime geopolitical monitor (bronze/silver/gold)")
    parser.add_argument("--config", default=None, help="Path to JSON config")
    parser.add_argument("--db-path", default="examples/geopolitical_monitoring/monitor.db", help="SQLite DB path")
    parser.add_argument("--interval", type=int, default=120, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--show-stats", action="store_true", help="Print layered storage stats after run")
    parser.add_argument("--output", choices=["pretty", "jsonl"], default="pretty", help="Output format")
    return parser.parse_args()


def load_config(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def completion_status() -> dict[str, int]:
    """Return engineering completion estimation for current MVP."""
    return {
        "data_ingestion": 70,
        "layered_storage": 65,
        "event_dedup_scoring": 60,
        "alert_delivery": 30,
        "observability": 20,
        "production_hardening": 15,
        "overall": 45,
    }


def main() -> int:
    args: argparse.Namespace = parse_args()
    config: dict[str, Any] = load_config(args.config)

    feeds: list[str] = config.get("feeds", DEFAULT_FEEDS)
    interval: int = int(config.get("interval", args.interval))
    output: str = str(config.get("output", args.output))

    store: LayeredStore = LayeredStore(args.db_path)

    if args.once:
        events: list[Event] = run_once(feeds, store)
        print_events(events, output)
        if args.show_stats:
            print(json.dumps({"layers": store.layer_stats(), "completion": completion_status()}, ensure_ascii=False, indent=2))
        return 0

    while True:
        print(f"\n=== poll @ {now_utc_iso()} ===")
        events = run_once(feeds, store)
        print_events(events, output)
        if args.show_stats:
            print(json.dumps({"layers": store.layer_stats(), "completion": completion_status()}, ensure_ascii=False, indent=2))
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
