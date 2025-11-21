#!/usr/bin/env python3
import argparse
import asyncio
import datetime
import os
import re
import shutil
import sys
import requests
from typing import List, Optional

FFMPEG_BIN = "ffmpeg"
USER_AGENT = "RadioSampler/1.0"

# ----------------------------------------------------------
# Console logging
# ----------------------------------------------------------
def log_info(msg: str) -> None:
    print(f"[INFO] {msg}")

def log_warn(msg: str) -> None:
    print(f"[WARN] {msg}")

def log_error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)


# ----------------------------------------------------------
# Check FFmpeg availability
# ----------------------------------------------------------
def check_ffmpeg() -> bool:
    if shutil.which(FFMPEG_BIN) is None:
        log_error(f"{FFMPEG_BIN} not found in PATH. Please install FFmpeg.")
        return False
    return True


# ----------------------------------------------------------
# Fetch station URLs from Radio Browser API
# ----------------------------------------------------------
def fetch_station_urls(
    server: str,
    codec: str,
    bitrate_min: int,
    limit: int,
    tag: Optional[str] = None,
    name: Optional[str] = None,
    language: Optional[str] = None,
    country: Optional[str] = None
) -> List[str]:
    url = f"https://{server}/json/stations/search"

    params = {
        "codec": codec,
        "bitrateMin": bitrate_min,
        "lastcheckok": 1,
        "hidebroken": "true",
        "limit": limit
    }

    # Add optional content filters
    if tag:
        params["tag"] = tag
    if name:
        params["name"] = name
    if language:
        params["language"] = language
    if country:
        params["country"] = country

    headers = {
        "User-Agent": USER_AGENT
    }

    log_info(f"Fetching station list from Radio Browser API: {server}")

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        stations = response.json()
    except requests.RequestException as e:
        log_error(f"API request failed: {e}")
        return []
    except ValueError as e:
        log_error(f"JSON parsing failed: {e}")
        return []

    urls = []
    for st in stations:
        resolved = st.get("url_resolved")
        raw = st.get("url")
        if resolved:
            urls.append(resolved)
        elif raw:
            urls.append(raw)

    log_info(f"Received {len(urls)} usable station URLs")
    return urls


# ----------------------------------------------------------
# WAV output path
# ----------------------------------------------------------
def build_output_path(output_dir: str, index: int) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"clip_{timestamp}_ch{index}.wav")


# ----------------------------------------------------------
# Silence detection helper
# ----------------------------------------------------------
def silence_detected(stderr_output: str, duration: float, max_ratio: float) -> bool:
    durations = re.findall(r"silence_duration:\s*([0-9.]+)", stderr_output)
    total_silence = sum(float(d) for d in durations) if durations else 0.0
    if duration <= 0:
        return True
    return (total_silence / duration) >= max_ratio


# ----------------------------------------------------------
# FFmpeg capture
# ----------------------------------------------------------
async def capture_stream(
    url: str,
    output_path: str,
    duration: float,
    silence_threshold: str,
    silence_min_d: float,
    max_silence_ratio: float,
    timeout_s: float,
) -> Optional[str]:

    log_info(f"Sampling: {url}")

    cmd = [
        FFMPEG_BIN,
        "-hide_banner",
        "-loglevel", "info",
        "-y",
        "-i", url,
        "-t", str(duration),
        "-af", f"silencedetect=noise={silence_threshold}:d={silence_min_d}",
        "-ar", "44100",
        "-ac", "2",
        "-sample_fmt", "s16",
        output_path
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            log_warn(f"Timeout: {url}")
            proc.kill()
            await proc.communicate()
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

    except (OSError, ValueError) as e:
        log_error(f"FFmpeg execution error: {e}")
        return None

    if proc.returncode != 0:
        log_warn(f"FFmpeg error for {url}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

    stderr_text = stderr.decode(errors="replace")

    if silence_detected(stderr_text, duration, max_silence_ratio):
        log_info(f"Silent clip discarded: {url}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

    log_info(f"Saved: {output_path}")
    return output_path


# ----------------------------------------------------------
# Process all stations concurrently
# ----------------------------------------------------------
async def process_all_streams(
    urls: List[str],
    output_dir: str,
    duration: float,
    silence_threshold: str,
    silence_min_d: float,
    max_silence_ratio: float,
    timeout_s: float
):
    tasks = []
    for i, url in enumerate(urls, start=1):
        out = build_output_path(output_dir, i)
        tasks.append(capture_stream(
            url, out, duration, silence_threshold,
            silence_min_d, max_silence_ratio, timeout_s
        ))

    await asyncio.gather(*tasks)


# ----------------------------------------------------------
# CLI argument parsing
# ----------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Python Radio Sampler (single-file version)")
    p.add_argument("--fetch", action="store_true",
                   help="Fetch station URLs from Radio Browser API")
    p.add_argument("--server", default="all.api.radio-browser.info",
                   help="API mirror server")
    p.add_argument("--codec", default="MP3", help="Codec filter")
    p.add_argument("--bitrate-min", type=int, default=64, help="Minimum bitrate")
    p.add_argument("--limit", type=int, default=500, help="Limit station count")

    # Content filtering options
    p.add_argument("--tag", help="Filter by tag/genre (e.g., jazz, news, classical, rock)")
    p.add_argument("--name", help="Filter by station name (partial match)")
    p.add_argument("--language", help="Filter by language (e.g., english, spanish, french)")
    p.add_argument("--country", help="Filter by country (e.g., usa, uk, france)")

    p.add_argument("--urls", help="Optional text file with station URLs if not fetching")

    p.add_argument("--output-dir", required=True, help="Output directory for WAV clips")
    p.add_argument("--duration", type=float, default=4.0, help="Clip duration")
    p.add_argument("--timeout", type=float, default=10.0, help="Per-stream timeout")
    p.add_argument("--silence-threshold", default="-40dB", help="silencedetect noise level")
    p.add_argument("--silence-min-duration", type=float, default=0.3, help="Min silence duration")
    p.add_argument("--max-silence-ratio", type=float, default=0.75,
                   help="Max allowed silence ratio in clip")

    p.add_argument("--loop", action="store_true", help="Continuous sampling loop")
    p.add_argument("--interval", type=float, default=60.0,
                   help="Seconds between sampling cycles")

    return p.parse_args()


# ----------------------------------------------------------
# Main loop
# ----------------------------------------------------------
async def main():
    args = parse_args()

    if not check_ffmpeg():
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    log_info(f"Output directory: {args.output_dir}")

    if args.fetch:
        urls = fetch_station_urls(
            args.server,
            args.codec,
            args.bitrate_min,
            args.limit,
            tag=args.tag,
            name=args.name,
            language=args.language,
            country=args.country
        )
    else:
        if not args.urls or not os.path.isfile(args.urls):
            log_error("Must specify --urls path.txt or use --fetch")
            sys.exit(1)
        with open(args.urls) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        log_error("No station URLs available")
        sys.exit(1)

    log_info(f"Loaded {len(urls)} stations")

    while True:
        log_info("Starting sampling cycle")
        await process_all_streams(
            urls,
            args.output_dir,
            args.duration,
            args.silence_threshold,
            args.silence_min_duration,
            args.max_silence_ratio,
            args.timeout
        )

        if not args.loop:
            break

        log_info(f"Sleeping {args.interval} seconds...")
        await asyncio.sleep(args.interval)

    log_info("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted.")

