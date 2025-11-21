# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Radio Sampler is a single-file Python application that concurrently samples multiple internet radio streams, captures short audio clips, and filters out silent content. It uses FFmpeg for stream capture and silence detection, and can either fetch station URLs from the Radio Browser API or read from a file.

## Core Architecture

The application is structured around these key components:

- **API Integration** (`fetch_station_urls`): Retrieves radio station URLs from Radio Browser API with filtering by codec, bitrate, and operational status
- **Async Stream Processing** (`capture_stream`, `process_all_streams`): Handles concurrent FFmpeg subprocess execution for multiple streams using asyncio
- **Silence Detection** (`silence_detected`): Parses FFmpeg stderr output to calculate silence ratios and discard clips exceeding the threshold
- **Main Loop** (`main`): Orchestrates single-run or continuous sampling cycles with configurable intervals

## Running the Application

### Basic Usage

Fetch stations from API and sample:
```bash
python3 radio-sampler.py --fetch --output-dir ./output
```

Use a custom station list:
```bash
python3 radio-sampler.py --urls stations.txt --output-dir ./output
```

### Continuous Sampling

Run in loop mode with custom interval:
```bash
python3 radio-sampler.py --fetch --output-dir ./output --loop --interval 120.0
```

### Common Parameters

- `--duration 4.0`: Clip length in seconds
- `--timeout 10.0`: Per-stream connection timeout
- `--silence-threshold -40dB`: FFmpeg silencedetect noise level
- `--max-silence-ratio 0.75`: Discard clips with >75% silence
- `--codec MP3 --bitrate-min 64 --limit 500`: API filtering options

## Dependencies

The script requires:
- Python 3.7+ (uses asyncio.run)
- FFmpeg binary in PATH (checked at startup)
- Python packages: Install via `pip install -r requirements.txt`

## Key Implementation Details

**Concurrency Model**: All streams are captured concurrently via `asyncio.gather()` on individual `capture_stream` tasks. Each task spawns an FFmpeg subprocess and waits for completion with timeout.

**Output Format**: WAV files at 44.1kHz, 2-channel, 16-bit signed PCM. Filenames use pattern `clip_YYYYMMDD_HHMMSS_chN.wav` where N is the station index. The output directory is created automatically if it doesn't exist.

**Error Handling**: Failed streams (timeout, FFmpeg error, excess silence) are logged and their partial output files are cleaned up. The script continues processing remaining streams.

**Silence Detection**: FFmpeg's silencedetect filter runs during capture. Post-capture analysis sums all silence durations from stderr and compares against total clip duration.
