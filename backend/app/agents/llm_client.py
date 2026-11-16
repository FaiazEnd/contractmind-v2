"""Multi-Provider LLM Gateway (Gemini, Ollama, OpenAI, Anthropic) with automatic fallback simulator."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable
import httpx

from app.config import settings
from app.models.audit import calculate_cost


@dataclass
class LLMResponse:
    text: str
    provider: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    used_fallback: bool = False


class LLMGateway:
    """Routes prompts to configured provider with seamless fallback to secondary/simulator."""

    def __init__(self) -> None:
        self.provider: str = settings.DEFAULT_LLM_PROVIDER or "gemini"
        self.model: str = settings.DEFAULT_LLM_MODEL or "gemini-2.5-flash"
        self.gemini_api_key: str = settings.GEMINI_API_KEY or ""
        self.openai_api_key: str = settings.OPENAI_API_KEY or ""
        self.anthropic_api_key: str = settings.ANTHROPIC_API_KEY or ""
        self.ollama_base_url: str = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.ollama_model: str = settings.OLLAMA_MODEL or "qwen3.5:4b"

    def get_config(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
            "has_gemini_key": bool(self.gemini_api_key),
            "has_openai_key": bool(self.openai_api_key),
            "has_anthropic_key": bool(self.anthropic_api_key),
            "available_providers": [
                {"id": "gemini", "name": "Google Gemini", "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]},
                {"id": "simulator", "name": "Deterministic Legal Simulator", "models": ["simulator"]},
                {"id": "ollama", "name": "Local Ollama", "models": ["qwen3.5:4b", "llama3.2"]},
                {"id": "openai", "name": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini"]},
                {"id": "anthropic", "name": "Anthropic", "models": ["claude-3-5-sonnet"]},
            ],
        }

    def update_config(
        self,
        provider: str | None = None,
        model: str | None = None,
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
    ) -> dict[str, Any]:
        if provider:
            self.provider = provider.strip().lower()
        if model:
            self.model = model.strip()
        if gemini_api_key is not None and gemini_api_key.strip():
            self.gemini_api_key = gemini_api_key.strip()
        if openai_api_key is not None and openai_api_key.strip():
            self.openai_api_key = openai_api_key.strip()
        if anthropic_api_key is not None and anthropic_api_key.strip():
            self.anthropic_api_key = anthropic_api_key.strip()
        if ollama_base_url is not None and ollama_base_url.strip():
            self.ollama_base_url = ollama_base_url.strip().rstrip("/")
        if ollama_model is not None and ollama_model.strip():
            self.ollama_model = ollama_model.strip()
        return self.get_config()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len((text or "").split()) * 4 // 3)

    async def _call_gemini(self, prompt: str, system_prompt: str, model: str) -> tuple[str, int, int]:
        if not self.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")
        alias_map = {
            "gemini-3.5-flash-lite": "gemini-2.5-flash-lite",
            "gemini-1.5-flash": "gemini-2.5-flash",
        }
        target_model = alias_map.get(model or "", model or "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.gemini_api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        candidates = data.get("candidates") or []
        text = candidates[0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata") or {}
        p_tok = int(usage.get("promptTokenCount") or self._estimate_tokens(system_prompt + prompt))
        c_tok = int(usage.get("candidatesTokenCount") or self._estimate_tokens(text))
        return text.strip(), p_tok, c_tok

    async def _call_ollama(self, prompt: str, system_prompt: str, model: str) -> tuple[str, int, int]:
        target_model = model or self.ollama_model or "qwen3.5:4b"
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            "model": target_model,
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = str(data.get("response", "")).strip()
        if not text:
            raise RuntimeError("Empty response from Ollama")
        p_tok = int(data.get("prompt_eval_count") or self._estimate_tokens(system_prompt + prompt))
        c_tok = int(data.get("eval_count") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def _call_openai(self, prompt: str, system_prompt: str, model: str) -> tuple[str, int, int]:
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        target_model = model or "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}
        payload = {
            "model": target_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage") or {}
        p_tok = int(usage.get("prompt_tokens") or self._estimate_tokens(system_prompt + prompt))
        c_tok = int(usage.get("completion_tokens") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def _call_anthropic(self, prompt: str, system_prompt: str, model: str) -> tuple[str, int, int]:
        if not self.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        target_model = model or "claude-3-5-sonnet-20241022"
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": target_model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = data["content"][0]["text"].strip()
        usage = data.get("usage") or {}
        p_tok = int(usage.get("input_tokens") or self._estimate_tokens(system_prompt + prompt))
        c_tok = int(usage.get("output_tokens") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        fallback_fn: Callable[[], str],
    ) -> LLMResponse:
        """Invoke active provider, falling back cleanly to secondary or deterministic simulator."""
        start = time.time()
        chosen_provider = self.provider
        chosen_model = self.model
        used_fallback = False

        if chosen_provider != "simulator":
            provider_map = {
                "gemini": self._call_gemini,
                "ollama": self._call_ollama,
                "openai": self._call_openai,
                "anthropic": self._call_anthropic,
            }
            fn = provider_map.get(chosen_provider)
            if fn:
                try:
                    text, p_tok, c_tok = await fn(prompt, system_prompt, chosen_model)
                    latency_ms = round((time.time() - start) * 1000.0, 2)
                    cost = calculate_cost(chosen_model, p_tok, c_tok)
                    return LLMResponse(
                        text=text,
                        provider=chosen_provider,
                        model_name=chosen_model,
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        total_tokens=p_tok + c_tok,
                        latency_ms=latency_ms,
                        estimated_cost_usd=cost,
                        used_fallback=False,
                    )
                except Exception:
                    used_fallback = True

        # Deterministic legal simulation fallback
        text = fallback_fn()
        p_tok = self._estimate_tokens(system_prompt + prompt)
        c_tok = self._estimate_tokens(text)
        latency_ms = round((time.time() - start) * 1000.0, 2)
        eff_model = chosen_model if chosen_provider != "simulator" else (chosen_model or "gemini-3.5-flash-lite")
        cost = calculate_cost("simulator" if used_fallback or chosen_provider == "simulator" else eff_model, p_tok, c_tok)
        return LLMResponse(
            text=text,
            provider="simulator",
            model_name=f"{eff_model} (sim)" if used_fallback else eff_model,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=max(0.5, latency_ms),
            estimated_cost_usd=cost,
            used_fallback=used_fallback,
        )


llm_gateway = LLMGateway()
