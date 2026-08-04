# Gaokao Digital Human Pilot

The first engineering slice validates the versioned content package before any avatar, TTS, render, live, or publishing provider is called.

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

The next implementation slice will add provider adapters behind this gate:

1. TTS/voice provider;
2. avatar/lip-sync provider, initially evaluating the existing Wav2Lip wrapper against a managed API;
3. subtitle and channel composition;
4. immutable render manifest;
5. operator-supervised live playlist package.

Customer facts and scripts remain owned by the Gaokao business unit. Do not put student personal data or provider secrets in this repository.
