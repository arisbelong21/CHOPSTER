"""Settings page — grouped sections (full PRD)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QSpinBox, QFileDialog, QScrollArea, QFrame, QMessageBox, QListWidget, QListWidgetItem
)

from chopster.app.configuration import FILENAME_TEMPLATES, QUALITIES, FORMATS, SPEED_PRESETS
from chopster.ui.theme import THEMES
from chopster.ui.components.cards import Card


class SettingsPage(QWidget):
    ai_settings_changed = Signal()
    def __init__(self, app, theme: str = "dark", parent: QWidget | None = None):
        super().__init__(parent)
        self.app = app
        self._theme = theme
        C = THEMES.get(theme, THEMES["dark"])

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)

        title = QLabel("Settings", container)
        title.setObjectName("h1")
        lay.addWidget(title)

        # -- DOWNLOAD
        lay.addWidget(self._section_title("DOWNLOAD", container))
        card = Card(container, theme)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)
        cl.addWidget(self._lbl("LOKASI PENYIMPANAN", card))
        row = QHBoxLayout()
        self.out_dir = QLineEdit(card)
        self.out_dir.setText(self.app.config.get("out_dir"))
        row.addWidget(self.out_dir, 1)
        btn = QPushButton("Pilih Folder", card)
        btn.setObjectName("ghost")
        btn.clicked.connect(self._pick_folder)
        row.addWidget(btn)
        cl.addLayout(row)

        row2 = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(self._lbl("KUALITAS", card))
        self.quality = QComboBox(card)
        self.quality.addItems(list(QUALITIES.keys()))
        self.quality.setCurrentText(self.app.config.get("quality"))
        col1.addWidget(self.quality)
        row2.addLayout(col1, 1)
        col2 = QVBoxLayout()
        col2.addWidget(self._lbl("FORMAT", card))
        self.format_cb = QComboBox(card)
        self.format_cb.addItems(list(FORMATS))
        self.format_cb.setCurrentText(self.app.config.get("output_format"))
        col2.addWidget(self.format_cb)
        row2.addLayout(col2, 1)
        cl.addLayout(row2)

        audio_row=QHBoxLayout()
        audio_col=QVBoxLayout(); audio_col.addWidget(self._lbl("AUDIO TRACK", card))
        self.audio_language=QComboBox(card)
        self.audio_language.addItems(["Auto — Indonesia jika tersedia","Indonesia","English","Original / default"])
        self.audio_language.setCurrentText(self.app.config.get("audio_language") or "Auto — Indonesia jika tersedia")
        self.audio_language.setToolTip("URL YouTube tidak menyimpan track player yang sedang dipilih. Auto memprioritaskan Indonesia jika tersedia.")
        audio_col.addWidget(self.audio_language); audio_row.addLayout(audio_col,1)
        info=QLabel("Auto: Indonesia → fallback. Untuk track lain, pilih bahasa secara eksplisit.",card); info.setWordWrap(True); info.setStyleSheet(f"color:{THEMES.get(self._theme, THEMES['dark'])['MUTED']};font-size:10px;"); audio_row.addWidget(info,1)
        cl.addLayout(audio_row)

        self.h264 = QCheckBox("Prioritaskan H.264", card)
        self.h264.setChecked(bool(self.app.config.get("h264")))
        cl.addWidget(self.h264)

        row3 = QHBoxLayout()
        c1 = QVBoxLayout()
        c1.addWidget(self._lbl("TEMPLATE NAMA FILE", card))
        self.tmpl = QComboBox(card)
        self.tmpl.addItems(list(FILENAME_TEMPLATES.keys()))
        self.tmpl.setCurrentText(self.app.config.get("filename_template"))
        c1.addWidget(self.tmpl)
        row3.addLayout(c1, 1)
        c2 = QVBoxLayout()
        c2.addWidget(self._lbl("BATAS KECEPATAN", card))
        self.speed = QComboBox(card)
        self.speed.addItems(list(SPEED_PRESETS.keys()))
        self.speed.setCurrentText(self.app.config.get("speed_limit"))
        c2.addWidget(self.speed)
        row3.addLayout(c2, 1)
        cl.addLayout(row3)

        prow = QHBoxLayout()
        prow.addWidget(self._lbl("PARALEL (1-3)", card))
        self.parallel = QSpinBox(card)
        self.parallel.setRange(1, 3)
        self.parallel.setValue(int(self.app.config.get("parallel") or 2))
        prow.addWidget(self.parallel)
        prow.addStretch()
        cl.addLayout(prow)

        for key, label in [
            ("subfolders", "Subfolder per platform"),
            ("subtitles", "Unduh subtitle (id/en)"),
            ("thumbnail", "Unduh thumbnail"),
            ("ask_duplicates", "Tanya jika duplikat"),
            ("download_playlist", "Unduh seluruh playlist"),
        ]:
            cb = QCheckBox(label, card)
            cb.setChecked(bool(self.app.config.get(key)))
            setattr(self, f"cb_{key}", cb)
            cl.addWidget(cb)

        cl.addWidget(self._lbl("ITEM PLAYLIST (contoh 1-10,12)", card))
        self.playlist_items = QLineEdit(card)
        self.playlist_items.setText(self.app.config.get("playlist_items") or "")
        cl.addWidget(self.playlist_items)

        cl.addWidget(self._lbl("SESI BROWSER UNTUK SITUS YANG BUTUH LOGIN", card))
        self.browser_cookie = QComboBox(card)
        self.browser_cookie.addItems(["Auto", "Chrome", "Edge", "Firefox", "Brave", "Chromium", "None"])
        self.browser_cookie.setCurrentText(str(self.app.config.get("browser_cookie_source") or "Auto"))
        self.browser_cookie.setToolTip("Chopster hanya mencoba cookie browser saat situs menolak akses/login, misalnya TikTok restricted post.")
        cl.addWidget(self.browser_cookie)
        hint_cookie = QLabel("Dipakai hanya sebagai fallback autentikasi. Login tetap harus ada di browser kamu.", card)
        hint_cookie.setWordWrap(True)
        hint_cookie.setStyleSheet("color:#94A3B8;font-size:10px;")
        cl.addWidget(hint_cookie)

        cl.addWidget(self._lbl("FILE COOKIES (Netscape)", card))
        crow = QHBoxLayout()
        self.cookies = QLineEdit(card)
        self.cookies.setText(self.app.config.get("cookies_file") or "")
        crow.addWidget(self.cookies, 1)
        cb = QPushButton("Pilih", card)
        cb.setObjectName("ghost")
        cb.clicked.connect(self._pick_cookies)
        crow.addWidget(cb)
        cl.addLayout(crow)

        cl.addWidget(self._lbl("PROXY (opsional)", card))
        self.proxy = QLineEdit(card)
        self.proxy.setPlaceholderText("http://127.0.0.1:8080 atau socks5://127.0.0.1:9050")
        self.proxy.setText(self.app.config.get("proxy") or "")
        cl.addWidget(self.proxy)
        lay.addWidget(card)

        # -- TAMPILAN
        lay.addWidget(self._section_title("TAMPILAN", container))
        acard = Card(container, theme)
        al = QHBoxLayout(acard)
        al.setContentsMargins(16, 12, 16, 12)
        al.addWidget(self._lbl("TEMA", acard))
        self.theme_cb = QComboBox(acard)
        self.theme_cb.addItems(["dark", "light"])
        self.theme_cb.setCurrentText(self.app.config.get("theme") or "dark")
        al.addWidget(self.theme_cb)
        al.addStretch()
        lay.addWidget(acard)

        # -- CLIPPER
        lay.addWidget(self._section_title("CLIPPER", container))
        ccard = Card(container, theme)
        ccl = QVBoxLayout(ccard)
        ccl.setContentsMargins(16, 14, 16, 14)
        ccl.setSpacing(8)
        row_c1 = QHBoxLayout()
        row_c1.addWidget(self._lbl("DURASI DEFAULT (detik)", ccard))
        self.clip_dur = QSpinBox(ccard)
        self.clip_dur.setRange(5, 600)
        self.clip_dur.setValue(int(self.app.config.get("clip_default_duration") or 30))
        row_c1.addWidget(self.clip_dur)
        row_c1.addWidget(self._lbl("OVERLAP (detik)", ccard))
        self.clip_overlap = QSpinBox(ccard)
        self.clip_overlap.setRange(0, 60)
        self.clip_overlap.setValue(int(self.app.config.get("clip_overlap") or 0))
        row_c1.addWidget(self.clip_overlap)
        row_c1.addStretch()
        ccl.addLayout(row_c1)

        row_c2 = QHBoxLayout()
        row_c2.addWidget(self._lbl("ASPECT", ccard))
        self.clip_aspect = QComboBox(ccard)
        self.clip_aspect.addItems(["original", "9:16", "1:1", "16:9", "4:5"])
        self.clip_aspect.setCurrentText(self.app.config.get("clip_aspect") or "9:16")
        row_c2.addWidget(self.clip_aspect)
        row_c2.addWidget(self._lbl("QUALITY", ccard))
        self.clip_quality = QComboBox(ccard)
        self.clip_quality.addItems(["fast", "balanced", "high"])
        self.clip_quality.setCurrentText(self.app.config.get("clip_quality") or "balanced")
        row_c2.addWidget(self.clip_quality)
        row_c2.addWidget(self._lbl("PARALEL RENDER", ccard))
        self.clip_parallel = QSpinBox(ccard)
        self.clip_parallel.setRange(1, 3)
        self.clip_parallel.setValue(int(self.app.config.get("clip_parallel") or 1))
        row_c2.addWidget(self.clip_parallel)
        row_c2.addStretch()
        ccl.addLayout(row_c2)

        row_c3 = QHBoxLayout()
        row_c3.addWidget(self._lbl("OUTPUT CLIPS", ccard))
        self.clip_out = QLineEdit(ccard)
        self.clip_out.setPlaceholderText("Kosong = <projects>/<id>/clips")
        self.clip_out.setText(self.app.config.get("clip_output_dir") or "")
        row_c3.addWidget(self.clip_out, 1)
        btn_c = QPushButton("Pilih", ccard)
        btn_c.setObjectName("ghost")
        btn_c.clicked.connect(lambda: self._pick_dir(self.clip_out))
        row_c3.addWidget(btn_c)
        ccl.addLayout(row_c3)
        lay.addWidget(ccard)

        # -- TRANSCRIPTION
        lay.addWidget(self._section_title("TRANSCRIPTION", container))
        tcard = Card(container, theme)
        tl = QVBoxLayout(tcard)
        tl.setContentsMargins(16, 14, 16, 14)
        tl.setSpacing(8)
        row_t1 = QHBoxLayout()
        row_t1.addWidget(self._lbl("MODEL", tcard))
        self.tr_model = QComboBox(tcard)
        self.tr_model.addItems(["tiny", "base", "small", "medium", "large-v2", "large-v3"])
        self.tr_model.setCurrentText(self.app.config.get("transcribe_model") or "tiny")
        row_t1.addWidget(self.tr_model)
        row_t1.addWidget(self._lbl("BAHASA", tcard))
        self.tr_lang = QComboBox(tcard)
        self.tr_lang.addItems(["auto", "id", "en", "ja", "ko", "ar", "zh"])
        self.tr_lang.setCurrentText(self.app.config.get("transcribe_language") or "auto")
        row_t1.addWidget(self.tr_lang)
        row_t1.addWidget(self._lbl("DEVICE", tcard))
        self.tr_device = QComboBox(tcard)
        self.tr_device.addItems(["auto", "cpu", "cuda"])
        self.tr_device.setCurrentText(self.app.config.get("transcribe_device") or "auto")
        row_t1.addWidget(self.tr_device)
        self.tr_gpu_status = QLabel("Auto = gunakan GPU hanya jika cuDNN 9 + cuBLAS CUDA 12 dan symbol yang diperlukan benar-benar tersedia; jika tidak, otomatis CPU agar aplikasi tidak force close.", tcard)
        self.tr_gpu_status.setWordWrap(True)
        self.tr_gpu_status.setStyleSheet(f"color: {C['FOOT']}; font-size:10px;")
        tl.addWidget(self.tr_gpu_status)
        gpu_btn = QPushButton("🧪 Test GPU Safe", tcard)
        gpu_btn.setObjectName("ghost")
        gpu_btn.clicked.connect(self._test_cuda_safe)
        tl.addWidget(gpu_btn)
        row_t1.addStretch()
        tl.addLayout(row_t1)
        row_t2 = QHBoxLayout()
        row_t2.addWidget(self._lbl("MODEL DIR", tcard))
        self.tr_model_dir = QLineEdit(tcard)
        self.tr_model_dir.setPlaceholderText("Kosong = cache default")
        self.tr_model_dir.setText(self.app.config.get("transcribe_model_dir") or "")
        row_t2.addWidget(self.tr_model_dir, 1)
        btn_t = QPushButton("Pilih", tcard)
        btn_t.setObjectName("ghost")
        btn_t.clicked.connect(lambda: self._pick_dir(self.tr_model_dir))
        row_t2.addWidget(btn_t)
        tl.addLayout(row_t2)
        self.tr_word = QCheckBox("Aktifkan word-level timestamps (untuk karaoke highlight)", tcard)
        self.tr_word.setChecked(bool(self.app.config.get("word_timestamps")))
        tl.addWidget(self.tr_word)
        lay.addWidget(tcard)

        # -- AI
        lay.addWidget(self._section_title("AI & MODEL CONNECTION", container))
        aicard = Card(container, theme)
        al2 = QVBoxLayout(aicard)
        al2.setContentsMargins(16, 14, 16, 14)
        al2.setSpacing(8)
        al2.addWidget(QLabel("AI Manual (opsional dan terpisah). Isi Base URL/API sendiri untuk analisis teks, viral analysis, judul/caption/deskripsi, B-roll, dan reasoning konten. Embedded Gemini tetap menangani frame/scene/camera.", aicard))
        row_ai1 = QHBoxLayout()
        row_ai1.addWidget(self._lbl("TYPE", aicard))
        self.ai_provider = QComboBox(aicard)
        self.ai_provider.addItem("Tidak digunakan", "none")
        self.ai_provider.addItem("OpenAI-compatible API", "openai-compatible")
        self.ai_provider.addItem("Custom OpenAI-compatible", "custom")
        current_provider = str(self.app.config.get("ai_provider") or "none")
        if current_provider == "openai":
            current_provider = "openai-compatible"
        idx = self.ai_provider.findData(current_provider)
        self.ai_provider.setCurrentIndex(idx if idx >= 0 else 0)
        row_ai1.addWidget(self.ai_provider)
        row_ai1.addStretch()
        al2.addLayout(row_ai1)

        al2.addWidget(self._lbl("BASE URL", aicard))
        self.ai_endpoint = QLineEdit(aicard)
        self.ai_endpoint.setPlaceholderText("Contoh: https://provider.example/v1")
        self.ai_endpoint.setText(self.app.config.get("ai_endpoint") or "")
        self.ai_endpoint.editingFinished.connect(self._auto_discover_ai)
        al2.addWidget(self.ai_endpoint)

        al2.addWidget(self._lbl("API KEY", aicard))
        self.ai_key = QLineEdit(aicard)
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("cc_... / sk_...  — disimpan lokal")
        self.ai_key.setText(self.app.config.get("ai_api_key") or "")
        self.ai_key.editingFinished.connect(self._auto_discover_ai)
        al2.addWidget(self.ai_key)
        show_key = QCheckBox("Tampilkan API key", aicard)
        show_key.toggled.connect(lambda checked: self.ai_key.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password))
        al2.addWidget(show_key)

        row_actions = QHBoxLayout()
        self.ai_test_btn = QPushButton("🔌 Test Connection", aicard); self.ai_test_btn.setObjectName("primary"); self.ai_test_btn.clicked.connect(self._test_ai_connection); row_actions.addWidget(self.ai_test_btn)
        self.ai_refresh_btn = QPushButton("🔄 Refresh Models", aicard); self.ai_refresh_btn.setObjectName("ghost"); self.ai_refresh_btn.clicked.connect(self._refresh_ai_models); row_actions.addWidget(self.ai_refresh_btn)
        self.ai_infer_btn = QPushButton("🧪 Test AI", aicard); self.ai_infer_btn.setObjectName("ghost"); self.ai_infer_btn.clicked.connect(self._test_ai_inference); row_actions.addWidget(self.ai_infer_btn)
        self.ai_vision_btn = QPushButton("🖼 Test Vision", aicard); self.ai_vision_btn.setObjectName("ghost"); self.ai_vision_btn.clicked.connect(self._test_ai_vision); row_actions.addWidget(self.ai_vision_btn)
        row_actions.addStretch()
        al2.addLayout(row_actions)
        self.ai_status = QLabel("Belum terhubung", aicard); self.ai_status.setObjectName("muted"); al2.addWidget(self.ai_status)
        self.ai_local_status = QLabel("🧠 Local Vision: READY • Face/Body/Composition • selalu tersedia tanpa API", aicard)
        self.ai_local_status.setWordWrap(True); self.ai_local_status.setStyleSheet(f"color:{C['GREEN']};font-size:10px;font-weight:700;"); al2.addWidget(self.ai_local_status)
        self.ai_embedded_status = QLabel("✨ Embedded Gemini Vision: READY • membaca representative frame untuk Master Analysis & Camera Director", aicard)
        self.ai_embedded_status.setWordWrap(True); self.ai_embedded_status.setStyleSheet(f"color:{C['BLUE']};font-size:10px;font-weight:800;"); al2.addWidget(self.ai_embedded_status)
        self.ai_embedded_test_btn = QPushButton("🧠 Test Embedded Gemini Vision", aicard); self.ai_embedded_test_btn.setObjectName("ghost"); self.ai_embedded_test_btn.clicked.connect(self._test_embedded_gemini_vision); al2.addWidget(self.ai_embedded_test_btn)

        al2.addWidget(self._lbl("MODEL DARI PROVIDER", aicard))
        manual_row = QHBoxLayout()
        manual_row.addWidget(self._lbl("MODEL ID MANUAL", aicard))
        self.ai_manual_model = QLineEdit(aicard)
        self.ai_manual_model.setPlaceholderText("Opsional — dipakai jika /models sedang gagal")
        self.ai_manual_model.setText(str(self.app.config.get("ai_model") or ""))
        manual_row.addWidget(self.ai_manual_model, 1)
        al2.addLayout(manual_row)

        vision_row = QHBoxLayout()
        vision_row.addWidget(self._lbl("VISION MODEL ID", aicard))
        self.ai_vision_model = QLineEdit(aicard)
        self.ai_vision_model.setPlaceholderText("Kosong = Auto berdasarkan capability provider")
        self.ai_vision_model.setText(str(self.app.config.get("ai_vision_model") or ""))
        vision_row.addWidget(self.ai_vision_model, 1)
        al2.addLayout(vision_row)
        self.ai_models_list = QListWidget(aicard)
        self.ai_models_list.setMinimumHeight(130)
        al2.addWidget(self.ai_models_list)
        row_add = QHBoxLayout()
        add_model = QPushButton("＋ Tambahkan Model Terpilih", aicard); add_model.setObjectName("ghost"); add_model.clicked.connect(self._add_selected_ai_model); row_add.addWidget(add_model)
        use_model = QPushButton("▶ Gunakan Model Terpilih", aicard); use_model.setObjectName("primary"); use_model.clicked.connect(self._use_selected_ai_model); row_add.addWidget(use_model)
        row_add.addStretch(); al2.addLayout(row_add)

        al2.addWidget(self._lbl("AI YANG DISIMPAN", aicard))
        self.ai_saved_list = QListWidget(aicard); self.ai_saved_list.setMinimumHeight(90); al2.addWidget(self.ai_saved_list)
        row_saved = QHBoxLayout()
        use_saved = QPushButton("Gunakan", aicard); use_saved.clicked.connect(self._use_saved_ai_model); row_saved.addWidget(use_saved)
        del_saved = QPushButton("Hapus", aicard); del_saved.setObjectName("danger"); del_saved.clicked.connect(self._delete_saved_ai_model); row_saved.addWidget(del_saved)
        row_saved.addStretch(); al2.addLayout(row_saved)

        self.ai_auto_model = QCheckBox("Auto pilih model untuk tiap tugas (mengikuti capability)", aicard)
        self.ai_auto_model.setChecked(bool(self.app.config.get("ai_auto_model", True))); al2.addWidget(self.ai_auto_model)
        self.ai_auto_visual = QCheckBox("Auto pilih model Vision untuk membaca frame video saat analisis visual", aicard)
        self.ai_auto_visual.setChecked(bool(self.app.config.get("ai_auto_visual", True))); al2.addWidget(self.ai_auto_visual)
        self.ai_failover_local = QCheckBox("AUTO FALLBACK: jika AI API gagal/crash, lanjutkan dengan Local Engine", aicard)
        self.ai_failover_local.setChecked(bool(self.app.config.get("ai_failover_local", True)))
        self.ai_failover_local.setToolTip("AI online hanya enhancement. Saat timeout/error/rate-limit, Chopster otomatis berpindah ke analisis lokal dan tidak mengulang pekerjaan yang sudah berhasil.")
        al2.addWidget(self.ai_failover_local)
        fail_info = QLabel("Local fallback: Viral/Highlight → heuristic transcript · Camera → local tracking/lock · Content → local generator · Export/FFmpeg tetap lokal", aicard)
        fail_info.setWordWrap(True); fail_info.setStyleSheet(f"color: {C['FOOT']}; font-size:10px;"); al2.addWidget(fail_info)
        row_ai2 = QHBoxLayout()
        row_ai2.addWidget(self._lbl("TIMEOUT (detik)", aicard))
        self.ai_timeout = QSpinBox(aicard); self.ai_timeout.setRange(10, 600); self.ai_timeout.setValue(int(self.app.config.get("ai_timeout") or 60)); row_ai2.addWidget(self.ai_timeout); row_ai2.addStretch(); al2.addLayout(row_ai2)
        warn = QLabel("Pemisahan AI: Embedded Gemini (tertanam di Chopster) khusus visual/frame/scene/camera. AI Manual di Settings adalah layanan terpisah untuk analisis teks, viral analysis, judul/caption/deskripsi, B-roll, dan reasoning konten. Jangan samakan atau campur endpoint keduanya. Jika layanan remote gagal, fitur tetap turun ke local fallback tanpa force close.", aicard)
        warn.setWordWrap(True); warn.setStyleSheet(f"color: {C['FOOT']}; font-size:10px;"); al2.addWidget(warn)
        lay.addWidget(aicard)
        self.ai_models_cache=self.app.config.get("ai_models_cache", []) or []
        self._render_ai_model_lists()
        # -- STORAGE
        lay.addWidget(self._section_title("STORAGE", container))
        scard = Card(container, theme)
        sl = QVBoxLayout(scard)
        sl.setContentsMargins(16, 14, 16, 14)
        sl.setSpacing(8)
        for key, label, placeholder in [
            ("project_dir", "PROJECT DIR", "Kosong = AppData/ChopsterByAris/projects"),
            ("cache_dir", "CACHE DIR", "Kosong = default"),
            ("temp_dir", "TEMP DIR", "Kosong = system temp"),
        ]:
            sl.addWidget(self._lbl(label, scard))
            row_s = QHBoxLayout()
            le = QLineEdit(scard)
            le.setPlaceholderText(placeholder)
            le.setText(self.app.config.get(key) or "")
            setattr(self, f"storage_{key}", le)
            row_s.addWidget(le, 1)
            btn_s = QPushButton("Pilih", scard)
            btn_s.setObjectName("ghost")
            btn_s.clicked.connect(lambda _=False, w=le: self._pick_dir(w))
            row_s.addWidget(btn_s)
            sl.addLayout(row_s)
        # disk info
        self.disk_label = QLabel("", scard)
        self.disk_label.setStyleSheet(f"color: {C['FOOT']}; font-size:10px;")
        sl.addWidget(self.disk_label)
        self._refresh_disk()
        clear_btn = QPushButton("Bersihkan cache (hapus file sementara)", scard)
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self._clear_cache)
        sl.addWidget(clear_btn)
        lay.addWidget(scard)

        # Save
        save = QPushButton("💾  Simpan Pengaturan", container)
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        lay.addWidget(save)

        hint = QLabel("Ekstensi browser: hapus/nonaktifkan ekstensi Chopster versi lama, lalu buka chrome://extensions → Mode pengembang → Muat tidak terpakai → pilih folder browser_extension dari folder Chopster build ini. Muat ulang ekstensi setelah mengganti build.\nPastikan popup menampilkan “Chopster v8.5.5 terhubung” saat aplikasi terbaru berjalan.", container)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C['MUTED']}; font-size:10px;")
        lay.addWidget(hint)
        lay.addStretch()

    def _lbl(self, t, parent):
        from PySide6.QtWidgets import QLabel
        from chopster.ui.theme import THEMES
        C = THEMES.get(self._theme, THEMES["dark"])
        lbl = QLabel(t, parent)
        lbl.setStyleSheet(f"color: {C['MUTED']}; font-weight:700; font-size:10px;")
        return lbl

    def _section_title(self, t, parent):
        lbl = QLabel(t, parent)
        C = THEMES.get(self._theme, THEMES["dark"])
        lbl.setStyleSheet(f"color: {C['GOLD']}; font-weight:800; font-size:11px; letter-spacing:1px;")
        return lbl

    def _test_cuda_safe(self):
        from chopster.clipper.transcript_manager import _cuda_preflight
        ok, detail = _cuda_preflight()
        if ok:
            self.tr_gpu_status.setText(f"✅ CUDA/cuDNN aman: {detail}")
        else:
            self.tr_gpu_status.setText(f"⚠️ GPU tidak aman: {detail}\nChopster akan memakai CPU agar tetap stabil.")


    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder", self.out_dir.text() or str(Path.home()))
        if d:
            self.out_dir.setText(d)

    def _pick_dir(self, widget):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder", widget.text() or str(Path.home()))
        if d:
            widget.setText(d)

    def _pick_cookies(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pilih cookies", "", "Cookies (*.txt *.cookies);;All (*.*)")
        if p:
            self.cookies.setText(p)

    def _refresh_disk(self):
        try:
            out = self.app.config.get("out_dir") or str(Path.home() / "Downloads")
            free = shutil.disk_usage(out).free
            total = shutil.disk_usage(out).total
            self.disk_label.setText(f"Disk {out}: {free/(1024**3):.1f} GB free / {total/(1024**3):.1f} GB total")
        except Exception:
            self.disk_label.setText("Info disk tidak tersedia")

    def _clear_cache(self):
        from chopster.app.paths import user_data_dir
        cache = user_data_dir() / "cache"
        if not cache.exists():
            QMessageBox.information(self, "Cache", "Cache sudah kosong.")
            return
        if QMessageBox.question(self, "Bersihkan cache", f"Hapus isi {cache} ?") != QMessageBox.Yes:
            return
        import shutil as _sh
        try:
            for child in cache.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    _sh.rmtree(child, ignore_errors=True)
            QMessageBox.information(self, "Cache", "Cache dibersihkan.")
        except Exception as exc:
            QMessageBox.warning(self, "Cache", str(exc))

    def _auto_discover_ai(self):
        endpoint=self.ai_endpoint.text().strip(); key=self.ai_key.text().strip()
        if not endpoint or not key:
            return
        sig=(endpoint,key)
        if getattr(self,"_last_ai_signature",None)==sig and getattr(self,"ai_models_cache",None):
            return
        self._last_ai_signature=sig
        self._test_ai_connection(auto=True)

    def _ai_provider_value(self) -> str:
        value = self.ai_provider.currentData()
        return str(value or self.ai_provider.currentText() or "none")

    def _provider_from_fields(self):
        from chopster.ai.api_provider import APIProvider
        return APIProvider(self.ai_endpoint.text().strip(), self.ai_key.text().strip(), str(self.app.config.get("ai_model") or ""), int(self.ai_timeout.value()), str(self.ai_vision_model.text().strip() if hasattr(self,"ai_vision_model") else self.app.config.get("ai_vision_model") or ""))

    def _test_ai_connection(self, auto: bool = False):
        endpoint=self.ai_endpoint.text().strip(); key=self.ai_key.text().strip(); timeout=int(self.ai_timeout.value())
        if not endpoint or not key:
            QMessageBox.information(self, "AI Connection", "Isi Base URL dan API Key terlebih dahulu."); return
        self.app.config.update({"ai_provider": self._ai_provider_value(), "ai_endpoint": endpoint, "ai_api_key": key, "ai_timeout": timeout})
        try:
            self.app.config.save()
        except Exception:
            pass
        self.ai_status.setText("⏳ Menguji /v1/models…")
        self.ai_test_btn.setEnabled(False); self.ai_refresh_btn.setEnabled(False)
        manual_model=str(self.ai_manual_model.text().strip()) if hasattr(self,"ai_manual_model") else str(self.app.config.get("ai_model") or "")
        if manual_model:
            self.app.config.set("ai_model", manual_model)
        def worker(*,signals,cancel_check):
            from chopster.ai.api_provider import APIProvider
            provider=APIProvider(endpoint,key,manual_model,timeout)
            return provider.connection_probe(manual_model)
        def done(result):
            models=list(result.get("models") or [])
            if models:
                self.ai_models_cache=models; self.app.config.set("ai_models_cache", models)
            self._render_ai_model_lists()
            if result.get("ok"):
                vision_count=sum(1 for m in models if "vision" in [str(x).lower() for x in (m.get("capabilities") or [])])
                via="model list" if result.get("model_route_ok") else "direct inference"
                self.ai_status.setText(f"✅ AI ONLINE • {len(models) if models else 'cached/manual'} model • Vision: {vision_count} • via {via} • Local fallback: {'ON' if self.app.config.get('ai_failover_local', True) else 'OFF'}")
                self.app.config.set("ai_last_connection", "connected")
            else:
                err=str(result.get("message") or result.get("model_error") or "Remote AI tidak tersedia")
                self.ai_status.setText(f"⚠️ AI REMOTE OFFLINE • {err[:260]} • LOCAL FALLBACK SIAP")
                self.app.config.set("ai_last_connection", "degraded_remote")
            try:self.app.config.save()
            except Exception:pass
            self.ai_test_btn.setEnabled(True); self.ai_refresh_btn.setEnabled(True); self.ai_settings_changed.emit()
        def failed(tid,error):
            self.ai_status.setText(f"⚠️ AI REMOTE OFFLINE: {error[:220]} • LOCAL FALLBACK SIAP")
            self.app.config.set("ai_last_connection", "degraded_remote")
            self.ai_test_btn.setEnabled(True); self.ai_refresh_btn.setEnabled(True)
        self._ai_task_callbacks=getattr(self,"_ai_task_callbacks",{})
        self._ai_task_callbacks["settings:ai_connect"]=done
        if not hasattr(self,"_ai_task_hooked"):
            self._ai_task_hooked=True
            self.app.tasks.task_result.connect(self._on_ai_task_result)
            self.app.tasks.task_failed.connect(self._on_ai_task_failed)
        self.app.tasks.submit("settings:ai_connect","AI Connection",worker)

    def _refresh_ai_models(self):
        self._test_ai_connection()

    def _test_ai_vision(self):
        endpoint=self.ai_endpoint.text().strip(); key=self.ai_key.text().strip(); timeout=int(self.ai_timeout.value())
        if not endpoint or not key:
            QMessageBox.information(self,"Test Vision","Hubungkan AI terlebih dahulu."); return
        self.ai_status.setText("⏳ Menguji Vision AI dengan frame uji kecil…")
        self.ai_vision_btn.setEnabled(False)
        def worker(*,signals,cancel_check):
            import tempfile
            from pathlib import Path
            try:
                from PIL import Image, ImageDraw
            except Exception as exc:
                raise RuntimeError(f"Pillow tidak tersedia: {exc}")
            from chopster.ai.api_provider import APIProvider
            img=Path(tempfile.gettempdir())/"chopster_vision_probe.png"
            im=Image.new("RGB",(96,96),(238,238,238))
            d=ImageDraw.Draw(im); d.rectangle((8,8,88,88),outline=(20,20,20),width=3); d.text((18,40),"CHOPSTER",fill=(10,10,10))
            im.save(img)
            p=APIProvider(endpoint,key,str(self.app.config.get("ai_model") or ""),timeout,str(self.ai_vision_model.text().strip()) if hasattr(self,"ai_vision_model") else str(self.app.config.get("ai_vision_model") or ""))
            resp=p.generate_vision(
                'Balas JSON saja: {"ok":true,"description":"jelaskan gambar secara singkat"}.',
                [str(img)],
                system="Uji kemampuan vision.",
                model=(str(self.ai_vision_model.text().strip()) if hasattr(self,"ai_vision_model") and self.ai_vision_model.text().strip() else str(self.app.config.get("ai_vision_model") or "")),
                temperature=0,
                max_tokens=256,
                timeout=timeout,
            )
            raw=resp.raw if isinstance(resp.raw,dict) else {}
            return {"text":resp.text,"provider":raw.get("provider") or "remote","model":raw.get("model") or self.app.config.get("ai_model") or "auto"}
        def done(res):
            provider=str(res.get("provider") or "remote")
            if provider.startswith("local"):
                self.ai_status.setText("⚠️ Vision remote belum tersedia. Fitur visual akan memakai Local Fallback.")
            else:
                self.ai_status.setText(f"✅ Vision API aktif • model: {res.get('model','Auto')}")
            self.ai_vision_btn.setEnabled(True)
        self._ai_task_callbacks=getattr(self,"_ai_task_callbacks",{})
        self._ai_task_callbacks["settings:ai_vision"]=done
        if not hasattr(self,"_ai_task_hooked"):
            self._ai_task_hooked=True
            self.app.tasks.task_result.connect(self._on_ai_task_result)
            self.app.tasks.task_failed.connect(self._on_ai_task_failed)
        self.app.tasks.submit("settings:ai_vision","AI Vision Test",worker)

    def _test_embedded_gemini_vision(self):
        self.ai_embedded_test_btn.setEnabled(False)
        self.ai_status.setText("⏳ Menguji Embedded Gemini Vision…")
        def worker(*,signals,cancel_check):
            import tempfile
            from pathlib import Path
            from PIL import Image, ImageDraw
            from chopster.ai.embedded_gemini import EmbeddedGeminiProvider, EMBEDDED_GEMINI_MODEL
            img=Path(tempfile.gettempdir())/"chopster_embedded_gemini_probe.png"
            im=Image.new("RGB",(320,200),(38,44,58)); d=ImageDraw.Draw(im); d.rectangle((70,45,250,155),outline=(255,190,34),width=4); d.text((85,85),"CHOPSTER",fill=(255,255,255)); im.save(img)
            p=EmbeddedGeminiProvider(timeout=25)
            r=p.generate_vision("Jelaskan singkat isi frame ini dan apakah komposisinya aman untuk video portrait. Balas maksimal 3 kalimat.",[str(img)],model=EMBEDDED_GEMINI_MODEL,max_tokens=600,timeout=25)
            return {"model":str((r.raw or {}).get("gemini_model") or EMBEDDED_GEMINI_MODEL),"text":r.text,"provider":str((r.raw or {}).get("provider") or "embedded-gemini-vision")}
        def done(result):
            self.ai_status.setText(f"✅ Embedded Gemini Vision aktif • {result.get('model','auto')} • {str(result.get('text') or '')[:180]}")
            self.ai_embedded_test_btn.setEnabled(True)
        def fail(tid,error):
            self.ai_status.setText(f"⚠️ Embedded Gemini belum tersedia: {str(error)[:260]} • Local Vision tetap siap")
            self.ai_embedded_test_btn.setEnabled(True)
        self._ai_task_callbacks=getattr(self,"_ai_task_callbacks",{})
        self._ai_task_callbacks["settings:embedded_gemini_vision"]=done
        self._ai_task_callbacks_fail=getattr(self,"_ai_task_callbacks_fail",{})
        self._ai_task_callbacks_fail["settings:embedded_gemini_vision"]=fail
        if not hasattr(self,"_ai_task_hooked"):
            self._ai_task_hooked=True
            self.app.tasks.task_result.connect(self._on_ai_task_result)
            self.app.tasks.task_failed.connect(self._on_ai_task_failed)
        self.app.tasks.submit("settings:embedded_gemini_vision","Embedded Gemini Vision",worker)

    def _test_ai_inference(self):
        endpoint=self.ai_endpoint.text().strip(); key=self.ai_key.text().strip(); model=(str(self.ai_manual_model.text().strip()) if hasattr(self,"ai_manual_model") and self.ai_manual_model.text().strip() else str(self.app.config.get("ai_model") or "")); timeout=int(self.ai_timeout.value())
        if not endpoint or not key:
            QMessageBox.information(self,"Test AI","Hubungkan AI terlebih dahulu."); return
        def worker(*,signals,cancel_check):
            from chopster.ai.api_provider import APIProvider
            p=APIProvider(endpoint,key,model,timeout)
            return p.test_inference(model or None)
        def done(resp): self.ai_status.setText(f"✅ AI merespons • {resp.text[:80] or 'OK'}")
        self._ai_task_callbacks=getattr(self,"_ai_task_callbacks",{})
        self._ai_task_callbacks["settings:ai_infer"]=done
        if not hasattr(self,"_ai_task_hooked"):
            self._ai_task_hooked=True; self.app.tasks.task_result.connect(self._on_ai_task_result); self.app.tasks.task_failed.connect(self._on_ai_task_failed)
        self.app.tasks.submit("settings:ai_infer","AI Inference Test",worker)

    def _on_ai_task_result(self,tid,result):
        cb=getattr(self,"_ai_task_callbacks",{}).pop(tid,None)
        if cb: cb(result)

    def _on_ai_task_failed(self,tid,error):
        self._ai_task_callbacks=getattr(self,"_ai_task_callbacks",{})
        self._ai_task_callbacks_fail=getattr(self,"_ai_task_callbacks_fail",{})
        cb_fail=self._ai_task_callbacks_fail.pop(tid,None)
        if cb_fail:
            self._ai_task_callbacks.pop(tid,None)
            cb_fail(tid,error)
            return
        if tid in self._ai_task_callbacks: self._ai_task_callbacks.pop(tid,None)
        if tid == "settings:ai_connect":
            self.app.config.set("ai_last_connection", "degraded_remote")
            # Keep the last known-good model cache so the app can still resume with
            # a manually selected model when the provider comes back.
            self.ai_models_cache=self.app.config.get("ai_models_cache", []) or getattr(self,"ai_models_cache", []) or []
            self._render_ai_model_lists()
        if tid.startswith("settings:ai_"):
            self.ai_status.setText(f"⚠️ Remote AI tidak tersedia: {error[:220]} • LOCAL FALLBACK SIAP")
            self.ai_test_btn.setEnabled(True); self.ai_refresh_btn.setEnabled(True)
            if tid == "settings:ai_vision" and hasattr(self, "ai_vision_btn"):
                self.ai_vision_btn.setEnabled(True)
            if tid == "settings:ai_infer" and hasattr(self, "ai_infer_btn"):
                self.ai_infer_btn.setEnabled(True)

    def _render_ai_model_lists(self):
        models=getattr(self,"ai_models_cache", None) or self.app.config.get("ai_models_cache", []) or []
        self.ai_models_list.clear()
        for m in models:
            caps=", ".join(m.get("capabilities") or []) or "text"
            it=QListWidgetItem(f"{m.get('id')}  •  {caps}")
            it.setData(32,m); self.ai_models_list.addItem(it)
        self.ai_saved_list.clear()
        profiles=self.app.config.get("ai_profiles", []) or []
        active=self.app.config.get("ai_model") or ""
        for m in profiles:
            mid=str(m.get("id") or m.get("model") or "")
            caps=", ".join(m.get("capabilities") or [])
            mark="✅ AKTIF" if mid==active else ""
            it=QListWidgetItem(f"{mid}  •  {caps}  {mark}")
            it.setData(32,m); self.ai_saved_list.addItem(it)

    def _add_selected_ai_model(self):
        item=self.ai_models_list.currentItem()
        if not item: return
        model=item.data(32) or {}
        profiles=list(self.app.config.get("ai_profiles", []) or [])
        mid=str(model.get("id") or "")
        if not mid: return
        if not any(str(x.get("id") or x.get("model") or "") == mid for x in profiles): profiles.append(model)
        self.app.config.set("ai_profiles",profiles)
        self._render_ai_model_lists(); self.ai_status.setText(f"✅ {mid} ditambahkan ke AI tersimpan")

    def _use_selected_ai_model(self):
        item=self.ai_models_list.currentItem()
        if not item: return
        self._activate_ai_model(item.data(32) or {})

    def _use_saved_ai_model(self):
        item=self.ai_saved_list.currentItem()
        if item: self._activate_ai_model(item.data(32) or {})

    def _activate_ai_model(self,model):
        mid=str(model.get("id") or model.get("model") or "").strip()
        if not mid:return
        self.app.config.set("ai_model",mid)
        profiles=list(self.app.config.get("ai_profiles",[]) or [])
        if not any(str(x.get("id") or x.get("model") or "") == mid for x in profiles):
            profiles.append(model); self.app.config.set("ai_profiles",profiles)
        self._render_ai_model_lists(); self.ai_status.setText(f"✅ Model aktif: {mid}"); self.ai_settings_changed.emit()

    def _delete_saved_ai_model(self):
        item=self.ai_saved_list.currentItem()
        if not item:return
        mid=str((item.data(32) or {}).get("id") or "")
        profiles=[x for x in (self.app.config.get("ai_profiles",[]) or []) if str(x.get("id") or x.get("model") or "") != mid]
        self.app.config.set("ai_profiles",profiles)
        if self.app.config.get("ai_model") == mid:self.app.config.set("ai_model","")
        self._render_ai_model_lists(); self.ai_settings_changed.emit()

    def _save(self):
        if hasattr(self,"ai_manual_model") and self.ai_manual_model.text().strip():
            self.app.config.set("ai_model", self.ai_manual_model.text().strip())
        manual_endpoint = self.ai_endpoint.text().strip()
        manual_key = self.ai_key.text().strip()
        manual_provider = self._ai_provider_value()
        self.app.config.update({
            "out_dir": self.out_dir.text().strip(),
            "quality": self.quality.currentText(),
            "output_format": self.format_cb.currentText(),
            "h264": self.h264.isChecked(),
            "filename_template": self.tmpl.currentText(),
            "speed_limit": self.speed.currentText(),
            "parallel": int(self.parallel.value()),
            "subfolders": self.cb_subfolders.isChecked(),
            "subtitles": self.cb_subtitles.isChecked(),
            "thumbnail": self.cb_thumbnail.isChecked(),
            "ask_duplicates": self.cb_ask_duplicates.isChecked(),
            "download_playlist": self.cb_download_playlist.isChecked(),
            "playlist_items": self.playlist_items.text().strip(),
            "cookies_file": self.cookies.text().strip(),
            "browser_cookie_source": self.browser_cookie.currentText(),
            "proxy": self.proxy.text().strip(),
            "theme": self.theme_cb.currentText(),
            "clip_default_duration": int(self.clip_dur.value()),
            "clip_overlap": int(self.clip_overlap.value()),
            "clip_aspect": self.clip_aspect.currentText(),
            "clip_quality": self.clip_quality.currentText(),
            "clip_output_dir": self.clip_out.text().strip(),
            "clip_parallel": int(self.clip_parallel.value()),
            "transcribe_model": self.tr_model.currentText(),
            "transcribe_model_dir": self.tr_model_dir.text().strip(),
            "transcribe_language": self.tr_lang.currentText(),
            "transcribe_device": self.tr_device.currentText(),
            "transcribe_cuda_preflight": True,
            "word_timestamps": bool(self.tr_word.isChecked()),
            "ai_provider": manual_provider,
            "ai_endpoint": manual_endpoint,
            "ai_api_key": manual_key,
            "ai_settings_user_configured": bool(manual_provider not in ("", "none", "local") and manual_endpoint and manual_key),
            "ai_model": self.app.config.get("ai_model") or "",
            "ai_vision_model": self.ai_vision_model.text().strip() if hasattr(self,"ai_vision_model") else str(self.app.config.get("ai_vision_model") or ""),
            "ai_vision_preference": "",
            "ai_local_enabled": True,
            "ai_local_vision": True,
            "ai_timeout": int(self.ai_timeout.value()),
            "ai_auto_model": bool(self.ai_auto_model.isChecked()),
            "ai_auto_visual": bool(self.ai_auto_visual.isChecked()),
            "ai_failover_local": bool(self.ai_failover_local.isChecked()),
            "project_dir": self.storage_project_dir.text().strip(),
            "cache_dir": self.storage_cache_dir.text().strip(),
            "temp_dir": self.storage_temp_dir.text().strip(),
            "ai_models_cache": getattr(self, "ai_models_cache", []),
        })
        self._refresh_disk()
        self.ai_settings_changed.emit()
        QMessageBox.information(self, "Tersimpan", "Pengaturan disimpan. AI yang sudah terhubung akan dipakai otomatis oleh Content Clipper AI.")
