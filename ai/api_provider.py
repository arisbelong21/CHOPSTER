"""OpenAI-compatible API provider with model discovery and vision support."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import time
from typing import Any
from pathlib import Path

from chopster.ai.provider_interface import AIProvider, AIRequest, AIResponse


def normalize_base_url(endpoint: str) -> str:
    """Normalize a base URL to the provider root, preserving /v1 when present."""
    value = (endpoint or "").strip().rstrip("/")
    if not value:
        return ""
    for suffix in ("/chat/completions", "/models"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    if value.endswith("/v1"):
        return value
    if "/v1/" in value:
        return value.split("/v1/", 1)[0] + "/v1"
    return value


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value]
    return []


def model_capabilities(model: dict[str, Any]) -> list[str]:
    """Return normalized capabilities, including conservative provider-side inference.

    Some OpenAI-compatible routers omit a ``capabilities`` field even though the
    underlying model accepts images. Chopster therefore also reads common
    ``modalities``/``input_modalities`` fields and, as a final conservative hint,
    recognizable vision-model names such as Gemini-Vision/VL families. This only
    affects model selection; the actual request is still allowed to fail and will
    fall back to the local engine.
    """
    caps = set(x.lower() for x in _string_list(model.get("capabilities")))
    for key in ("modalities", "input_modalities", "supported_modalities", "capability", "features"):
        for x in _string_list(model.get(key)):
            caps.add(x.lower())
    if bool(model.get("vision")) or bool(model.get("supports_vision")) or bool(model.get("vision_capable")):
        caps.add("vision")
    name = " ".join(str(model.get(k) or "") for k in ("id", "name", "model", "owned_by")).lower()
    vision_markers = (
        "gemini", "vision", "-vl", ".vl", "vl-", "llava", "pixtral",
        "qwen2.5-vl", "qwen3-vl", "internvl", "minicpm-v", "moondream",
        "gpt-4o", "gpt-4.1", "gpt-4.5", "claude-3", "claude-4", "claude-opus",
        "claude-sonnet", "claude-haiku"
    )
    if any(marker in name for marker in vision_markers):
        caps.add("vision")
    return sorted(caps)


def score_model(model: dict[str, Any], require_vision: bool = False) -> int:
    caps = set(model_capabilities(model))
    if require_vision and "vision" not in caps:
        return -10_000
    score = 0
    if "vision" in caps:
        score += 100
    name_blob = " ".join(str(model.get(k) or "") for k in ("id", "name", "model", "owned_by")).lower()
    if "gemini" in name_blob:
        score += 70 if require_vision else 25
    if any(x in name_blob for x in ("vl", "vision", "llava", "pixtral", "internvl", "moondream")):
        score += 35 if require_vision else 8
    if "reasoning" in caps:
        score += 35
    if "tools" in caps:
        score += 18
    if "streaming" in caps:
        score += 8
    if "json_mode" in caps:
        score += 8
    score += min(int(model.get("context_length") or model.get("context_window") or 0) // 100_000, 10)
    return score


def choose_best_model(models: list[dict[str, Any]], require_vision: bool = False, preferred: str = "") -> dict[str, Any] | None:
    usable = [m for m in models if not require_vision or "vision" in model_capabilities(m)]
    if not usable:
        return None
    chosen = None
    if preferred:
        for m in usable:
            if str(m.get("id")) == preferred:
                chosen = m
                break
    if chosen is None:
        chosen = sorted(usable, key=lambda m: (score_model(m, require_vision), str(m.get("id") or "")), reverse=True)[0]
    normalized = dict(chosen)
    normalized["capabilities"] = model_capabilities(normalized)
    return normalized


def _extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                parts.append(str(item.get("text") or ""))
        return "\n".join(x for x in parts if x)
    return str(content or "")


class APIProvider(AIProvider):
    def __init__(self, endpoint: str, api_key: str, model: str = "", timeout: int = 60, vision_model: str = "", retry_5xx: bool = True):
        self.base_url = normalize_base_url(endpoint)
        self.endpoint = self.base_url + "/chat/completions" if self.base_url else ""
        self.api_key = api_key or ""
        self.model = model or ""
        self.vision_model = vision_model or ""
        self.timeout = max(5, int(timeout or 60))
        self.retry_5xx = bool(retry_5xx)
        self.models_cache: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "api"

    def is_available(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, "Base URL belum diatur"
        if not self.api_key:
            return False, "API key belum diatur"
        return True, "Siap"

    def _request_json(self, url: str, payload: dict[str, Any] | None = None, method: str = "GET", timeout: int | None = None, _allow_5xx_retry: bool = True) -> dict[str, Any]:
        ok, msg = self.is_available()
        if not ok:
            raise RuntimeError(msg)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154.0 Safari/537.36 ChopsterByAris/6.7",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as resp:
                raw = resp.read().decode("utf-8", "ignore")
            return json.loads(raw or "{}")
        except urllib.error.HTTPError as he:
            try:
                body = he.read().decode("utf-8", "ignore")[:3000]
                js = json.loads(body) if body else {}
                err = js.get("error", {}).get("message") or body or str(he)
            except Exception:
                err = str(he)
            # Cloudflare/proxy 5xx can be transient, and some Windows networking
            # stacks reach the same endpoint more reliably through the native curl.exe.
            # Retry a couple of times, then try curl with HTTP/1.1 before declaring the
            # remote provider unavailable. This never falls through silently.
            if he.code in (502, 503, 504) and _allow_5xx_retry and self.retry_5xx:
                retry_timeout = timeout or self.timeout
                for attempt in range(1, 3):
                    time.sleep(0.6 * attempt)
                    try:
                        return self._request_json(url, payload=payload, method=method, timeout=retry_timeout, _allow_5xx_retry=False)
                    except RuntimeError:
                        pass
                try:
                    return self._request_via_curl(url, payload, method, retry_timeout, force_http11=True)
                except Exception:
                    cloud = " Cloudflare 5xx biasanya berarti gateway tidak berhasil berbicara dengan origin/upstream." if "cloudflare" in err.lower() else ""
                    raise RuntimeError(f"AI server tidak tersedia ({he.code}): {err[:500]}.{cloud}")
            # Some Windows installations can reach providers with curl.exe while
            # Python's urllib request is challenged by Cloudflare.
            if he.code == 403 and any(token in err.lower() for token in ("cloudflare", "error 1010", "access denied")):
                return self._request_via_curl(url, payload, method, timeout or self.timeout)
            if he.code == 401:
                raise RuntimeError(f"API key tidak valid (401): {err[:400]}")
            if he.code == 403:
                raise RuntimeError(f"Akses ditolak (403): {err[:400]}")
            if he.code == 404:
                raise RuntimeError(f"Endpoint tidak ditemukan (404): {err[:400]}")
            if he.code == 422:
                raise RuntimeError(f"Request tidak didukung (422): {err[:500]}")
            if he.code == 429:
                raise RuntimeError(f"Rate limit (429): {err[:400]}")
            raise RuntimeError(f"API error {he.code}: {err[:700]}")
        except Exception as exc:
            # Retry low-level connection failures through curl, which is available on
            # supported Windows installations.
            if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
                try:
                    return self._request_via_curl(url, payload, method, timeout or self.timeout, force_http11=True)
                except Exception:
                    pass
            raise RuntimeError(f"Gagal terhubung ke AI API: {exc}") from exc

    def _request_via_curl(self, url: str, payload: dict[str, Any] | None, method: str, timeout: int, force_http11: bool = False) -> dict[str, Any]:
        curl = shutil.which("curl.exe") or shutil.which("curl")
        if not curl:
            raise RuntimeError("Clean APIs ditolak oleh Cloudflare dari Python dan curl.exe tidak ditemukan di Windows.")
        # Keep API key and request body out of the process command line.
        with tempfile.TemporaryDirectory(prefix="chopster_ai_") as td:
            cfg = Path(td) / "request.cfg"
            body_path = Path(td) / "body.json"
            lines = [
                f'url = "{url}"',
                'silent',
                'show-error',
                f'max-time = {int(timeout)}',
                'header = "Accept: application/json"',
                f'header = "Authorization: Bearer {self.api_key}"',
                f'header = "x-api-key: {self.api_key}"',
                'header = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154.0 Safari/537.36 ChopsterByAris/6.7"',
            ]
            if payload is not None:
                body_path.write_text(json.dumps(payload), encoding="utf-8")
                lines += [
                    f'header = "Content-Type: application/json"',
                    f'data-binary = "@{body_path.as_posix()}"',
                    f'request = "{method}"',
                ]
            cfg.write_text("\n".join(lines), encoding="utf-8")
            cmd=[curl, "--config", str(cfg)]
            if force_http11:
                cmd.insert(1, "--http1.1")
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=max(5, int(timeout)+5),
                # Windowed EXE: never flash a console for curl.exe on Windows.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode != 0:
                msg = (proc.stderr or proc.stdout or "curl gagal").strip()
                raise RuntimeError(f"Gagal terhubung ke Clean APIs via curl: {msg[:700]}")
            try:
                return json.loads(proc.stdout or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Clean APIs mengembalikan respons yang tidak valid: {(proc.stdout or '')[:500]}") from exc

    def connection_probe(self, preferred_model: str = "") -> dict[str, Any]:
        """Probe model discovery first, then optionally direct inference.

        This lets Settings distinguish a healthy API from an unavailable /v1/models
        route without discarding previously cached models.
        """
        result: dict[str, Any] = {"ok": False, "models": [], "model_route_ok": False, "inference_ok": False}
        try:
            models = self.discover_models()
            result.update({"ok": True, "models": models, "model_route_ok": True, "message": f"{len(models)} model"})
            return result
        except Exception as exc:
            result["model_error"] = str(exc)[:900]
            # A router may have a working chat route while its model-list route is
            # temporarily unavailable. If a model is known locally, test it directly.
            selected = preferred_model or self.model or (self.models_cache[0].get("id") if self.models_cache else "")
            if selected:
                try:
                    resp = self.test_inference(selected)
                    result.update({"ok": True, "inference_ok": True, "model": selected, "message": resp.text.strip() or "OK"})
                    return result
                except Exception as infer_exc:
                    result["inference_error"] = str(infer_exc)[:900]
            result["message"] = result.get("model_error") or "AI endpoint tidak merespons"
            return result

    def discover_models(self) -> list[dict[str, Any]]:
        """Read model metadata from GET /models."""
        js = self._request_json(self.base_url + "/models")
        rows = js.get("data") or []
        if not isinstance(rows, list):
            raise RuntimeError("Respons /models tidak valid")
        models: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict) and row.get("id"):
                normalized = dict(row)
                normalized["capabilities"] = model_capabilities(normalized)
                models.append(normalized)
        self.models_cache = models
        return models

    def test_inference(self, model: str | None = None) -> AIResponse:
        selected = model or self.model
        if not selected:
            models = self.models_cache or self.discover_models()
            best = choose_best_model(models)
            selected = str(best.get("id")) if best else ""
        if not selected:
            raise RuntimeError("Belum ada model yang bisa dipakai")
        return self.generate(AIRequest(prompt="Balas tepat satu kata: OK", system="Kamu sedang diuji koneksinya. Jangan jelaskan apa pun.", model=selected, max_tokens=32, timeout=self.timeout))

    def _build_payload(self, req: AIRequest, model: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or ([{"role": "system", "content": req.system}] if req.system else []) + [{"role": "user", "content": req.prompt}],
            "temperature": req.temperature,
        }
        if req.max_tokens:
            payload["max_tokens"] = max(2048 if req.max_tokens < 2048 else req.max_tokens, 2048) if model.lower().startswith(("gpt-", "claude-")) else req.max_tokens
        return payload

    def generate(self, req: AIRequest) -> AIResponse:
        ok, msg = self.is_available()
        if not ok:
            raise RuntimeError(msg)
        model = req.model or self.model
        if not model:
            models = self.models_cache or self.discover_models()
            chosen = choose_best_model(models)
            if not chosen:
                raise RuntimeError("Model belum dipilih dan daftar model kosong")
            model = str(chosen["id"])
        payload = self._build_payload(req, model)
        js = self._request_json(self.endpoint, payload=payload, method="POST", timeout=req.timeout or self.timeout)
        choices = js.get("choices") or []
        text = ""
        if choices:
            msg_obj = choices[0].get("message") or {}
            text = _extract_message_text(msg_obj.get("content") if isinstance(msg_obj, dict) else "") or str(choices[0].get("text") or "")
        if not text and js.get("error"):
            raise RuntimeError(str(js["error"].get("message") or "AI tidak mengembalikan jawaban"))
        js.setdefault("_chopster_model", model)
        js.setdefault("_chopster_capabilities", model_capabilities({"id": model}))
        return AIResponse(text=text, raw=js, usage=js.get("usage"))

    def generate_vision(self, prompt: str, image_paths: list[str], system: str = "", model: str = "", temperature: float = 0.2, max_tokens: int = 4096, timeout: int | None = None) -> AIResponse:
        """Send images to an OpenAI-compatible multimodal model.

        Explicitly configured model IDs are tried DIRECTLY even when the model name
        does not contain a recognizable Vision marker. If that direct attempt returns
        404/unsupported, Chopster falls back to /models discovery and prefers Gemini
        or other clearly multimodal models. This prevents a broken /models route from
        making an otherwise working chat/completions Vision model unusable.
        """
        preferred=(model or self.vision_model or "").strip()
        candidate_ids=[]
        if preferred:
            candidate_ids.append(preferred)
        try:
            if not self.models_cache:
                self.models_cache=self.discover_models()
            models=self.models_cache
            chosen=choose_best_model(models, require_vision=True, preferred=preferred)
            if chosen:
                cid=str(chosen.get("id") or "")
                if cid and cid not in candidate_ids:
                    candidate_ids.append(cid)
        except Exception:
            # /models is optional when an explicit model id has been configured.
            pass
        if not candidate_ids:
            raise RuntimeError("Model Vision belum dipilih. Klik Refresh Models lalu pilih model Gemini/Vision, atau isi VISION MODEL ID secara manual.")

        last_error=None
        for selected in candidate_ids[:3]:
            content:[dict[str,Any]]=[{"type":"text","text":prompt}]
            for path in image_paths:
                p=str(path)
                with open(p,"rb") as fh:
                    encoded=base64.b64encode(fh.read()).decode("ascii")
                suffix=p.lower().rsplit(".",1)[-1] if "." in p else "jpg"
                mime={"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp","gif":"image/gif"}.get(suffix,"image/jpeg")
                content.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{encoded}"}})
            req=AIRequest(prompt=prompt, system=system, model=selected, temperature=temperature, max_tokens=max_tokens, timeout=timeout or self.timeout)
            messages=([{"role":"system","content":system}] if system else [])+[ {"role":"user","content":content} ]
            payload=self._build_payload(req,selected,messages=messages)
            try:
                js=self._request_json(self.endpoint,payload=payload,method="POST",timeout=timeout or self.timeout)
                choices=js.get("choices") or []
                text=""
                if choices:
                    msg_obj=choices[0].get("message") or {}
                    text=_extract_message_text(msg_obj.get("content") if isinstance(msg_obj,dict) else "")
                if not text and js.get("error"):
                    raise RuntimeError(str(js["error"].get("message") or "AI Vision tidak mengembalikan jawaban"))
                js.setdefault("_chopster_model",selected)
                js.setdefault("_chopster_capabilities",model_capabilities({"id":selected}))
                return AIResponse(text=text,raw=js,usage=js.get("usage"))
            except Exception as exc:
                last_error=exc
                # Try the discovered alternative after a direct-model failure.
                continue
        raise RuntimeError(str(last_error) if last_error else "AI Vision gagal")
