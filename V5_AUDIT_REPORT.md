# Chopster by Aris v5 — Audit Report

## Fixed

- PyAV/faster-whisper compatibility: `av>=11,<19`.
- Windows subtitle temp-file locking / `WinError 32`.
- False export failures caused by cleanup errors.
- Non-atomic final output writes: renderer now uses a temporary render file and verifies it before replacing the final output.
- FFmpeg cancellation: active render can be terminated instead of waiting for completion.
- Background UI safety in ClipperPage: worker functions no longer read Qt widgets/project state directly.
- Duplicate clipper task protection.
- Transcript re-run overhead: transcription cache keyed by source/config.
- Transcript editor changes are reflected in generated/saved subtitles.
- Caption clip selection now includes overlapping transcript segments, not only fully-contained segments.
- Project restore loads saved transcript data.
- Image watermark audio mapping.
- Vertical/aspect + subtitle + watermark combined rendering.
- Media probe rotation parsing precedence.

## Added

- Smart Pipeline: transcribe → highlight → subtitle → captions → render.
- Text watermark and image watermark.
- Watermark position, opacity and size.
- Burn-subtitle export integration.
- Cancel Export button.
- Render status/stat cards.
- Premium workspace treatment matching the Downloader visual language.
- Windows helper scripts: `install_dependencies.bat`, `run_chopster.bat`.
- Improved PyInstaller collection for `faster_whisper`, `ctranslate2`, and `av`.

## Automated checks

- Python compileall: PASS
- Worker UI-access audit: PASS
- Core tests: PASS
- E2E video split/export: PASS
- Subtitle burn E2E: PASS
- Text watermark + subtitle + 9:16 render: PASS
- Image watermark + audio render: PASS
- Transcript cache-key regression: PASS
- Theme stylesheet generation: PASS

## Environment limitation

The audit environment did not have PySide6 installed and could not download packages because external package access was unavailable. Therefore the UI was parser/compile audited and the worker architecture was statically checked, but a live Qt window could not be launched in this environment.

On the target Windows machine, run `install_dependencies.bat`, then `run_chopster.bat`. For a portable EXE, run `build_exe.bat`.
