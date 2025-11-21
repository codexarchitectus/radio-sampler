# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Radio Sampler is a single-file Python application that concurrently samples multiple internet radio streams, captures short audio clips, and filters out silent content. It uses FFmpeg for stream capture and silence detection, and can either fetch station URLs from the Radio Browser API or read from a file.

## Core Architecture

The application is structured around these key components:

- **API Integration** (`fetch_station_urls`): Retrieves radio station URLs from Radio Browser API with filtering by codec, bitrate, operational status, and content (tags, language, country, station name)
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

### Content Filtering

Filter stations by specific content:
```bash
# Jazz stations only
python3 radio-sampler.py --fetch --tag jazz --output-dir ./output

# Multiple tags (ALL must match - finds stations with both jazz AND smooth tags)
python3 radio-sampler.py --fetch --tag "jazz,smooth" --output-dir ./output

# English-language news stations
python3 radio-sampler.py --fetch --tag news --language english --output-dir ./output

# Stations from a specific country
python3 radio-sampler.py --fetch --country usa --output-dir ./output

# Search by station name
python3 radio-sampler.py --fetch --name "BBC" --output-dir ./output

# Combine filters for precise targeting
python3 radio-sampler.py --fetch --tag classical --language french --country france --codec MP3 --bitrate-min 128 --output-dir ./output
```

### DSP Effects Processing

Apply random audio effects to captured clips for creative exploration:
```bash
# Enable random DSP effects (saves both original and processed versions)
python3 radio-sampler.py --fetch --tag jazz --output-dir ./output --apply-effects

# Combine with content filtering for targeted creative processing
python3 radio-sampler.py --fetch --tag rock --language english --output-dir ./output --apply-effects
```

Each clip generates two files:
- `clip_YYYYMMDD_HHMMSS_chN_original.wav` - Normalized capture (-3 dB peak)
- `clip_YYYYMMDD_HHMMSS_chN_effected.wav` - Randomly processed and normalized version

Effects include randomized chains of 2-4 effects from these categories:
- **Distortion**: Overdrive, bitcrushing (drive: 10-40dB, bit depth: 4-12 bits)
- **Spatial**: Reverb, delay (room size: 0.3-0.95, delay: 0.1-0.5s)
- **Modulation**: Chorus, phaser (rate: 0.5-5Hz, depth: 0.2-0.8)
- **Filtering**: Low/high/band-pass filters (cutoff: 200-5000Hz, resonance: 0.1-0.7)
- **Pitch**: Pitch shifting (±1-12 semitones, extreme mode: ±7-24 semitones)

**Normalization**: All captured audio is normalized to -3 dB peak level for consistent loudness across samples.

### Common Parameters

- `--duration 4.0`: Clip length in seconds
- `--timeout 10.0`: Per-stream connection timeout
- `--silence-threshold -40dB`: FFmpeg silencedetect noise level
- `--max-silence-ratio 0.75`: Discard clips with >75% silence
- `--codec MP3 --bitrate-min 64 --limit 500`: API filtering options
- `--tag jazz`: Filter by genre/content tag (e.g., jazz, news, classical, rock)
- `--tag "jazz,smooth"`: Multiple tags (comma-separated, ALL must match)
- `--language english`: Filter by broadcast language
- `--country usa`: Filter by country
- `--name "BBC"`: Filter by station name (partial match)

## Dependencies

The script requires:
- Python 3.7+ (uses asyncio.run)
- FFmpeg binary in PATH (checked at startup)
- Python packages: Install via `pip install -r requirements.txt`
  - `requests`: API communication
  - `pedalboard` (optional): DSP audio effects processing
  - `numpy` (optional): Required by pedalboard for audio manipulation

## Key Implementation Details

**Concurrency Model**: All streams are captured concurrently via `asyncio.gather()` on individual `capture_stream` tasks. Each task spawns an FFmpeg subprocess and waits for completion with timeout.

**Output Format**: WAV files at 44.1kHz, 2-channel, 16-bit signed PCM. Filenames use pattern `clip_YYYYMMDD_HHMMSS_chN.wav` where N is the station index. The output directory is created automatically if it doesn't exist.

**Error Handling**: Failed streams (timeout, FFmpeg error, excess silence) are logged and their partial output files are cleaned up. The script continues processing remaining streams.

**Silence Detection**: FFmpeg's silencedetect filter runs during capture. Post-capture analysis sums all silence durations from stderr and compares against total clip duration.
