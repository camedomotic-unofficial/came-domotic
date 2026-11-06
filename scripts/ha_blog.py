"""Track which Home Assistant contributors blog posts have been reviewed.

The ledger (``.claude/skills/ha-blog-review/ledger.json``) records a verdict for
every blog post. This script diffs the RSS feed against it, so no post is ever
missed, and keeps the ledger sorted and consistently formatted. It uses only the
standard library so it can run in GitHub Actions without installing anything.

Subcommands:
  new        Print unseen posts as JSON (input for the review).
  record     Merge verdicts from a JSON file into the ledger.
  baseline   Mark all unseen posts published before a date as ``baseline``.
  open       Print ledger entries that still need attention.
  issue-body Print a Markdown summary for the monthly reminder issue.

Used by the ``/ha-blog-review`` skill and the ``ha-blog-reminder`` workflow.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import sys
from typing import Any
import urllib.request
import xml.etree.ElementTree as ET  # nosec B405 - trusted HTTPS feed, no DTDs

FEED_URL = "https://contributors.home-assistant.io/blog/rss.xml"
ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / ".claude" / "skills" / "ha-blog-review" / "ledger.json"
USER_AGENT = "came-domotic-ha-blog-check/1.0"

# Verdicts that keep a post on the radar until someone closes it.
OPEN_VERDICTS = ("action-needed", "watch")
VERDICTS = ("not-relevant", "done", "baseline", *OPEN_VERDICTS)
ENTRY_KEYS = (
    "url",
    "date",
    "title",
    "verdict",
    "reason",
    "deadline",
    "ref",
    "reviewed",
)


def fetch_feed(feed_file: str | None) -> list[dict[str, Any]]:
    """Return feed posts, newest first, from a local file or the live feed."""
    if feed_file:
        raw = Path(feed_file).read_bytes()
    else:
        # FEED_URL is a constant https:// URL, not user input.
        request = urllib.request.Request(  # noqa: S310
            FEED_URL, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310  # nosec B310
            raw = response.read()
    root = ET.fromstring(raw)  # noqa: S314  # nosec B314 - trusted HTTPS feed
    posts = []
    for item in root.iterfind("./channel/item"):
        published = parsedate_to_datetime(item.findtext("pubDate", ""))
        posts.append(
            {
                "url": (item.findtext("guid") or item.findtext("link") or "").strip(),
                "date": published.astimezone(UTC).date().isoformat(),
                "title": (item.findtext("title") or "").strip(),
                "categories": [c.text for c in item.iterfind("category") if c.text],
                "description": (item.findtext("description") or "").strip(),
            }
        )
    return posts


def load_ledger() -> dict[str, dict[str, Any]]:
    """Return ledger entries keyed by post URL."""
    if not LEDGER.exists():
        return {}
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    return {entry["url"]: entry for entry in data["posts"]}


def save_ledger(entries: dict[str, dict[str, Any]]) -> None:
    """Write the ledger sorted newest first, with a stable key order."""
    posts = [
        {key: entry[key] for key in ENTRY_KEYS if entry.get(key)}
        for entry in sorted(
            entries.values(), key=lambda e: (e["date"], e["url"]), reverse=True
        )
    ]
    data = {"feed": FEED_URL, "posts": posts}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def unseen(posts: list[dict[str, Any]], ledger: dict[str, Any]) -> list[dict]:
    """Return feed posts that have no ledger entry yet."""
    return [post for post in posts if post["url"] not in ledger]


def cmd_new(args: argparse.Namespace) -> int:
    """Print unseen posts as JSON."""
    posts = unseen(fetch_feed(args.feed_file), load_ledger())
    if args.since:
        posts = [post for post in posts if post["date"] >= args.since]
    json.dump(posts, sys.stdout, indent=2, ensure_ascii=False)
    print()
    print(f"{len(posts)} unseen post(s)", file=sys.stderr)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    """Merge verdicts from a JSON file (list of {url, verdict, reason, ...})."""
    verdicts = json.loads(Path(args.file).read_text(encoding="utf-8"))
    ledger = load_ledger()
    feed = {post["url"]: post for post in fetch_feed(args.feed_file)}
    errors = []
    for item in verdicts:
        url = item.get("url", "")
        if item.get("verdict") not in VERDICTS:
            errors.append(f"{url}: verdict must be one of {', '.join(VERDICTS)}")
            continue
        if item["verdict"] != "baseline" and not item.get("reason"):
            errors.append(f"{url}: a reason is required")
            continue
        base = ledger.get(url) or feed.get(url)
        if base is None:
            errors.append(f"{url}: not in the feed or the ledger")
            continue
        ledger[url] = {
            "url": url,
            "date": base["date"],
            "title": base["title"],
            **{k: v for k, v in item.items() if k in ENTRY_KEYS and k != "url"},
        }
    if errors:
        print("Nothing written:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    save_ledger(ledger)
    print(f"Recorded {len(verdicts)} verdict(s)", file=sys.stderr)
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    """Mark every unseen post published before a date as baseline."""
    ledger = load_ledger()
    old = [
        p for p in unseen(fetch_feed(args.feed_file), ledger) if p["date"] < args.before
    ]
    for post in old:
        ledger[post["url"]] = {
            "url": post["url"],
            "date": post["date"],
            "title": post["title"],
            "verdict": "baseline",
        }
    save_ledger(ledger)
    print(
        f"Marked {len(old)} post(s) before {args.before} as baseline", file=sys.stderr
    )
    return 0


def open_entries(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Return entries still needing attention, soonest deadline first."""
    entries = [e for e in ledger.values() if e["verdict"] in OPEN_VERDICTS]
    return sorted(entries, key=lambda e: (e.get("deadline") or "9999", e["date"]))


def cmd_open(args: argparse.Namespace) -> int:
    """Print open entries as JSON."""
    json.dump(open_entries(load_ledger()), sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


def cmd_issue_body(args: argparse.Namespace) -> int:
    """Print the reminder issue body; expose the unseen count to GitHub Actions."""
    ledger = load_ledger()
    new_posts = unseen(fetch_feed(args.feed_file), ledger)
    lines = [
        f"There are **{len(new_posts)}** Home Assistant contributors blog post(s) "
        "not yet reviewed for this integration.",
        "",
        "Run `/ha-blog-review` in Claude Code to triage them and update the "
        "ledger (`.claude/skills/ha-blog-review/ledger.json`). This issue is "
        "updated monthly and can be closed once the ledger is up to date.",
        "",
        "## Unreviewed posts",
        "",
    ]
    lines += [
        f"- {p['date']} [{p['title']}]({p['url']}) ({', '.join(p['categories'])})"
        for p in new_posts
    ]
    pending = open_entries(ledger)
    if pending:
        lines += ["", "## Still open from earlier reviews", ""]
        for entry in pending:
            extra = "".join(
                f" · {label} {entry[key]}"
                for key, label in (("deadline", "deadline"), ("ref", "tracked in"))
                if entry.get(key)
            )
            lines.append(
                f"- `{entry['verdict']}` [{entry['title']}]({entry['url']}){extra}"
            )
    print("\n".join(lines))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"unseen={len(new_posts)}\n")
    return 0


def _iso_date(value: str) -> str:
    """Validate a YYYY-MM-DD argument."""
    return date.fromisoformat(value).isoformat()


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run a subcommand."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed-file", help="read the feed from a local file")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="print unseen posts as JSON")
    new.add_argument("--since", type=_iso_date, help="only posts on/after this date")
    new.set_defaults(func=cmd_new)

    record = sub.add_parser("record", help="merge verdicts from a JSON file")
    record.add_argument("file")
    record.set_defaults(func=cmd_record)

    baseline = sub.add_parser("baseline", help="mark old unseen posts as baseline")
    baseline.add_argument("--before", type=_iso_date, required=True)
    baseline.set_defaults(func=cmd_baseline)

    sub.add_parser("open", help="print open entries").set_defaults(func=cmd_open)
    sub.add_parser("issue-body", help="print reminder issue body").set_defaults(
        func=cmd_issue_body
    )

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
