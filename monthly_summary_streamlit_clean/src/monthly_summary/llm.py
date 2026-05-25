from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Sequence

import requests

from .text_utils import extract_json_object, sections_to_text, validate_sections


class LLMError(RuntimeError):
    pass


def _strip_base_url(url: str) -> str:
    return str(url or "http://localhost:11434").rstrip("/")


def _headers_for_key(api_key: str | None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def offline_structured_summary(output_kind: str) -> Dict[str, List[str]]:
    size_note = "bigger_summary" if output_kind == "bigger_summary" else "summary"
    return {
        "Executive Overview": [
            f"Offline mode generated a placeholder {size_note}; connect an LLM before using this report externally."
        ],
        "Key Completed Work": ["No major items identified."],
        "Ongoing / In Progress": ["No major items identified."],
        "Pending / Risks": ["No major items identified."],
    }


class LLMClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.llm_cfg = cfg.get("llm", {})
        self.provider = str(self.llm_cfg.get("provider", "ollama")).lower().strip()
        self.base_url = _strip_base_url(self.llm_cfg.get("base_url", "http://localhost:11434"))
        key_env = str(self.llm_cfg.get("api_key_env", "OLLAMA_API_KEY"))
        self.api_key = os.getenv(key_env, "")
        self.timeout = int(self.llm_cfg.get("request_timeout_seconds", 900))
        self.retry_count = int(self.llm_cfg.get("retry_count", 2))

    def model_for(self, output_kind: str) -> str:
        if output_kind == "bigger_summary":
            return str(self.llm_cfg.get("bigger_summary_model", self.llm_cfg.get("summary_model", "gpt-oss:120b-cloud")))
        return str(self.llm_cfg.get("summary_model", "gpt-oss:120b-cloud"))

    def candidate_models(self, output_kind: str) -> List[str]:
        first = self.model_for(output_kind)
        fallbacks = [str(m) for m in self.llm_cfg.get("fallback_models", [])]
        result: List[str] = []
        for model in [first] + fallbacks:
            if model and model not in result:
                result.append(model)
        return result

    def generate_sections(
        self,
        system_prompt: str,
        user_prompt: str,
        output_kind: str,
        max_tokens: int | None = None,
        required_sections: Sequence[str] | None = None,
    ) -> Dict[str, List[str]]:
        if self.provider == "offline":
            return validate_sections(offline_structured_summary(output_kind), required_sections or None)

        errors: List[str] = []
        for model in self.candidate_models(output_kind):
            for attempt in range(self.retry_count + 1):
                try:
                    raw = self._generate_once(model, system_prompt, user_prompt, max_tokens=max_tokens)
                    obj = extract_json_object(raw)
                    sections = validate_sections(obj, required_sections or None)
                    return sections
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{model} attempt {attempt + 1}: {exc}")
                    time.sleep(min(2 ** attempt, 8))
        raise LLMError("All LLM calls failed or returned invalid JSON:\n" + "\n".join(errors[-10:]))

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        output_kind: str,
        max_tokens: int | None = None,
        required_sections: Sequence[str] | None = None,
    ) -> str:
        sections = self.generate_sections(system_prompt, user_prompt, output_kind, max_tokens, required_sections)
        return sections_to_text(sections, required_sections or None)

    def _generate_once(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        if self.provider == "ollama":
            return self._call_ollama_native(model, system_prompt, user_prompt, max_tokens)
        if self.provider in {"ollama_openai", "openai_compatible"}:
            return self._call_openai_compatible(model, system_prompt, user_prompt, max_tokens)
        raise LLMError(f"Unsupported provider: {self.provider}")

    def _call_ollama_native(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        url = self.base_url
        if not url.endswith("/api"):
            url = url + "/api"
        endpoint = url + "/chat"
        options: Dict[str, Any] = {
            "temperature": float(self.llm_cfg.get("temperature", 0.05)),
            "top_p": float(self.llm_cfg.get("top_p", 0.9)),
            "num_ctx": int(self.llm_cfg.get("num_ctx", 128000)),
        }
        if max_tokens:
            options["num_predict"] = int(max_tokens)
        if self.llm_cfg.get("reasoning_effort"):
            options["reasoning_effort"] = str(self.llm_cfg.get("reasoning_effort"))
        # Some Ollama/OpenAI-compatible models respect this and return cleaner JSON.
        if bool(self.llm_cfg.get("json_mode", True)):
            options["format"] = "json"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": options,
        }
        response = requests.post(endpoint, headers=_headers_for_key(self.api_key), json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise LLMError(f"HTTP {response.status_code}: {response.text[:1000]}")
        data = response.json()
        return data.get("message", {}).get("content", "") or data.get("response", "")

    def _call_openai_compatible(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        url = self.base_url
        if url.endswith("/api"):
            url = url[:-4]
        if not url.endswith("/v1"):
            url = url + "/v1"
        endpoint = url + "/chat/completions"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(self.llm_cfg.get("temperature", 0.05)),
            "top_p": float(self.llm_cfg.get("top_p", 0.9)),
            "max_tokens": int(max_tokens or self.llm_cfg.get("summary_max_tokens", 2500)),
        }
        if bool(self.llm_cfg.get("json_mode", True)):
            payload["response_format"] = {"type": "json_object"}
        response = requests.post(endpoint, headers=_headers_for_key(self.api_key or "ollama"), json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise LLMError(f"HTTP {response.status_code}: {response.text[:1000]}")
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
