# Radio Sampler

A Python tool for concurrently sampling multiple internet radio streams and capturing audio clips with automatic silence detection.

## Features

- Fetch radio station URLs from the [Radio Browser API](https://www.radio-browser.info/) or use a custom list
- Concurrent stream sampling using async I/O
- Automatic silence detection and filtering
- Configurable clip duration, timeout, and quality settings
- Continuous sampling mode for long-running data collection
- High-quality WAV output (44.1kHz, stereo, 16-bit)

## Installation

### Prerequisites

1. **Python 3.7 or higher**
   ```bash
   python3 --version
   ```

2. **FFmpeg** - Required for stream capture and audio processing

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get update
   sudo apt-get install ffmpeg
   ```

   **macOS (Homebrew):**
   ```bash
   brew install ffmpeg
   ```

   **Windows:**
   Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install requests
```

## Quick Start

Sample 10 random radio stations from the API:

```bash
python3 radio-sampler.py --fetch --limit 10 --output-dir ./samples
```

This will:
- Fetch 10 MP3 radio station URLs
- Capture 4-second clips from each station concurrently
- Save clips to `./samples/` directory (created automatically)
- Filter out clips with >75% silence

## Usage

### Basic Commands

**Fetch stations from Radio Browser API:**
```bash
python3 radio-sampler.py --fetch --output-dir ./output
```

**Use a custom station list:**
```bash
python3 radio-sampler.py --urls stations.txt --output-dir ./output
```

**Continuous sampling (runs indefinitely):**
```bash
python3 radio-sampler.py --fetch --output-dir ./output --loop --interval 300
```

### Command-Line Options

#### Station Source
- `--fetch` - Fetch station URLs from Radio Browser API
- `--urls FILE` - Read station URLs from a text file (one per line)

#### API Filtering (when using `--fetch`)
- `--server SERVER` - API mirror server (default: `all.api.radio-browser.info`)
  - Alternative servers: `de1.api.radio-browser.info`, `fr1.api.radio-browser.info`
- `--codec CODEC` - Codec filter (default: `MP3`, options: `AAC`, `OGG`, etc.)
- `--bitrate-min KBPS` - Minimum bitrate in kbps (default: `64`)
- `--limit COUNT` - Maximum number of stations (default: `500`)

#### Content Filtering (when using `--fetch`)
- `--tag TAG` - Filter by genre/content tag (e.g., `jazz`, `news`, `classical`, `rock`, `pop`)
- `--name NAME` - Filter by station name, partial match (e.g., `"BBC"`, `"Radio"`)
- `--language LANG` - Filter by broadcast language (e.g., `english`, `spanish`, `french`)
- `--country COUNTRY` - Filter by country (e.g., `usa`, `uk`, `france`, `germany`)

#### Output Settings
- `--output-dir DIR` - Output directory for WAV clips (required, created if missing)
- `--duration SECONDS` - Clip duration in seconds (default: `4.0`)
- `--timeout SECONDS` - Per-stream connection timeout (default: `10.0`)

#### Silence Detection
- `--silence-threshold LEVEL` - FFmpeg silencedetect noise level (default: `-40dB`)
- `--silence-min-duration SECONDS` - Minimum silence duration to detect (default: `0.3`)
- `--max-silence-ratio RATIO` - Max allowed silence ratio, 0.0-1.0 (default: `0.75`)

#### Loop Mode
- `--loop` - Enable continuous sampling
- `--interval SECONDS` - Seconds between sampling cycles (default: `60.0`)

### Examples

**Sample jazz stations only:**
```bash
python3 radio-sampler.py --fetch --tag jazz --output-dir ./jazz-samples
```

**English-language news stations with high quality:**
```bash
python3 radio-sampler.py --fetch --tag news --language english \
  --codec MP3 --bitrate-min 128 --output-dir ./news-clips
```

**Classical music from European stations:**
```bash
python3 radio-sampler.py --fetch --tag classical --country france \
  --output-dir ./classical-eu
```

**Search for specific stations by name:**
```bash
python3 radio-sampler.py --fetch --name "BBC Radio" --output-dir ./bbc-samples
```

**Combine multiple filters for precise targeting:**
```bash
python3 radio-sampler.py --fetch --tag rock --language english --country usa \
  --codec AAC --bitrate-min 128 --limit 50 --output-dir ./rock-usa
```

**High-quality AAC stations with strict silence filtering:**
```bash
python3 radio-sampler.py --fetch --codec AAC --bitrate-min 128 \
  --output-dir ./hq-samples --max-silence-ratio 0.5
```

**Longer clips with more generous timeout:**
```bash
python3 radio-sampler.py --fetch --duration 10 --timeout 20 \
  --output-dir ./long-clips
```

**Sample from a specific list every 5 minutes:**
```bash
python3 radio-sampler.py --urls my-stations.txt --output-dir ./output \
  --loop --interval 300
```

**Adjust silence detection sensitivity:**
```bash
# More sensitive (catches quieter passages as silence)
python3 radio-sampler.py --fetch --output-dir ./output \
  --silence-threshold -50dB

# Less sensitive (only very quiet parts count as silence)
python3 radio-sampler.py --fetch --output-dir ./output \
  --silence-threshold -30dB
```

## Custom Station Lists

Create a text file with one stream URL per line:

```
# my-stations.txt
http://stream.example.com/radio1
http://stream.example.com/radio2
# Lines starting with # are ignored
http://stream.example.com/radio3
```

Then use it:
```bash
python3 radio-sampler.py --urls my-stations.txt --output-dir ./output
```

## Output Files

Clips are saved with timestamped filenames:
```
clip_20231120_143052_ch1.wav
clip_20231120_143052_ch2.wav
clip_20231120_143052_ch3.wav
```

Format: `clip_YYYYMMDD_HHMMSS_chN.wav` where N is the station index.

All files are 44.1kHz stereo WAV (16-bit signed PCM).

## How It Works

1. **Station Discovery**: Fetches station URLs from Radio Browser API or reads from file
2. **Concurrent Capture**: Spawns async FFmpeg subprocesses for each stream simultaneously
3. **Silence Detection**: FFmpeg's silencedetect filter analyzes audio during capture
4. **Quality Filtering**: Post-processing analyzes silence ratio and discards poor clips
5. **Output**: Successful clips are saved as WAV files

Streams that timeout, fail to connect, or exceed the silence threshold are logged and skipped.

## Troubleshooting

**"ffmpeg not found in PATH"**
- Install FFmpeg (see Installation section)
- Verify with: `ffmpeg -version`

**Many timeout errors**
- Increase `--timeout` value (default is 10 seconds)
- Try a lower `--limit` to reduce concurrent connections
- Check your internet connection

**All clips are being discarded as silent**
- Lower `--max-silence-ratio` (e.g., `0.5` instead of `0.75`)
- Adjust `--silence-threshold` to be less sensitive (e.g., `-30dB`)

**No stations returned from API / DNS resolution errors**
- Try a different `--server`: `--server all.api.radio-browser.info` or `--server de1.api.radio-browser.info`
- See [Radio Browser servers](https://www.radio-browser.info/) for more options
- Relax filters: lower `--bitrate-min`, remove `--codec` restriction

## License

This project is provided as-is for educational and research purposes.

## Acknowledgments

Radio station data provided by [Radio Browser API](https://www.radio-browser.info/).
