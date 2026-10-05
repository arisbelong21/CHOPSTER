"""Embedded Gemini visual/editor AI for Chopster.

This is intentionally separate from the optional AI configured in Settings.
The embedded channel is Gemini-only and is used for frame/scene/camera visual
reasoning. It auto-discovers Gemini model IDs exposed by the configured router
and never falls back to Claude/Kimi/OpenAI.
"""
from __future__ import annotations

from typing import Any

from chopster.ai.api_provider import APIProvider, model_capabilities, score_model
from chopster.ai.provider_interface import AIRequest, AIResponse

EMBEDDED_GEMINI_ENDPOINT = "https://vansrouter.farzani.shop/v1"
EMBEDDED_GEMINI_API_KEY = "sk-2f04a3152a9b10ee-fm2p3h-6862f99d"
# Empty on purpose: choose an exact Gemini route from /v1/models when available.
EMBEDDED_GEMINI_MODEL = ""
# Known Gemini-only routes documented by VansRouter; these are fallbacks when
# /v1/models is unavailable. They intentionally remain Gemini-only.
EMBEDDED_GEMINI_FALLBACK_MODELS = (
    "gc/gemini-3-flash-preview",
    "vertex/gemini-3.1-pro-preview",
    "ag/gemini-3.7-flash-high",
    "gh/gemini-3.1-pro-preview",
)


def _is_gemini_model(model_id: str) -> bool:
    return "gemini" in str(model_id or "").lower()


def _rank_gemini_models(models: list[dict[str, Any]], *, vision: bool = False) -> list[str]:
    rows = []
    for model in models or []:
        mid = str(model.get("id") or "").strip()
        if not mid or not _is_gemini_model(mid):
            continue
        caps = set(model_capabilities(model))
        # Some routers omit explicit vision capabilities. Gemini routes are treated
        # as potential multimodal candidates and the actual request validates it.
        if vision and "vision" not in caps:
            caps.add("vision")
        score = score_model({**model, "capabilities": sorted(caps)}, vision)
        rows.append((score, mid))
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [mid for _, mid in rows]


class EmbeddedGeminiProvider(APIProvider):
    """Gemini-only AI provider embedded in Chopster's visual/editor path."""

    def __init__(self, timeout: int = 45, model: str = EMBEDDED_GEMINI_MODEL):
        super().__init__(
            endpoint=EMBEDDED_GEMINI_ENDPOINT,
            api_key=EMBEDDED_GEMINI_API_KEY,
            model=model,
            timeout=timeout,
            vision_model=model,
            retry_5xx=False,
        )
        self.embedded_model = model or ""
        self.last_attempts: list[str] = []

    @property
    def name(self) -> str:
        return "embedded-gemini"

    def _discover_candidates(self, *, vision: bool = False, refresh: bool = False) -> list[str]:
        candidates: list[str] = []
        if self.embedded_model and _is_gemini_model(self.embedded_model):
            candidates.append(self.embedded_model)
        if refresh or not self.models_cache:
            try:
                self.models_cache = self.discover_models()
            except Exception:
                pass
        # Prefer exact models exposed by this key/router.
        for mid in _rank_gemini_models(self.models_cache, vision=vision):
            if mid not in candidates:
                candidates.append(mid)
        # Only use known provider-qualified Gemini routes when discovery is unavailable.
        for mid in EMBEDDED_GEMINI_FALLBACK_MODELS:
            if mid not in candidates:
                candidates.append(mid)
        return candidates[:6]

    @staticmethod
    def _is_model_level_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(token in text for token in ("404", "403", "422", "model", "provider"))

    def generate(self, req: AIRequest) -> AIResponse:
        last: Exception | None = None
        self.last_attempts = []
        # Do discovery first. This avoids the old unqualified `gemini-*` route that
        # could be interpreted as provider `gemini` and rejected by the router ACL.
        # Reuse a discovered model list within this provider instance. Refreshing
        # /models before every request adds latency and makes offline/unit-test
        # behavior depend on a live router.
        candidates = self._discover_candidates(vision=False, refresh=not bool(self.models_cache))
        for selected in candidates:
            self.last_attempts.append(selected)
            try:
                cloned = AIRequest(
                    prompt=req.prompt,
                    system=req.system,
                    model=selected,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    timeout=req.timeout,
                )
                resp = super().generate(cloned)
                self.embedded_model = selected
                if isinstance(resp.raw, dict):
                    resp.raw["provider"] = "embedded-gemini"
                    resp.raw["embedded"] = True
                    resp.raw["gemini_model"] = selected
                    resp.raw["gemini_attempts"] = list(self.last_attempts)
                return resp
            except Exception as exc:
                last = exc
                # A 403/404 may be provider/model-specific. Keep trying the next Gemini
                # route. Transport/auth failures that are not model-level stop quickly.
                if not self._is_model_level_error(exc) and any(token in str(exc).lower() for token in ("502", "503", "504", "timed out", "timeout", "401", "gagal terhubung")):
                    break
        raise RuntimeError(
            f"Embedded Gemini tidak tersedia. Attempts={self.last_attempts}. Last error={str(last)[:700] if last else 'unknown'}"
        )

    def generate_vision(
        self,
        prompt: str,
        image_paths: list[str],
        *,
        system: str = "",
        model: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: int | None = None,
    ) -> AIResponse:
        preferred = model.strip() if model and _is_gemini_model(model) else self.embedded_model
        candidates = []
        if preferred and _is_gemini_model(preferred):
            candidates.append(preferred)
        # Discovery is cached after the first successful lookup. Candidate-level
        # 403/404 handling below still tries the remaining provider-qualified routes.
        discovered = self._discover_candidates(vision=True, refresh=not bool(self.models_cache))
        for mid in discovered:
            if mid not in candidates:
                candidates.append(mid)
        last: Exception | None = None
        self.last_attempts = []
        for selected in candidates[:6]:
            self.last_attempts.append(selected)
            try:
                # Seed metadata only for this exact candidate; the actual multimodal
                # request is sent to /chat/completions and is validated by the router.
                self.models_cache = [{"id": selected, "capabilities": ["vision"], "vision": True}]
                resp = super().generate_vision(
                    prompt,
                    image_paths,
                    system=system,
                    model=selected,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout or self.timeout,
                )
                self.embedded_model = selected
                if isinstance(resp.raw, dict):
                    resp.raw["provider"] = "embedded-gemini-vision"
                    resp.raw["embedded"] = True
                    resp.raw["gemini_model"] = selected
                    resp.raw["gemini_attempts"] = list(self.last_attempts)
                return resp
            except Exception as exc:
                last = exc
                # Model/provider route denial should allow the next Gemini route.
                if not self._is_model_level_error(exc) and any(token in str(exc).lower() for token in ("502", "503", "504", "timed out", "timeout", "401", "gagal terhubung")):
                    break
        raise RuntimeError(
            f"Embedded Gemini Vision tidak tersedia. Attempts={self.last_attempts}. Last error={str(last)[:700] if last else 'unknown'}"
        )

    def health_probe(self) -> dict[str, Any]:
        result = {"ok": False, "provider": self.name, "model": self.embedded_model, "vision": False, "error": "", "models": [], "vision_models": []}
        try:
            models = self.discover_models()
            gemini = _rank_gemini_models(models, vision=False)
            gemini_vision = _rank_gemini_models(models, vision=True)
            result.update({"ok": True, "models": gemini, "vision_models": gemini_vision})
            if gemini:
                result["model"] = gemini[0]
            if gemini_vision:
                result["vision_model"] = gemini_vision[0]
                result["vision"] = True
        except Exception as exc:
            result["error"] = str(exc)[:700]
        return result
