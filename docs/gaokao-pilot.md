# Gaokao Digital Human Pilot

The pilot audience is confirmed as parents of Shaanxi students in the 2027 senior-high cohort. The internal-preview presenter is an original synthetic, non-real mature male teacher with a generic synthesized male voice; it does not clone a real person's face or voice.

Launch channels, the real lead-capture URL, reviewer/approver identities, and the live operator remain open. Until those are supplied, `target_channels` stays `internal_preview`, all outputs must show a conspicuous `PREVIEW` watermark, and publication/live operation remains disabled.

Validate the draft example:

```bash
python -m src.video_solution.cli validate-content \
  --package examples/gaokao/rank-vs-score-001.json \
  --mode validate \
  --report output/gaokao/rank-vs-score-001.validation.json
```

Production validation intentionally fails for the example because its source is pending, rights are empty, and the package is not approved:

```bash
python -m src.video_solution.cli validate-content \
  --package examples/gaokao/rank-vs-score-001.json \
  --mode production
```

The internal-preview implementation adds provider adapters behind this gate:

1. `EdgeTTSSpeechProvider` uses the generic `zh-CN-YunyangNeural` synthesized male voice, without voice cloning;
2. `FFmpegStaticAvatarProvider` composes a supplied original portrait behind a replaceable provider interface;
3. the renderer creates a 1080x1920 H.264 MP4 with burned-in subtitles and a visible internal-only watermark;
4. every attempt receives its own directory and immutable render manifest, including failed attempts.

Install the lightweight preview dependencies separately from the legacy GPU pipeline:

```bash
python -m pip install -r requirements-preview.txt
```

Render after an original portrait asset is available:

```bash
python -m src.video_solution.cli render-preview \
  --package examples/gaokao/rank-vs-score-001.json \
  --avatar assets/gaokao/gaokao-mature-male-teacher-v1.png \
  --output-dir output/gaokao/previews
```

The initial preview provider uses a still portrait. Lip sync and managed avatar providers remain later adapters and must not weaken the same validation, approval, rights, watermark, or manifest controls.

Customer facts and scripts remain owned by the Gaokao business unit. Do not put student personal data or provider secrets in this repository.
