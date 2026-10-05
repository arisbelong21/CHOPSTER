"""Dependency-light regression checks for issues identified in the audit."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import subprocess
from types import ModuleType
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from chopster.auto_clip_studio.engine.utils.text import is_safe_remote_url
from chopster.auto_clip_studio.engine.video_engine import (
    clear_mp4_validation_cache,
    is_valid_mp4,
)
from chopster.clipper.media_probe import clear_probe_cache, probe
from chopster.clipper.clip_renderer import _run_ffmpeg
from chopster.clipper.transcript_manager import (
    _load_whisper_model,
    clear_whisper_model_cache,
)
from chopster.downloader.engine import _runtime_version


class RemoteUrlValidationTests(unittest.TestCase):
    def test_known_video_provider_is_allowed(self):
        self.assertTrue(
            is_safe_remote_url(
                "https://www.youtube.com/watch?v=abcdefghijk",
                {"youtube.com", "youtu.be"},
            )
        )

    def test_local_and_non_http_targets_are_rejected(self):
        for url in (
            "http://localhost/admin",
            "https://127.0.0.1/latest/meta-data",
            "https://[::1]/",
            "file:///etc/passwd",
            "https://youtube.com.attacker.invalid/watch?v=abcdefghijk",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_safe_remote_url(url, {"youtube.com", "youtu.be"}))


class AuditRegressionTests(unittest.TestCase):
    def test_history_thumbnail_uses_existing_route(self):
        app_source = (PROJECT_ROOT / "auto_clip_studio/web_source/src/App.tsx").read_text()
        media_source = (PROJECT_ROOT / "auto_clip_studio/engine/routers/media.py").read_text()
        self.assertIn("/api/clip-frame?video_id=", app_source)
        self.assertIn('@router.get("/api/clip-frame")', media_source)
        self.assertNotIn("/api/frame/", app_source)

    def test_build_spec_bundles_frontend_and_required_assets(self):
        spec = (PROJECT_ROOT / "Chopster.spec").read_text()
        build = (PROJECT_ROOT / "build_exe.bat").read_text()
        for asset in ("web_dist", "engine/fonts", "engine/cascades"):
            self.assertIn(asset, spec)
        # Datas paths in the spec are relative to this folder, not to its
        # parent. These checks catch the old extra "chopster/" source prefix.
        for source in (
            "resources",
            "VERSION.txt",
            "auto_clip_studio/engine/fonts",
            "auto_clip_studio/engine/cascades",
            "auto_clip_studio/engine/haarcascade_frontalface_default.xml",
            "auto_clip_studio/web_dist",
            "auto_clip_studio/web_source",
        ):
            self.assertTrue((PROJECT_ROOT / source).exists(), source)
            self.assertIn(f'"{source}"', spec)
        self.assertIn('"dotenv"', spec)
        self.assertNotIn('"python_dotenv"', spec)
        self.assertIn("Chopster.spec", build)
        self.assertIn("py -3.12", build)
        self.assertIn(".venv-build", build)
        self.assertIn("face_detection_yunet.onnx", build)
        self.assertIn('set "DIST_DIR=dist\\Chopster by Aris"', build)
        self.assertIn('browser_extension\\manifest.json', build)
        self.assertIn("call :copy_valid_deno", build)
        self.assertIn("versi di bawah 2.3; file tidak disalin", build)
        self.assertIn("build_exe.log", build)
        self.assertIn('call "%~f0" >>"%BUILD_LOG%" 2>&1', build)
        install = (PROJECT_ROOT / "install_dependencies.bat").read_text()
        self.assertIn("Memakai Node sebagai pengganti Deno", install)
        for script in (
            "test_camera_pipeline_v84.bat",
            "test_dual_ai_windows.bat",
        ):
            source = (PROJECT_ROOT / script).read_text()
            self.assertIn("python -m unittest discover", source)
            self.assertNotIn("python -m pytest", source)
        for script in (
            "test_embedded_gemini_windows.bat",
            "test_gpu_safe.bat",
        ):
            source = (PROJECT_ROOT / script).read_text()
            self.assertIn("PYTHONPATH=%~dp0..", source)

    def test_drive_download_has_size_limit_and_partial_cleanup(self):
        source = (PROJECT_ROOT / "auto_clip_studio/engine/services/gdrive_service.py").read_text()
        self.assertIn('"max_filesize": max_bytes', source)
        self.assertIn("Content-Length", source)
        self.assertIn("downloaded > max_bytes", source)
        self.assertIn("cleanup_partial()", source)

    def test_development_backend_uses_real_module_and_loopback(self):
        source = (PROJECT_ROOT / "auto_clip_studio/web_source/scripts/start-backend.js").read_text()
        self.assertIn("chopster.auto_clip_studio.engine.main:app", source)
        self.assertIn("host='127.0.0.1'", source)
        self.assertNotIn("backend.main:app", source)
        self.assertNotIn("host='0.0.0.0'", source)

    def test_local_admin_actions_require_token_and_origin_validation(self):
        system_source = (PROJECT_ROOT / "auto_clip_studio/engine/routers/system.py").read_text()
        main_source = (PROJECT_ROOT / "auto_clip_studio/engine/main.py").read_text()
        self.assertIn("secrets.compare_digest", system_source)
        self.assertIn("_LOCAL_SESSION_TOKEN = secrets.token_urlsafe", system_source)
        self.assertIn("Cross-origin request blocked", main_source)
        self.assertIn("Origin header required for state-changing requests", main_source)

    def test_tls_verification_is_not_disabled(self):
        source = (PROJECT_ROOT / "auto_clip_studio/engine/services/youtube_service.py").read_text()
        self.assertNotIn("nocheckcertificate", source)

    def test_media_probe_cache_reuses_only_unchanged_file_revisions(self):
        clear_probe_cache()
        probe_json = json.dumps({
            "format": {"duration": "10.0", "bit_rate": "100000"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1280,
                 "height": 720, "avg_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
        })
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "sample.mp4"
            media.write_bytes(b"media-a")
            with patch("chopster.clipper.media_probe._find_ffprobe", return_value="ffprobe"), \
                 patch("chopster.clipper.media_probe.subprocess.run",
                       return_value=SimpleNamespace(returncode=0, stdout=probe_json, stderr="")) as run:
                self.assertEqual(probe(media).duration, 10.0)
                self.assertEqual(probe(media).duration, 10.0)
                self.assertEqual(run.call_count, 1)
                media.write_bytes(b"media-changed")
                os.utime(media, ns=(media.stat().st_atime_ns, media.stat().st_mtime_ns + 1_000_000))
                self.assertEqual(probe(media).duration, 10.0)
                self.assertEqual(run.call_count, 2)
        clear_probe_cache()

    def test_auto_clip_mp4_validation_cache_rechecks_changed_files(self):
        clear_mp4_validation_cache()
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "sample.mp4"
            media.write_bytes(b"x" * 12000)
            with patch(
                "chopster.auto_clip_studio.engine.video_engine.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout="10.0", stderr=""),
            ) as run:
                self.assertTrue(is_valid_mp4(media))
                self.assertTrue(is_valid_mp4(media))
                self.assertEqual(run.call_count, 1)
                media.write_bytes(b"y" * 15000)
                os.utime(media, ns=(media.stat().st_atime_ns, media.stat().st_mtime_ns + 1_000_000))
                self.assertTrue(is_valid_mp4(media))
                self.assertEqual(run.call_count, 2)
        clear_mp4_validation_cache()

    def test_ffmpeg_runner_does_not_deadlock_on_large_stderr(self):
        command = [
            sys.executable, "-c",
            "import sys; sys.stderr.write('E' * 200000); sys.exit(7)",
        ]
        code, detail = _run_ffmpeg(command, timeout=10)
        self.assertEqual(code, 7)
        self.assertLessEqual(len(detail), 5000)
        self.assertTrue(detail.endswith("E"))

    def test_auto_clip_batch_zip_does_not_recompress_mp4(self):
        source = (PROJECT_ROOT / "auto_clip_studio/engine/services/render_service.py").read_text()
        self.assertIn("compression=zipfile.ZIP_STORED", source)

    def test_downloader_runtime_version_probe_is_cached(self):
        _runtime_version.cache_clear()
        with patch(
            "chopster.downloader.engine.subprocess.run",
            return_value=SimpleNamespace(stdout="v24.1.0", stderr=""),
        ) as run:
            self.assertEqual(_runtime_version("node", "/fake/node"), (24, 1, 0))
            self.assertEqual(_runtime_version("node", "/fake/node"), (24, 1, 0))
            self.assertEqual(run.call_count, 1)
        _runtime_version.cache_clear()

    def test_content_clipper_reuses_only_the_selected_whisper_model(self):
        clear_whisper_model_cache()
        fake_module = ModuleType("faster_whisper")
        fake_module.WhisperModel = unittest.mock.Mock(side_effect=[object(), object()])
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            first = _load_whisper_model("tiny", "cpu", "int8", 4, 1)
            reused = _load_whisper_model("tiny", "cpu", "int8", 4, 1)
            self.assertIs(first, reused)
            self.assertEqual(fake_module.WhisperModel.call_count, 1)
            replacement = _load_whisper_model("small", "cpu", "int8", 4, 1)
            self.assertIsNot(first, replacement)
            self.assertEqual(fake_module.WhisperModel.call_count, 2)
        clear_whisper_model_cache()

    def test_release_version_is_consistent(self):
        release = (PROJECT_ROOT / "VERSION.txt").read_text().strip()
        package_version = json.loads(
            (PROJECT_ROOT / "auto_clip_studio/web_source/package.json").read_text()
        )["version"]
        self.assertEqual(release, package_version)
        self.assertEqual(release, __import__("chopster").__version__)
        self.assertIn("with_name(\"VERSION.txt\")", (PROJECT_ROOT / "__init__.py").read_text())


if __name__ == "__main__":
    unittest.main()