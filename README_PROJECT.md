# YouTube Channel → segmentation pipeline (project scaffold)

This repository is a scaffold for a pipeline that:

- Fetches video lists (separating public videos / live replays / live pages) and writes a manifest (JSON/CSV).
- Downloads audio first (mp3/m4a) for ASR/transcription + alignment.
- Produces an initial segmentation/timeline from the transcript, then refines segments with an LLM.
- Cuts video aligned to keyframes, writes per-segment metadata, and supports audio censoring/muting.
- Supports translation, controlled-duration TTS, and optional voice fine-tuning.

Files created in this step:
- [requirements.txt](requirements.txt)
- [.github/workflows/ci.yml](.github/workflows/ci.yml)
- [src/video_solution/fetch_list.py](src/video_solution/fetch_list.py)
- [src/video_solution/downloader.py](src/video_solution/downloader.py)
- [src/video_solution/asr.py](src/video_solution/asr.py)
- [src/video_solution/segment.py](src/video_solution/segment.py)
- [src/video_solution/editor.py](src/video_solution/editor.py)
- [src/video_solution/censor.py](src/video_solution/censor.py)
- [src/video_solution/translate_tts.py](src/video_solution/translate_tts.py)
- [docs/chrome_cookies_windows.md](docs/chrome_cookies_windows.md)

Next suggested steps:

1. Implement `fetch_channel_list()` to call YouTube Data API or use `yt-dlp` scraping.
2. Implement ASR integration (e.g., `faster-whisper` + `whisperx` for alignment).
3. Implement censorship filtergraph and segment-aware ffmpeg trimming (keyframe-aware).
4. Create tests for each module and enable them in CI.

Quick run examples:

- Fetch channel/playlist list (JSON):

```bash
python -m src.video_solution.cli fetch-list --out output/list.json --format json --cookies cookies.txt --channel-url "<CHANNEL_OR_PLAYLIST_URL>"
```

- Download audio (example):

```bash
python scripts/test_download.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --out output/audio --cookies cookies.txt
```

Note: On Windows use an exported `cookies.txt` (Netscape format) from Chrome — do not base64 the file. See docs/chrome_cookies_windows.md

Cookie note: for Windows Chrome do not encode cookies; export a Netscape `cookies.txt` and provide its path to the downloader. See [docs/chrome_cookies_windows.md](docs/chrome_cookies_windows.md).
