#!/usr/bin/env python3
import argparse
import asyncio
import datetime
import os
import random
import re
import shutil
import sys
import requests
from typing import List, Optional

try:
    from pedalboard import Pedalboard, Chorus, Reverb, Distortion, Phaser, Delay
    from pedalboard import LadderFilter, Bitcrush, Compressor, PitchShift
    from pedalboard.io import AudioFile
    import numpy as np
    PEDALBOARD_AVAILABLE = True
except ImportError:
    PEDALBOARD_AVAILABLE = False

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
# DSP Effect Generation with Randomized Parameters
# ----------------------------------------------------------
def create_random_distortion():
    """Create distortion/overdrive with random drive amount"""
    drive_db = random.uniform(10, 40)
    return Distortion(drive_db=drive_db)

def create_random_bitcrusher():
    """Create bitcrusher with random bit depth"""
    bit_depth = random.uniform(4, 12)
    return Bitcrush(bit_depth=bit_depth)

def create_random_reverb():
    """Create reverb with randomized room size and wetness"""
    room_size = random.uniform(0.3, 0.95)
    damping = random.uniform(0.2, 0.8)
    wet_level = random.uniform(0.2, 0.6)
    dry_level = random.uniform(0.4, 0.8)
    return Reverb(
        room_size=room_size,
        damping=damping,
        wet_level=wet_level,
        dry_level=dry_level
    )

def create_random_delay():
    """Create delay with random time and feedback"""
    delay_seconds = random.uniform(0.1, 0.5)
    feedback = random.uniform(0.2, 0.6)
    mix = random.uniform(0.2, 0.5)
    return Delay(delay_seconds=delay_seconds, feedback=feedback, mix=mix)

def create_random_chorus():
    """Create chorus with random rate and depth"""
    rate_hz = random.uniform(0.5, 3.0)
    depth = random.uniform(0.2, 0.7)
    mix = random.uniform(0.3, 0.7)
    return Chorus(rate_hz=rate_hz, depth=depth, mix=mix)

def create_random_phaser():
    """Create phaser with random rate and depth"""
    rate_hz = random.uniform(0.5, 5.0)
    depth = random.uniform(0.3, 0.8)
    mix = random.uniform(0.3, 0.7)
    return Phaser(rate_hz=rate_hz, depth=depth, mix=mix)

def create_random_filter():
    """Create filter with random cutoff frequency"""
    mode_choice = random.choice(['LPF', 'HPF', 'BPF'])
    if mode_choice == 'LPF':
        cutoff = random.uniform(500, 5000)
        mode = LadderFilter.Mode.LPF12
    elif mode_choice == 'HPF':
        cutoff = random.uniform(200, 2000)
        mode = LadderFilter.Mode.HPF12
    else:  # BPF
        cutoff = random.uniform(800, 4000)
        mode = LadderFilter.Mode.BPF12

    resonance = random.uniform(0.1, 0.7)
    return LadderFilter(mode=mode, cutoff_hz=cutoff, resonance=resonance)

def create_random_pitch_shift():
    """Create pitch shift with random semitones shift"""
    # Shift between -12 and +12 semitones (1 octave down to 1 octave up)
    # More common shifts are smaller, so weight towards -5 to +5
    shift_choices = [-12, -7, -5, -3, -2, -1, 1, 2, 3, 5, 7, 12]
    semitones = random.choice(shift_choices)
    return PitchShift(semitones=semitones)

def create_random_extreme_pitch_shift():
    """Create extreme pitch shift for more creative/destructive effects"""
    # Larger shifts for more extreme effects (-24 to +24 semitones)
    semitones = random.choice([-24, -19, -12, -7, 7, 12, 19, 24])
    return PitchShift(semitones=semitones)

def create_random_effect_chain():
    """Create a random chain of 2-4 effects from different categories"""
    effect_pool = {
        'distortion': [create_random_distortion, create_random_bitcrusher],
        'spatial': [create_random_reverb, create_random_delay],
        'modulation': [create_random_chorus, create_random_phaser],
        'filter': [create_random_filter],
        'pitch': [create_random_pitch_shift, create_random_extreme_pitch_shift]
    }

    # Pick 2-4 effect categories randomly
    num_effects = random.randint(2, 4)
    categories = random.sample(list(effect_pool.keys()), num_effects)

    # Create effect chain
    effects = []
    for category in categories:
        effect_creator = random.choice(effect_pool[category])
        effects.append(effect_creator())

    # Add subtle compression at the end to prevent clipping
    effects.append(Compressor(threshold_db=-12, ratio=3))

    return Pedalboard(effects)

def normalize_audio(audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    """
    Normalize audio to target dB peak level

    Args:
        audio: Audio array (channels x samples)
        target_db: Target peak level in dB (default: -3.0 dB)

    Returns:
        Normalized audio array
    """
    # Find current peak level
    current_peak = np.abs(audio).max()

    # Avoid division by zero
    if current_peak == 0:
        return audio

    # Calculate target peak amplitude from dB
    target_amplitude = 10 ** (target_db / 20.0)

    # Calculate gain needed
    gain = target_amplitude / current_peak

    # Apply gain
    normalized = audio * gain

    return normalized

def normalize_file(file_path: str, target_db: float = -3.0) -> bool:
    """
    Normalize an audio file in place to target dB peak level

    Args:
        file_path: Path to audio file
        target_db: Target peak level in dB (default: -3.0 dB)

    Returns:
        True if successful, False otherwise
    """
    try:
        with AudioFile(file_path) as f:
            audio = f.read(f.frames)
            samplerate = f.samplerate

        # Normalize
        normalized = normalize_audio(audio, target_db)

        # Write back
        with AudioFile(file_path, 'w', samplerate, normalized.shape[0]) as f:
            f.write(normalized)

        return True
    except Exception as e:
        log_error(f"Normalization failed for {file_path}: {e}")
        return False

def apply_effects_to_file(input_path: str, output_path: str) -> bool:
    """Apply random effect chain to audio file"""
    try:
        board = create_random_effect_chain()

        with AudioFile(input_path) as f:
            audio = f.read(f.frames)
            samplerate = f.samplerate

        # Process audio
        effected = board(audio, samplerate)

        # Normalize effected audio to -3 dB
        effected = normalize_audio(effected, -3.0)

        # Write output
        with AudioFile(output_path, 'w', samplerate, effected.shape[0]) as f:
            f.write(effected)

        return True
    except Exception as e:
        log_error(f"Effect processing failed: {e}")
        return False


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
        # Support multiple tags with comma separation (tagList parameter)
        # All tags must match (AND logic)
        if ',' in tag:
            params["tagList"] = tag
        else:
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
def build_output_path(output_dir: str, index: int, suffix: str = "") -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if suffix:
        return os.path.join(output_dir, f"clip_{timestamp}_ch{index}_{suffix}.wav")
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
    apply_effects: bool = False,
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

    # Apply effects if requested
    if apply_effects and PEDALBOARD_AVAILABLE:
        # Rename original file to include "_original" suffix
        base, ext = os.path.splitext(output_path)
        original_path = f"{base}_original{ext}"
        os.rename(output_path, original_path)

        # Normalize original to -3 dB
        if normalize_file(original_path, -3.0):
            log_info(f"Normalized original: {original_path}")

        # Create effected version
        effected_path = f"{base}_effected{ext}"
        if apply_effects_to_file(original_path, effected_path):
            log_info(f"Applied effects: {effected_path}")
        else:
            log_warn(f"Effect processing failed, keeping original only")
    else:
        # No effects, just normalize the original file
        if PEDALBOARD_AVAILABLE and normalize_file(output_path, -3.0):
            log_info(f"Normalized: {output_path}")

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
    timeout_s: float,
    apply_effects: bool = False
):
    tasks = []
    for i, url in enumerate(urls, start=1):
        out = build_output_path(output_dir, i)
        tasks.append(capture_stream(
            url, out, duration, silence_threshold,
            silence_min_d, max_silence_ratio, timeout_s, apply_effects
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

    # DSP Effects
    p.add_argument("--apply-effects", action="store_true",
                   help="Apply random DSP effects (distortion, reverb, modulation, filters)")

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

    # Check pedalboard availability if effects requested
    if args.apply_effects and not PEDALBOARD_AVAILABLE:
        log_error("--apply-effects requires pedalboard library. Install with: pip install pedalboard numpy")
        sys.exit(1)

    if args.apply_effects:
        log_info("DSP effects enabled: Random effect chains will be applied to captured audio")

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
            args.timeout,
            args.apply_effects
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

