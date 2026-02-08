"""Audio-first downloader utilities (audio-only to mp3/m4a).

Key points:
- Download audio only by default to save time (yt-dlp recommended).
- Accept a `cookies.txt` (Netscape) exported from Chrome (Windows). Do not encode it.
"""
from pathlib import Path
import subprocess
from typing import List, Optional


def download_audio(url: str, out_dir: str = "output/audio", cookies_path: Optional[str] = None, format_ext: str = "m4a", quiet: bool = True) -> List[str]:
    """Download audio-only stream(s) using `yt-dlp`.

    Workflow:
    1. Use `yt-dlp --get-filename` with an output template to determine expected filenames.
    2. Run `yt-dlp -x --audio-format <format>` to extract audio.

    Returns a list of downloaded file paths.

    Args:
        url: video/playlist/channel URL.
        out_dir: directory to write audio files.
        cookies_path: optional path to cookies.txt (Netscape format). Do not encode.
        format_ext: desired audio format (e.g., 'mp3', 'm4a').
        quiet: whether to suppress yt-dlp console output.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_template = f"{out_dir}/%(id)s.%(ext)s"

    base_cmd = ["yt-dlp"]
    if cookies_path:
        base_cmd += ["--cookies", cookies_path]

    # Step 1: get filenames that will be produced
    get_cmd = base_cmd + ["--get-filename", "-o", out_template, url]
    get_proc = subprocess.run(get_cmd, check=True, capture_output=True)
    filenames_raw = get_proc.stdout.decode("utf-8").strip().splitlines()
    expected_paths = [p.strip() for p in filenames_raw if p.strip()]

    # Step 2: download and extract audio
    download_cmd = base_cmd + ["-x", "--audio-format", format_ext, "-o", out_template, url]
    if quiet:
        # keep errors visible, but limit other output
        download_cmd = ["yt-dlp", "-q"] + ( ["--cookies", cookies_path] if cookies_path else []) + ["-x", "--audio-format", format_ext, "-o", out_template, url]

    subprocess.run(download_cmd, check=True)

    # Verify files exist; if yt-dlp produced different extensions, try to find matching files by id
    result_paths: List[str] = []
    for p in expected_paths:
        pth = Path(p)
        if pth.exists():
            result_paths.append(str(pth))
        else:
            # try to find by stem in out_dir
            matches = list(Path(out_dir).glob(pth.stem + "*"))
            for m in matches:
                if m.is_file():
                    result_paths.append(str(m))

    return result_paths

