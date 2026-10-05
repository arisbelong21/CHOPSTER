"""Central AI orchestration for Chopster.

There are two distinct remote AI layers:
1) Embedded Gemini: shipped/configured inside Chopster and used by default for
   visual/editor intelligence, especially frame analysis and camera decisions.
2) Settings AI: optional user-configured provider. When configured, it can be
   used by every feature and can refine embedded-Gemini results for vision.

Local OpenCV/heuristics remain the last-resort safety net.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from chopster.ai.api_provider import APIProvider
from chopster.ai.embedded_gemini import EmbeddedGeminiProvider
from chopster.ai.local_provider import LocalProvider
from chopster.ai.provider_interface import AIRequest, AIResponse, AIProvider


@dataclass
class AIHealth:
    state: str = "ready"  # ready | online | degraded | offline | local
    failures: int = 0
    last_error: str = ""
    last_success: float = 0.0
    disabled_until: float = 0.0

    @property
    def circuit_open(self) -> bool:
        return self.disabled_until > time.time()


class AIOrchestrator:
    """Single gateway between all features and all AI layers."""

    _settings_health: dict[str, AIHealth] = {}

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = dict(config or {})
        self.provider_name = str(self.config.get("ai_provider") or "none").strip()
        self.endpoint = str(self.config.get("ai_endpoint") or "").strip()
        self.api_key = str(self.config.get("ai_api_key") or "").strip()
        self.model = str(self.config.get("ai_model") or "").strip()
        self.settings_enabled = self.provider_name not in ("", "none", "local") and bool(self.endpoint and self.api_key)
        self.failover_local = bool(self.config.get("ai_failover_local", True))
        self.cooldown = max(5.0, float(self.config.get("ai_failover_cooldown", 60) or 60))
        self.embedded_enabled = bool(self.config.get("ai_embedded_gemini_enabled", True))
        self.local = LocalProvider()
        self._remote: AIProvider | None = None
        self._embedded: EmbeddedGeminiProvider | None = None
        self._embedded_health = AIHealth()
        self._settings_health_state = self._settings_health.setdefault(self.key, AIHealth())

    @property
    def key(self) -> str:
        return f"settings|{self.endpoint}|{self.model}|{self.provider_name}"

    @property
    def health(self) -> AIHealth:
        return self._settings_health_state

    def _embedded_state(self) -> AIHealth:
        return self._embedded_health

    def _vision_prefers_local_evidence(self) -> bool:
        pref = str(self.config.get("ai_vision_preference") or "").strip().lower()
        return pref in {"local_first", "hybrid", "evidence_first"}

    def status(self) -> dict[str, Any]:
        sh = self.health
        if not self.settings_enabled:
            settings_state = "not-configured"
        elif sh.circuit_open:
            settings_state = "degraded"
        elif sh.last_success:
            settings_state = "online"
        else:
            settings_state = "ready"
        eh = self._embedded_state()
        if not self.embedded_enabled:
            embedded_state = "disabled"
        elif eh.circuit_open:
            embedded_state = "degraded"
        elif eh.last_success:
            embedded_state = "online"
        else:
            embedded_state = "ready"
        overall = "online" if embedded_state == "online" or settings_state == "online" else ("degraded" if embedded_state == "degraded" or settings_state == "degraded" else "ready")
        return {
            "state": overall,
            # Backward-compatible top-level fields used by older UI/tests.
            "failures": sh.failures,
            "last_error": sh.last_error or eh.last_error,
            "last_success": max(sh.last_success, eh.last_success),
            "cooldown_remaining": max(max(0.0, sh.disabled_until - time.time()), max(0.0, eh.disabled_until - time.time())),
            "provider": self.provider_name if self.settings_enabled else "embedded-gemini",
            "model": self.model or getattr(self._embedded_provider(), "embedded_model", "Gemini Auto"),
            "settings": {
                "state": settings_state,
                "provider": self.provider_name if self.settings_enabled else "none",
                "model": self.model,
                "last_error": sh.last_error,
            },
            "embedded_gemini": {
                "state": embedded_state,
                "model": getattr(self._embedded_provider(), "embedded_model", "Gemini Auto") if self.embedded_enabled else "",
                "last_error": eh.last_error,
            },
            "fallback_local": self.failover_local,
        }

    def remote_provider(self, *, require_vision: bool = False) -> AIProvider | None:
        """Return optional user-configured Settings AI."""
        if not self.settings_enabled or self.health.circuit_open:
            return None
        if self._remote is None:
            self._remote = APIProvider(
                endpoint=self.endpoint,
                api_key=self.api_key,
                model=self.model,
                timeout=int(self.config.get("ai_timeout") or 60),
                vision_model=str(self.config.get("ai_vision_model") or ""),
            )
        ok, _ = self._remote.is_available()
        return self._remote if ok else None

    def _embedded_provider(self) -> EmbeddedGeminiProvider | None:
        if not self.embedded_enabled:
            return None
        if self._embedded is None:
            self._embedded = EmbeddedGeminiProvider(timeout=int(self.config.get("ai_timeout") or 60))
        ok, _ = self._embedded.is_available()
        return self._embedded if ok else None

    def _record_settings_success(self) -> None:
        h = self.health
        h.failures = 0; h.last_error = ""; h.last_success = time.time(); h.disabled_until = 0.0; h.state = "online"

    def _record_settings_failure(self, exc: Exception | str) -> None:
        h = self.health
        h.failures += 1; h.last_error = str(exc)[:700]; h.disabled_until = time.time() + self.cooldown; h.state = "degraded"

    def _record_embedded_success(self) -> None:
        h = self._embedded_state()
        h.failures = 0; h.last_error = ""; h.last_success = time.time(); h.disabled_until = 0.0; h.state = "online"

    def _record_embedded_failure(self, exc: Exception | str) -> None:
        h = self._embedded_state()
        h.failures += 1; h.last_error = str(exc)[:700]; h.disabled_until = time.time() + self.cooldown; h.state = "degraded"

    def local_response(self, fn: Callable[[], AIResponse | str]) -> AIResponse:
        result = fn()
        if isinstance(result, AIResponse):
            return result
        return AIResponse(text=str(result or ""), raw={"provider": "local", "fallback": True})

    def _bounded_request(self, req: AIRequest) -> AIRequest:
        if not self.failover_local:
            return req
        return AIRequest(
            prompt=req.prompt, system=req.system, model=req.model,
            temperature=req.temperature, max_tokens=req.max_tokens,
            timeout=min(int(req.timeout or 60), max(5, int(self.config.get("ai_failover_timeout") or 15))),
        )

    def generate(self, req: AIRequest, *, local_fallback: Callable[[], AIResponse | str] | None = None) -> AIResponse:
        """Text/reasoning route: Settings AI first; local fallback when Settings AI is absent.

        Embedded Gemini is intentionally NOT used for captions/analysis text. Its job is
        visual/frame/scene/camera understanding. This keeps the two AI services separate.
        """
        bounded = self._bounded_request(req)
        errors=[]

        if self.settings_enabled:
            provider = self.remote_provider()
            if provider is not None and not self.health.circuit_open:
                try:
                    reviewed = provider.generate(bounded)
                    self._record_settings_success()
                    if isinstance(reviewed.raw, dict):
                        reviewed.raw.setdefault("provider", "settings-ai")
                        reviewed.raw["ai_layer"]="settings"
                        reviewed.raw["provider_chain"]=["settings-ai"]
                    return reviewed
                except Exception as exc:
                    self._record_settings_failure(exc)
                    errors.append(f"settings: {exc}")
            else:
                errors.append(self.health.last_error or "Settings AI tidak tersedia")
        else:
            errors.append("Settings AI belum dikonfigurasi")

        if local_fallback and self.failover_local:
            resp = self.local_response(local_fallback)
            if isinstance(resp.raw, dict):
                resp.raw["provider"] = "local-fallback"
                resp.raw["ai_layer"] = "local"
                resp.raw["ai_error"] = " | ".join(errors)[-900:]
            return resp
        return self.local.generate(bounded)

    def generate_json(
        self,
        req: AIRequest,
        *,
        local_fallback: Callable[[], Any],
        validator: Callable[[Any], Any] | None = None,
    ) -> tuple[Any, AIResponse]:
        def fallback_response() -> AIResponse:
            value = local_fallback()
            return AIResponse(text=json.dumps(value, ensure_ascii=False), raw={"provider": "local-fallback", "fallback": True})

        resp = self.generate(req, local_fallback=fallback_response)
        raw = (resp.text or "").strip()
        if "```" in raw:
            m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.S | re.I)
            if m: raw = m.group(1).strip()
        try:
            value = json.loads(raw)
            if validator: value = validator(value)
            return value, resp
        except Exception as exc:
            value = local_fallback()
            return value, AIResponse(text=json.dumps(value, ensure_ascii=False), raw={"provider":"local-fallback","ai_error":str(exc)[:400],"fallback":True})

    def generate_vision(
        self, prompt: str, image_paths: list[str], *, system: str = "", model: str = "",
        temperature: float = 0.2, max_tokens: int = 4096, timeout: int | None = None,
        local_fallback: Callable[[], AIResponse | str] | None = None,
    ) -> AIResponse:
        """Visual route: Embedded Gemini first; local vision fallback.

        The optional Settings AI is deliberately not used here. Frame/scene/person
        understanding belongs to the embedded Gemini service.
        """
        local_resp=None
        local_evidence=""
        collect_local_first = bool(self.config.get("ai_local_vision", True)) and self._vision_prefers_local_evidence()
        if collect_local_first:
            try:
                local_resp=self.local.generate_vision(prompt,image_paths,system=system,model=model,temperature=temperature,max_tokens=max_tokens,timeout=timeout)
                local_evidence=(local_resp.text or "")[:9000]
            except Exception as exc:
                local_resp=AIResponse(text="",raw={"provider":"local-vision-ai","error":str(exc)[:300]})

        evidence_prompt=prompt
        if local_evidence:
            evidence_prompt += "\n\nLOCAL VISION EVIDENCE (verify visually; do not blindly trust):\n" + local_evidence

        errors=[]
        embedded=self._embedded_provider()
        if embedded is not None and not self._embedded_state().circuit_open:
            try:
                embedded_resp=embedded.generate_vision(
                    evidence_prompt,image_paths,system=system,model=model,temperature=temperature,
                    max_tokens=max_tokens,timeout=self._bounded_request(AIRequest(prompt="",timeout=timeout or self.config.get("ai_timeout") or 60)).timeout,
                )
                self._record_embedded_success()
                if isinstance(embedded_resp.raw,dict):
                    embedded_resp.raw.setdefault("provider","embedded-gemini-vision")
                    embedded_resp.raw["ai_layer"]="embedded-gemini"
                    embedded_resp.raw["provider_chain"]=["local-vision-ai","embedded-gemini-vision"] if local_evidence else ["embedded-gemini-vision"]
                    embedded_resp.raw["local_vision_evidence"]=local_evidence
                return embedded_resp
            except Exception as exc:
                self._record_embedded_failure(exc)
                errors.append(f"embedded-gemini: {exc}")
        else:
            errors.append(self._embedded_state().last_error or "Embedded Gemini belum tersedia")

        if local_fallback and self.failover_local:
            resp=self.local_response(local_fallback)
        else:
            if local_resp is None and bool(self.config.get("ai_local_vision", True)):
                try:
                    local_resp=self.local.generate_vision(prompt,image_paths,system=system,model=model,temperature=temperature,max_tokens=max_tokens,timeout=timeout)
                except Exception as exc:
                    local_resp=AIResponse(text="",raw={"provider":"local-vision-ai","error":str(exc)[:300]})
            resp=local_resp if local_resp is not None else self.local.generate_vision(prompt,image_paths,system=system,model=model,temperature=temperature,max_tokens=max_tokens,timeout=timeout)
        if isinstance(resp.raw,dict):
            resp.raw["provider"]="local-fallback"
            resp.raw["ai_layer"]="local"
            resp.raw["ai_error"]=" | ".join(errors)[-900:]
            resp.raw["local_vision_evidence"]=local_evidence
        return resp


def orchestrator_from_config(config: dict[str, Any] | None = None) -> AIOrchestrator:
    return AIOrchestrator(config or {})
