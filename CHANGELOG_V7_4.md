# Chopster by Aris v7.5 — Full Production Fix

## Framing & detection
- Scene Detection is now strictly visual and cannot overwrite camera focus.
- Pre-detection preview uses a lightweight current-frame subject lock.
- Full person analysis uses persistent track IDs, face + body subject envelopes, stable camera locks, and a body-only fallback when a face is temporarily missed.
- Long-video tracking decodes samples sequentially instead of doing a random seek for every sample.
- Aspect changes (9:16 / 3:4 / 4:5 / 1:1 / 4:3 / 16:9) are evaluated at render time using the current canvas ratio.

## Master pipeline
- Master Analysis is the single expensive analysis layer.
- Versioned transcript/scene/camera/master artifacts survive compatible upgrades and are invalidated by source signature changes.
- Auto Create Shorts uses Master Analysis and automatically opens Clip Queue after generation.
- Viral Analyzer includes direct Export Highlight Selected.

## AI content
- Rich content pack: multiple titles, captions, short description, long YouTube-style description, hashtags, SEO keywords, pinned comment, and thumbnail text.
- Selected highlight context is fed to the AI first so long podcasts do not let unrelated opening content dominate the generated copy.

## Downloader
- One real progress pipeline: indeterminate during connection/extraction, then actual yt-dlp percentage.
- Audio Track control: Auto (Indonesia first), Indonesia, English, Original/default.
- Preview reports available audio language metadata when yt-dlp exposes it.
- The app does not pretend a bare URL contains the browser player's selected alternate audio track.

## Responsive UX
- Narrow main windows use an icon-rail sidebar.
- Download workspace stacks source/control cards instead of squeezing columns.
- Clipper compresses header controls, hides secondary guidance, and keeps preview/tabs usable.
- Installer Deno validation only reports success after `deno --version` succeeds.

## Validation
- 49 automated regression tests passed.
- Python compileall passed.
- Full Windows GUI visual verification remains environment-specific and should be checked on the target Windows machine.


## v7.5 Resilient AI Orchestrator
- AI online is now an enhancement layer with circuit-breaker health state.
- Automatic local fallback is enabled by default for highlight, camera, content and vision workflows.
- Partial AI jobs keep successful remote results and merge local coverage instead of restarting.
- Added Settings checkbox: AUTO FALLBACK local.
- B-roll, transcript polish and voiceover script no longer crash the workflow when the provider is unavailable.
