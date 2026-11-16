"""Multi-provider LLM Gateway with automatic fallback and real telemetry."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.models.audit import calculate_cost_usd


PROVIDER_MODELS: dict[str, list[str]] = {
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
        "gemini-3.5-flash-lite",
    ],
    "ollama": ["qwen3.5:4b", "llama3.2", "mistral"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-5-sonnet-20241022"],
}


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    is_fallback: bool = False


class LLMGateway:
    """Async multi-provider LLM client with runtime configuration and deterministic fallback."""

    def __init__(self) -> None:
        self.provider: str = settings.DEFAULT_LLM_PROVIDER.lower()
        self.model: str = settings.DEFAULT_LLM_MODEL
        self.gemini_api_key: str = settings.GEMINI_API_KEY
        self.openai_api_key: str = settings.OPENAI_API_KEY
        self.anthropic_api_key: str = settings.ANTHROPIC_API_KEY
        self.ollama_base_url: str = settings.OLLAMA_BASE_URL

    def get_status(self) -> dict[str, Any]:
        return {
            "active_provider": self.provider,
            "active_model": self.model,
            "available_providers": PROVIDER_MODELS,
            "keys_configured": {
                "gemini": bool(self.gemini_api_key),
                "openai": bool(self.openai_api_key),
                "anthropic": bool(self.anthropic_api_key),
                "ollama": True,
            },
            "ollama_base_url": self.ollama_base_url,
        }

    def update_config(
        self,
        provider: str | None = None,
        model: str | None = None,
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        ollama_base_url: str | None = None,
    ) -> dict[str, Any]:
        if provider:
            self.provider = provider.lower().strip()
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
        return self.get_status()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len((text or "").split()) * 4 // 3)

    async def _call_gemini(
        self, prompt: str, system_prompt: str, model: str
    ) -> tuple[str, int, int]:
        if not self.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={self.gemini_api_key}"
        )
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.25, "maxOutputTokens": 1024},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned empty candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        usage = data.get("usageMetadata") or {}
        p_tok = int(usage.get("promptTokenCount") or self._estimate_tokens(prompt))
        c_tok = int(usage.get("candidatesTokenCount") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def _call_openai(
        self, prompt: str, system_prompt: str, model: str
    ) -> tuple[str, int, int]:
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        url = "https://api.openai.com/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {self.openai_api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.25},
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage") or {}
        p_tok = int(usage.get("prompt_tokens") or self._estimate_tokens(prompt))
        c_tok = int(usage.get("completion_tokens") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def _call_anthropic(
        self, prompt: str, system_prompt: str, model: str
    ) -> tuple[str, int, int]:
        if not self.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            body["system"] = system_prompt
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        content = data.get("content") or []
        text = "".join(c.get("text", "") for c in content).strip()
        usage = data.get("usage") or {}
        p_tok = int(usage.get("input_tokens") or self._estimate_tokens(prompt))
        c_tok = int(usage.get("output_tokens") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def _call_ollama(
        self, prompt: str, system_prompt: str, model: str
    ) -> tuple[str, int, int]:
        url = f"{self.ollama_base_url}/api/generate"
        full_prompt = f"{system_prompt}\n\n{prompt}".strip() if system_prompt else prompt
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url, json={"model": model, "prompt": full_prompt, "stream": False}
            )
            resp.raise_for_status()
            data = resp.json()
        text = (data.get("response") or "").strip()
        if not text:
            raise RuntimeError("Ollama returned empty response")
        p_tok = int(data.get("prompt_eval_count") or self._estimate_tokens(full_prompt))
        c_tok = int(data.get("eval_count") or self._estimate_tokens(text))
        return text, p_tok, c_tok

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        fallback_text: str = "",
    ) -> LLMResult:
        """Invoke primary configured provider, falling back to secondary providers or simulation."""
        start_time = time.time()

        attempts: list[tuple[str, str]] = [(self.provider, self.model)]
        if self.gemini_api_key and self.provider != "gemini":
            attempts.append(("gemini", "gemini-2.5-flash"))
        if self.openai_api_key and self.provider != "openai":
            attempts.append(("openai", "gpt-4o-mini"))
        if self.anthropic_api_key and self.provider != "anthropic":
            attempts.append(("anthropic", "claude-3-5-sonnet-20241022"))

        for prov, mod in attempts:
            try:
                if prov == "gemini":
                    text, p_tok, c_tok = await self._call_gemini(
                        prompt, system_prompt, mod
                    )
                elif prov == "openai":
                    text, p_tok, c_tok = await self._call_openai(
                        prompt, system_prompt, mod
                    )
                elif prov == "anthropic":
                    text, p_tok, c_tok = await self._call_anthropic(
                        prompt, system_prompt, mod
                    )
                elif prov == "ollama":
                    text, p_tok, c_tok = await self._call_ollama(
                        prompt, system_prompt, mod
                    )
                else:
                    continue

                latency_ms = round((time.time() - start_time) * 1000.0, 2)
                total_tokens = p_tok + c_tok
                cost = calculate_cost_usd(mod, p_tok, c_tok)
                return LLMResult(
                    text=text,
                    provider=prov,
                    model=mod,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    estimated_cost_usd=cost,
                    is_fallback=False,
                )
            except Exception:
                continue

        # Deterministic Legal Simulation Fallback (zero disruption offline mode)
        latency_ms = round((time.time() - start_time) * 1000.0, 2)
        sim_text = fallback_text.strip() or (
            "Enterprise legal review completed via deterministic simulation engine."
        )
        p_tok = self._estimate_tokens(f"{system_prompt} {prompt}")
        c_tok = self._estimate_tokens(sim_text)
        total_tokens = p_tok + c_tok
        cost = calculate_cost_usd("contractmind-legal-sim", p_tok, c_tok)
        return LLMResult(
            text=sim_text,
            provider="simulation",
            model="contractmind-legal-sim",
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=total_tokens,
            latency_ms=max(1.0, latency_ms),
            estimated_cost_usd=cost,
            is_fallback=True,
        )


llm_gateway = LLMGateway()
