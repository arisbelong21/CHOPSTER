"""Dependency-light regression checks for the Camera Director / Master Analysis path.

These tests intentionally avoid PySide6, OpenCV, FFmpeg and any network AI so they
run on every machine (including the audit sandbox). They cover the deterministic
parts of the camera pipeline plus the Master Analysis transcript-provenance fix.

Run with:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from chopster.clipper.camera_director import (
    ai_camera_director_visual,
    apply_ai_shots,
    interpolate_focus,
    make_clip_relative,
    normalize_points,
    stabilize_camera_path,
)
from chopster.clipper.master_analysis import _ai_signature


class _FakeResp:
    def __init__(self, text, raw=None):
        self.text = text
        self.raw = raw or {"provider": "fake"}


class _FakeOrchestrator:
    def __init__(self, text):
        self.text = text

    def generate_vision(self, prompt, image_paths, **kwargs):
        return _FakeResp(self.text)

    def generate(self, req, **kwargs):
        return _FakeResp(self.text)


def _noisy_points(targets):
    """Build a simple noisy detector timeline (one target per 40-sample block)."""
    pts = []
    t = 0.0
    for block in range(len(targets)):
        tid = targets[block]
        for i in range(40):
            pts.append({
                "t": round(t, 4), "x": 0.5, "y": 0.5, "source": "speaker-locked",
                "confidence": 0.7, "target_id": str(tid), "shot": "solo",
                "subject_left": 0.3, "subject_right": 0.7,
                "subject_top": 0.2, "subject_bottom": 0.8,
            })
            t += 0.75
    return pts


class NormalizeTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(normalize_points([]), [])

    def test_clamps_and_sorts(self):
        pts = normalize_points([
            {"t": 5.0, "x": 9.0, "y": -1.0, "target_id": "2"},
            {"t": 1.0, "x": 0.5, "y": 0.5, "target_id": "1"},
        ])
        self.assertEqual([p.t for p in pts], [1.0, 5.0])
        self.assertEqual(pts[-1].x, 1.0)  # clamped
        self.assertEqual(pts[-1].y, 0.0)  # clamped

    def test_dedups_same_timestamp(self):
        pts = normalize_points([
            {"t": 1.0, "x": 0.4, "confidence": 0.4, "target_id": "1"},
            {"t": 1.0, "x": 0.6, "confidence": 0.9, "target_id": "1"},
        ])
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].confidence, 0.9)


class StabilizeTests(unittest.TestCase):
    def test_locks_shot_and_removes_noise(self):
        stable = stabilize_camera_path(
            _noisy_points(["1", "2", "1"]),
            min_shot_duration=1.5, transition_duration=0.28, max_speed=0.48, max_step=0.10,
        )
        self.assertGreater(len(stable), 0)
        # The same-target run must not churn: 120 noisy samples collapse into a
        # small keyframe path (a few shots), far fewer than 120.
        self.assertLess(len(stable), 40)

    def test_empty_is_empty(self):
        self.assertEqual(stabilize_camera_path([]), [])


class ClipRelativeTests(unittest.TestCase):
    def test_shifts_clip_to_zero(self):
        pts = _noisy_points(["1"])
        rel = make_clip_relative(pts, 20.0, 40.0)
        self.assertGreater(len(rel), 0)
        self.assertLessEqual(rel[0]["t"], 0.001)

    def test_out_of_range_falls_back_to_center(self):
        pts = [{"t": 2.0, "x": 0.4, "y": 0.6, "source": "s", "confidence": 0.7, "target_id": "1", "shot": "solo"}]
        rel = make_clip_relative(pts, 50.0, 60.0)
        self.assertEqual(rel[0]["t"], 0.0)
        # A clip starting after the camera timeline holds the nearest (last) focus point.
        self.assertEqual(rel[0]["x"], 0.4)


class InterpolateTests(unittest.TestCase):
    def test_brackets_and_edges(self):
        pts = [{"t": 0.0, "x": 0.2, "y": 0.2, "target_id": "1"},
               {"t": 10.0, "x": 0.8, "y": 0.8, "target_id": "1"}]
        self.assertAlmostEqual(interpolate_focus(pts, 0.0)[0], 0.2)
        self.assertAlmostEqual(interpolate_focus(pts, 10.0)[0], 0.8)
        self.assertAlmostEqual(interpolate_focus(pts, 5.0)[0], 0.5)

    def test_empty_returns_center(self):
        self.assertEqual(interpolate_focus([], 3.0), (0.5, 0.5))


class AICameraDirectorTests(unittest.TestCase):
    TIMELINE = [
        {"t": i, "target_id": "1", "shot": "solo", "active_speaker": None,
         "faces": [{"id": "1", "x": 0.4, "y": 0.5, "left": 0.3, "right": 0.5, "top": 0.2, "bottom": 0.8, "motion": 1.2},
                   {"id": "2", "x": 0.6, "y": 0.5, "left": 0.5, "right": 0.7, "top": 0.2, "bottom": 0.8, "motion": 0.2}]}
        for i in range(20)
    ]

    def test_valid_decisions_become_compact_shots(self):
        good = ('{"decisions":[{"frame":1,"target_id":"1","shot":"solo","confidence":0.9,"reason":"a"},'
                '{"frame":2,"target_id":"2","shot":"solo","confidence":0.8,"reason":"b"}]}')
        shots = ai_camera_director_visual(
            _FakeOrchestrator(good), self.TIMELINE, "transcript",
            ["f1.jpg"] * 6, [0.0, 5.0, 10.0, 15.0, 18.0, 19.0],
        )
        self.assertGreater(len(shots), 0)

    def test_malformed_json_falls_back_locally(self):
        shots = ai_camera_director_visual(
            _FakeOrchestrator("{not json"), self.TIMELINE, "",
            ["f1.jpg"] * 4, [0.0, 5.0, 9.0, 11.0],
        )
        self.assertIsInstance(shots, list)

    def test_empty_image_times_uses_local_plan(self):
        shots = ai_camera_director_visual(_FakeOrchestrator("{}"), self.TIMELINE, "", [], [])
        self.assertIsInstance(shots, list)

    def test_apply_ai_shots_maps_model_label_to_local_tracker_id(self):
        pts = [{"t": i, "x": 0.5, "y": 0.5, "source": "s", "confidence": 0.6,
                "target_id": "9", "shot": "solo",
                "subject_left": 0.3, "subject_right": 0.7, "subject_top": 0.2, "subject_bottom": 0.8}
               for i in range(10)]
        shots = [{"start": 4.0, "end": 20.0, "target_id": "1", "shot": "solo", "reason": "r"}]
        timeline = [{"t": p["t"], "target_id": p["target_id"], "shot": p["shot"],
                     "faces": [{"id": "1", "x": 0.5, "y": 0.5, "left": 0.3, "right": 0.7, "top": 0.2, "bottom": 0.8}]}
                    for p in pts]
        out = apply_ai_shots(pts, shots, timeline=timeline, source_aspect=9 / 16, target_aspect=9 / 16)
        switched = [p for p in out if float(p.get("t", 0)) >= 4.0 and p.get("target_id") == "1"]
        self.assertGreater(len(switched), 0)


class MasterAnalysisSignatureTests(unittest.TestCase):
    def test_signature_changes_with_camera_director_flag(self):
        cfg = {"ai_provider": "none", "ai_model": "m", "ai_vision_model": "", "ai_camera_director": True}
        cfg2 = dict(cfg, ai_camera_director=False)
        self.assertNotEqual(_ai_signature(cfg), _ai_signature(cfg2))

    def test_signature_is_stable_for_same_config(self):
        cfg = {"ai_provider": "none", "ai_model": "m", "ai_vision_model": "", "ai_camera_director": True}
        self.assertEqual(_ai_signature(cfg), _ai_signature(dict(cfg)))


class MasterAnalysisTranscriptProvenanceTests(unittest.TestCase):
    """Regression for the stale-transcript bug: changing Whisper settings between
    two Master Analysis runs must re-transcribe instead of reusing the old artifact."""

    def test_model_change_forces_retranscription(self):
        from chopster.clipper.media_probe import MediaInfo
        from chopster.clipper.master_analysis import ensure_master_analysis
        from chopster.clipper.transcript_manager import Segment, Transcript

        meta = MediaInfo(path="x.mp4", duration=120.0, width=1920, height=1080, fps=30.0,
                         vcodec="h264", acodec="aac", has_audio=True, has_video=True,
                         rotation=0, bitrate=1000)
        tr = Transcript(language="id", segments=[Segment(0.0, 2.0, "Satu dua tiga", [])])
        tr2 = Transcript(language="id", segments=[Segment(0.0, 2.0, "Empat lima enam", [])])
        cfg = {"ai_provider": "none", "ai_endpoint": "", "ai_api_key": "",
               "ai_auto_visual": False, "ai_camera_director": True}

        base = [
            patch("chopster.clipper.master_analysis.probe", return_value=meta),
            patch("chopster.clipper.master_analysis.detect_scenes", return_value=[(0.0, 120.0)]),
            patch("chopster.clipper.master_analysis.analyze_scene_visuals", return_value={"source": "local", "scenes": []}),
            patch("chopster.clipper.master_analysis.detect_face_focus", side_effect=RuntimeError("no faces")),
            patch("chopster.clipper.master_analysis.extract_frame_images", side_effect=RuntimeError("no ffmpeg")),
            patch("chopster.clipper.master_analysis.save_cached_transcript", return_value=None),
            patch("chopster.clipper.master_analysis.load_cached_transcript", return_value=None),
            patch("chopster.clipper.master_analysis.prepare_transcript_and_subtitles", side_effect=lambda t, cfg, **kw: (t, "local")),
        ]
        calls = [0]

        def fake_transcribe(*args, **kwargs):
            calls[0] += 1
            return tr2 if calls[0] > 1 else tr

        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            src = Path(td) / "src.mp4"
            src.write_bytes(b"x")
            with patch("chopster.clipper.master_analysis.transcribe", side_effect=fake_transcribe):
                with base[0], base[1], base[2], base[3], base[4], base[5], base[6], base[7]:
                    r1 = ensure_master_analysis(proj, src, model="tiny", language="id", word_timestamps=False,
                                                mode="Smart", ai_config=cfg, target_aspect=9 / 16)
                    self.assertEqual(calls[0], 1)
                    self.assertEqual(r1["transcript"]["segments"][0]["text"], "Satu dua tiga")
                # Second run with a different model: artifact exists but provenance
                # no longer matches, so it must re-transcribe.
                with base[0], base[1], base[2], base[3], base[4], base[5], base[6], base[7]:
                    r2 = ensure_master_analysis(proj, src, model="small", language="id", word_timestamps=False,
                                                mode="Smart", ai_config=cfg, target_aspect=9 / 16)
                    self.assertEqual(calls[0], 2)
                    self.assertEqual(r2["transcript"]["segments"][0]["text"], "Empat lima enam")

    def test_same_settings_reuse_existing_artifact(self):
        from chopster.clipper.media_probe import MediaInfo
        from chopster.clipper.master_analysis import ensure_master_analysis
        from chopster.clipper.transcript_manager import Segment, Transcript

        meta = MediaInfo(path="x.mp4", duration=120.0, width=1920, height=1080, fps=30.0,
                         vcodec="h264", acodec="aac", has_audio=True, has_video=True,
                         rotation=0, bitrate=1000)
        tr = Transcript(language="id", segments=[Segment(0.0, 2.0, "Satu dua tiga", [])])
        cfg = {"ai_provider": "none", "ai_endpoint": "", "ai_api_key": "",
               "ai_auto_visual": False, "ai_camera_director": True}
        base = [
            patch("chopster.clipper.master_analysis.probe", return_value=meta),
            patch("chopster.clipper.master_analysis.detect_scenes", return_value=[(0.0, 120.0)]),
            patch("chopster.clipper.master_analysis.analyze_scene_visuals", return_value={"source": "local", "scenes": []}),
            patch("chopster.clipper.master_analysis.detect_face_focus", side_effect=RuntimeError("no faces")),
            patch("chopster.clipper.master_analysis.extract_frame_images", side_effect=RuntimeError("no ffmpeg")),
            patch("chopster.clipper.master_analysis.save_cached_transcript", return_value=None),
            patch("chopster.clipper.master_analysis.prepare_transcript_and_subtitles", side_effect=lambda t, cfg, **kw: (t, "local")),
        ]
        calls = [0]

        def fake_transcribe(*args, **kwargs):
            calls[0] += 1
            return tr

        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            src = Path(td) / "src.mp4"
            src.write_bytes(b"x")
            with patch("chopster.clipper.master_analysis.transcribe", side_effect=fake_transcribe):
                with base[0], base[1], base[2], base[3], base[4], base[5], base[6]:
                    ensure_master_analysis(proj, src, model="tiny", language="id", word_timestamps=False,
                                           mode="Smart", ai_config=cfg, target_aspect=9 / 16)
                with base[0], base[1], base[2], base[3], base[4], base[5], base[6]:
                    ensure_master_analysis(proj, src, model="tiny", language="id", word_timestamps=False,
                                           mode="Smart", ai_config=cfg, target_aspect=9 / 16)
            # Same settings on the second run: cached artifact is reused, no extra
            # transcription and no load from the (empty) global cache.
            self.assertEqual(calls[0], 1)


class FrozenEXEReadinessTests(unittest.TestCase):
    """EXE build readiness: frozen code paths must never launch a second GUI
    instance by calling sys.executable as if it were a plain Python interpreter."""

    def test_cuda_preflight_skips_child_probe_when_frozen(self):
        import sys as _sys
        from unittest.mock import patch
        from chopster.clipper.transcript_manager import _cuda_preflight

        saved = getattr(_sys, "frozen", False)
        _sys.frozen = True
        try:
            with patch("chopster.clipper.transcript_manager.subprocess.run") as mock_run:
                ok, detail = _cuda_preflight()
                self.assertFalse(ok)
                self.assertIn("EXE", detail)
                mock_run.assert_not_called()
        finally:
            _sys.frozen = saved

    def test_cuda_preflight_still_probes_when_not_frozen(self):
        import sys as _sys
        from unittest.mock import patch
        from chopster.clipper.transcript_manager import _cuda_preflight

        saved = getattr(_sys, "frozen", False)
        _sys.frozen = False
        try:
            with patch("chopster.clipper.transcript_manager.subprocess.run") as mock_run, \
                    patch("chopster.clipper.transcript_manager._windows_cuda_dll_preflight", return_value=(True, "ok")):
                _cuda_preflight()
                # In dev (non-frozen), the isolated ctranslate2 child probe still runs;
                # the frozen EXE guard must not disable the normal dev path.
                self.assertTrue(mock_run.called)
        finally:
            _sys.frozen = saved

    def test_frozen_guards_present_in_exe_risk_sites(self):
        # Dev-only subprocess calls that would relaunch the EXE must be guarded.
        sys_present = 0
        for rel in (
            "auto_clip_studio/engine/video_engine.py",
            "auto_clip_studio/engine/services/youtube_service.py",
            "auto_clip_studio/engine/routers/system.py",
            "auto_clip_studio/engine/services/system_service.py",
        ):
            source = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn('getattr(sys, "frozen", False)', source)
            sys_present += 1
        self.assertEqual(sys_present, 4)


if __name__ == "__main__":
    unittest.main()
