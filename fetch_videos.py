#!/usr/bin/env python3
"""
fetch_videos.py
Scrapes YouTube via yt-dlp and writes ONE JSON file PER CATEGORY
under categories/, plus categories/manifest.json so the app can
discover all categories automatically.

Safety: if a category comes back EMPTY (YouTube blocked the GitHub
server, timeout, ...), the old file is kept instead of being
overwritten with an empty list.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

OUTPUT_DIR = "categories"

# ---------------------------------------------------------------------
# SONG / HOME CATEGORIES
# ---------------------------------------------------------------------
SONG_CATEGORIES = {
    "home": [
        "ytsearch40:latest entertainment videos 2026",
        "ytsearch30:lifestyle vlog 2026",
        "ytsearch30:travel vlog 2026",
        "ytsearch30:tech videos 2026",
        "ytsearch30:cooking videos 2026",
        "ytsearch20:motivational videos 2026",
        "ytsearch20:documentary videos 2026",
        "ytsearch20:podcast interview 2026",
    ],
    "recently_uploaded": [
        "ytsearch50:latest uploaded music videos 2026",
        "ytsearch40:new songs released today 2026",
        "ytsearch30:new music videos 2026",
        "ytsearch30:latest Hindi songs 2026",
    ],
    "indian_pop_music": [
        "ytsearch50:Indian pop music 2026",
        "ytsearch40:new Indian pop songs 2026",
        "ytsearch30:Indian pop hits",
        "ytsearch20:Indian independent music 2026",
    ],
    "haryanvi": [
        "ytsearch50:new Haryanvi songs 2026",
        "ytsearch40:Haryanvi songs 2026",
        "ytsearch30:Haryanvi DJ songs",
        "ytsearch20:Haryanvi romantic songs",
        "ytsearch20:Haryanvi hits",
    ],
    "punjabi": [
        "ytsearch50:new Punjabi songs 2026",
        "ytsearch40:Punjabi songs 2026",
        "ytsearch30:Punjabi bhangra songs",
        "ytsearch30:Punjabi romantic songs",
        "ytsearch20:Punjabi sad songs",
    ],
    "storytelling": [
        "ytsearch40:Hindi storytelling videos",
        "ytsearch30:Hindi kahani",
        "ytsearch30:storytelling Hindi",
        "ytsearch20:Indian stories",
        "ytsearch20:Hindi story podcast",
    ],
    "music": [
        "ytsearch50:latest music 2026",
        "ytsearch40:Hindi music 2026",
        "ytsearch30:Indian music hits 2026",
        "ytsearch30:new songs 2026",
        "ytsearch20:music videos 2026",
    ],
    "gaming": [
        "ytsearch50:gaming videos 2026",
        "ytsearch40:Indian gaming 2026",
        "ytsearch30:gaming highlights 2026",
        "ytsearch30:BGMI gameplay",
        "ytsearch20:Free Fire gameplay",
        "ytsearch20:gaming livestream",
    ],
    "news": [
        "ytsearch50:India news latest 2026",
        "ytsearch40:latest India news",
        "ytsearch30:breaking news India",
        "ytsearch30:world news 2026",
        "ytsearch20:technology news 2026",
    ],
    "sports": [
        "ytsearch50:India sports latest 2026",
        "ytsearch40:cricket latest 2026",
        "ytsearch30:cricket highlights",
        "ytsearch30:football latest 2026",
        "ytsearch20:sports news 2026",
    ],
    "fashion": [
        "ytsearch40:Indian fashion 2026",
        "ytsearch30:fashion trends 2026",
        "ytsearch30:Indian fashion trends",
        "ytsearch20:fashion vlog India",
        "ytsearch20:latest fashion videos",
    ],
}

# ---------------------------------------------------------------------
# MOVIE CATEGORIES
# ---------------------------------------------------------------------
MOVIE_CATEGORIES = {
    "bollywood_movies": [
        "ytsearch30:Bollywood full movie 2026",
        "ytsearch30:Bollywood movie trailer 2026",
        "ytsearch20:Bollywood full movie Hindi",
    ],
    "hollywood_movies": [
        "ytsearch30:Hollywood movie trailer 2026",
        "ytsearch20:Hollywood full movie English",
        "ytsearch20:Hollywood movie Hindi dubbed",
    ],
    "south_indian_movies": [
        "ytsearch30:South Indian movie Hindi dubbed",
        "ytsearch20:South Indian movie trailer 2026",
        "ytsearch20:South Indian movies",
    ],
    "punjabi_movies": [
        "ytsearch20:Punjabi full movie",
        "ytsearch15:Punjabi movie trailer",
        "ytsearch15:Punjabi movies 2026",
    ],
}

# ---------------------------------------------------------------------
# YT-DLP
# ---------------------------------------------------------------------
YTDLP_BASE_ARGS = [
    "yt-dlp",
    "--flat-playlist",
    "--dump-json",
    "--no-warnings",
    "--ignore-errors",
]


def fetch_query(query: str, category: str):
    try:
        proc = subprocess.run(
            YTDLP_BASE_ARGS + [query],
            capture_output=True,
            text=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        print(f"[WARN] timeout: {query}", file=sys.stderr)
        return []

    videos = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        vid = data.get("id")
        if not vid:
            continue

        videos.append({
            "id": vid,
            "title": data.get("title", ""),
            "channel": data.get("channel") or data.get("uploader") or "",
            "thumbnail": (
                data.get("thumbnail")
                or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            ),
            "duration": data.get("duration") or 0,
            "category": category,
        })

    if not videos:
        err = (proc.stderr or "").strip().splitlines()
        if err:
            print(f"[WARN] no results for '{query}': {err[-1][:200]}", file=sys.stderr)

    return videos


def dedupe(videos):
    seen = set()
    out = []
    for video in videos:
        video_id = video.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        out.append(video)
    return out


def fetch_category(category: str, queries: list) -> list:
    print(f"[INFO] fetching category: {category}")
    collected = []
    for query in queries:
        print(f"[QUERY] {query}")
        collected.extend(fetch_query(query, category))
    deduped = dedupe(collected)
    print(f"[INFO]   -> {len(deduped)} unique videos")
    return deduped


def write_category_file(category: str, videos: list) -> int:
    """Writes the file and returns how many videos the file now holds."""
    path = os.path.join(OUTPUT_DIR, f"{category}.json")
    # Empty result (blocked / timeout): keep the old file, never overwrite with [].
    if not videos and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
            print(f"[SKIP] {category}: empty result, keeping old file ({len(old)} videos)")
            return len(old)
        except Exception:
            pass

    with open(path, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

    print(f"[DONE] wrote {path} - {len(videos)} videos")
    return len(videos)


def run_group(categories: dict, kind: str, manifest_categories: list):
    for category, queries in categories.items():
        videos = fetch_category(category, queries)
        count = write_category_file(category, videos)
        manifest_categories.append({
            "name": category,
            "type": kind,
            "file": f"{category}.json",
            "count": count,
        })


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest_categories = []

    run_group(SONG_CATEGORIES, "song", manifest_categories)
    run_group(MOVIE_CATEGORIES, "movie", manifest_categories)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": manifest_categories,
    }

    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[DONE] wrote {manifest_path} - {len(manifest_categories)} categories")


if __name__ == "__main__":
    main()
