"""Multi-Provider LLM Gateway with automatic fallback and deterministic legal simulator."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.models.audit import calculate_token_cost

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]


@dataclass
class LLMResult:
    text: str
    model_name: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    used_fallback: bool = False


def _estimate_tokens(text: str) -> int:
    return max(1, len((text or "").split()) * 4 // 3)


class MultiProviderLLMGateway:
    """Routes completion calls across Gemini, Ollama, OpenAI, Anthropic, or Simulator."""

    def __init__(self) -> None:
        self.default_provider: str = settings.DEFAULT_LLM_PROVIDER or "simulator"
        self.gemini_api_key: str = settings.GEMINI_API_KEY
        self.gemini_model: str = settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        self.openai_api_key: str = settings.OPENAI_API_KEY
        self.openai_model: str = settings.OPENAI_MODEL or "gpt-4o"
        self.anthropic_api_key: str = settings.ANTHROPIC_API_KEY
        self.anthropic_model: str = settings.ANTHROPIC_MODEL or "claude-3-5-sonnet"
        self.ollama_base_url: str = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.ollama_model: str = settings.OLLAMA_MODEL or "qwen3.5:4b"

    def update_config(self, payload: Dict[str, Any]) -> None:
        """Update runtime LLM credentials and default provider without persisting secrets to disk."""
        if payload.get("default_provider"):
            self.default_provider = str(payload["default_provider"]).strip().lower()
        if payload.get("gemini_api_key") is not None:
            self.gemini_api_key = str(payload["gemini_api_key"]).strip()
        if payload.get("gemini_model"):
            self.gemini_model = str(payload["gemini_model"]).strip()
        if payload.get("openai_api_key") is not None:
            self.openai_api_key = str(payload["openai_api_key"]).strip()
        if payload.get("openai_model"):
            self.openai_model = str(payload["openai_model"]).strip()
        if payload.get("anthropic_api_key") is not None:
            self.anthropic_api_key = str(payload["anthropic_api_key"]).strip()
        if payload.get("anthropic_model"):
            self.anthropic_model = str(payload["anthropic_model"]).strip()
        if payload.get("ollama_base_url"):
            self.ollama_base_url = str(payload["ollama_base_url"]).strip().rstrip("/")
        if payload.get("ollama_model"):
            self.ollama_model = str(payload["ollama_model"]).strip()

    def get_status(self) -> Dict[str, Any]:
        """Return safe provider status without exposing full secret keys."""
        def _mask(key: str) -> str:
            if not key:
                return ""
            if len(key) <= 8:
                return "****"
            return f"{key[:4]}...{key[-4:]}"

        return {
            "default_provider": self.default_provider,
            "providers": {
                "gemini": {
                    "configured": bool(self.gemini_api_key),
                    "model": self.gemini_model,
                    "key_preview": _mask(self.gemini_api_key),
                },
                "openai": {
                    "configured": bool(self.openai_api_key),
                    "model": self.openai_model,
                    "key_preview": _mask(self.openai_api_key),
                },
                "anthropic": {
                    "configured": bool(self.anthropic_api_key),
                    "model": self.anthropic_model,
                    "key_preview": _mask(self.anthropic_api_key),
                },
                "ollama": {
                    "configured": bool(self.ollama_base_url),
                    "base_url": self.ollama_base_url,
                    "model": self.ollama_model,
                },
                "simulator": {
                    "configured": True,
                    "model": "deterministic-simulator",
                },
            },
        }

    async def _call_gemini(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        if not self.gemini_api_key or genai is None:
            return None
        genai.configure(api_key=self.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=self.gemini_model,
            system_instruction=system_instruction or None,
        )
        response = await model.generate_content_async(prompt)
        text = getattr(response, "text", "") or ""
        usage = getattr(response, "usage_metadata", None)
        p_tok = int(getattr(usage, "prompt_token_count", 0) or _estimate_tokens(system_instruction + prompt))
        c_tok = int(getattr(usage, "candidates_token_count", 0) or _estimate_tokens(text))
        return {"text": text.strip(), "model": self.gemini_model, "prompt_tokens": p_tok, "completion_tokens": c_tok}

    async def _call_openai(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        if not self.openai_api_key:
            return None
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_api_key}"},
                json={
                    "model": self.openai_model,
                    "messages": [
                        {"role": "system", "content": system_instruction or "You are an enterprise legal AI."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return {
                "text": text.strip(),
                "model": self.openai_model,
                "prompt_tokens": int(usage.get("prompt_tokens", _estimate_tokens(prompt))),
                "completion_tokens": int(usage.get("completion_tokens", _estimate_tokens(text))),
            }

    async def _call_anthropic(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        if not self.anthropic_api_key:
            return None
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.anthropic_model,
                    "max_tokens": 1024,
                    "system": system_instruction or "You are an enterprise legal AI.",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            usage = data.get("usage", {})
            return {
                "text": text.strip(),
                "model": self.anthropic_model,
                "prompt_tokens": int(usage.get("input_tokens", _estimate_tokens(prompt))),
                "completion_tokens": int(usage.get("output_tokens", _estimate_tokens(text))),
            }

    async def _call_ollama(self, prompt: str, system_instruction: str) -> Optional[Dict[str, Any]]:
        if not self.ollama_base_url:
            return None
        full_prompt = f"{system_instruction}\n\n{prompt}".strip() if system_instruction else prompt
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{self.ollama_base_url}/api/generate",
                json={"model": self.ollama_model, "prompt": full_prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "")
            return {
                "text": text.strip(),
                "model": self.ollama_model,
                "prompt_tokens": int(data.get("prompt_eval_count", _estimate_tokens(full_prompt))),
                "completion_tokens": int(data.get("eval_count", _estimate_tokens(text))),
            }

    def _provider_chain(self) -> List[str]:
        preferred = (self.default_provider or "simulator").lower()
        order = [preferred]
        for fallback in ["gemini", "openai", "anthropic", "ollama"]:
            if fallback not in order and preferred != "simulator":
                order.append(fallback)
        return order

    async def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        fallback_text: str = "",
    ) -> LLMResult:
        """Invoke the configured LLM provider with automatic fallback to deterministic template."""
        start = time.time()
        chain = self._provider_chain()

        for idx, provider in enumerate(chain):
            if provider == "simulator":
                break
            try:
                raw: Optional[Dict[str, Any]] = None
                if provider == "gemini":
                    raw = await self._call_gemini(prompt, system_instruction)
                elif provider == "openai":
                    raw = await self._call_openai(prompt, system_instruction)
                elif provider == "anthropic":
                    raw = await self._call_anthropic(prompt, system_instruction)
                elif provider == "ollama":
                    raw = await self._call_ollama(prompt, system_instruction)

                if raw and raw.get("text"):
                    latency_ms = round((time.time() - start) * 1000.0, 2)
                    p_tok = raw["prompt_tokens"]
                    c_tok = raw["completion_tokens"]
                    model_name = raw["model"]
                    return LLMResult(
                        text=raw["text"],
                        model_name=model_name,
                        provider=provider,
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        total_tokens=p_tok + c_tok,
                        latency_ms=latency_ms,
                        estimated_cost_usd=calculate_token_cost(model_name, p_tok, c_tok),
                        used_fallback=idx > 0,
                    )
            except Exception:
                continue

        # Deterministic legal simulation fallback
        sim_text = fallback_text.strip() or "Balanced commercial clause alignment applied per enterprise playbook."
        latency_ms = round((time.time() - start) * 1000.0, 2)
        p_tok = _estimate_tokens(system_instruction + " " + prompt)
        c_tok = _estimate_tokens(sim_text)
        return LLMResult(
            text=sim_text,
            model_name="deterministic-simulator",
            provider="simulator",
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=latency_ms,
            estimated_cost_usd=0.0,
            used_fallback=(self.default_provider != "simulator"),
        )


llm_gateway = MultiProviderLLMGateway()
