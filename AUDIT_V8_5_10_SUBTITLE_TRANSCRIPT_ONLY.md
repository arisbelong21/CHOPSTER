# Chopster v8.5.10 — Transcript/Subtitle/AI Settings Audit

Scope: only transcript cache deletion, transcript->Settings AI cleanup/subtitle cues, Subtitle Engine UI layout, and Settings AI priority for transcript/subtitle/viral/caption.

## Changes
- Added exact transcript cache deletion for the selected source/model/language/word-timestamp settings.
- Delete Transcript also clears the project transcript artifact and generated transcript-derived SRT/ASS files so stale subtitle output cannot reappear.
- Fresh Transcribe still performs raw ASR with local Whisper for timing, then routes transcript cleanup/subtitle cue segmentation through the Settings AI via the existing AI Orchestrator; local fallback remains automatic.
- Improved Subtitle Engine grid stretching/size policy to prevent flattened controls and make settings usable at narrower widths.
- No Downloader, Browser Extension, Camera Director, Scene Detect, Gemini, Master Analysis, Auto Shorts, Publish, or other unrelated feature source was changed.

## Audit
- Targeted new/previous subtitle tests: 6 passed.
- Full non-legacy suite: 127 passed, 1 deselected, repeated 3 times.
- compileall: passed 3 times.
- Source diff: 2 existing source files changed plus 1 new test file; no other runtime feature files changed.

## Known pre-existing test mismatch
- `tests/test_v82_dual_ai_roles.py::test_config_schema7_clears_manual_ai` still expects schema 7 while the application defaults to schema 8. This was intentionally not changed because configuration migration is outside the requested scope.
