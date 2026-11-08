"""
One swappable LLM client. Almost every provider exposes an OpenAI-compatible
chat endpoint, so the same code works for all of them. Change the model by
editing .env only; no code changes needed.

    LLM_PROVIDER=groq|gemini|openai|anthropic|ollama|custom
    LLM_API_KEY=...            (not needed for ollama)
    LLM_MODEL=...              (optional, overrides the provider default)
    LLM_BASE_URL=...           (required for custom)
"""

import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = {
    # free tiers: groq, gemini; local & free: ollama
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "anthropic": ("https://api.anthropic.com/v1/", "claude-sonnet-5-5"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
}


class LLMNotConfigured(RuntimeError):
    pass


def settings():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    base, model = PROVIDERS.get(provider, (None, None))
    base = os.getenv("LLM_BASE_URL") or base
    model = os.getenv("LLM_MODEL") or model
    key = os.getenv("LLM_API_KEY") or ("ollama" if provider == "ollama" else None)
    return provider, base, model, key


def is_configured():
    _, base, model, key = settings()
    return bool(base and model and key)


class RateLimited(RuntimeError):
    """Every configured model is rate-limited (free-tier quota used up)."""


LAST_MODEL_USED = {"name": None}


def chat(messages, temperature=0.2, max_tokens=4000, retries=None):
    """
    Rate limits: each model is tried `retries` times (env LLM_RETRIES, default 2), then the
    next model in LLM_FALLBACK_MODELS (comma-separated, same provider) is tried.
    """
    provider, base, model, key = settings()
    if not (base and model and key):
        raise LLMNotConfigured(
            "No LLM configured. Copy .env.example to .env and set LLM_PROVIDER and LLM_API_KEY."
        )
    import time

    from openai import OpenAI, RateLimitError

    # max_retries=0: the client's own hidden retries multiplied ours (minutes of waiting).
    client = OpenAI(base_url=base, api_key=key, max_retries=0, timeout=90)
    extra = {}
    # "Thinking" models (Gemini 2.5+/3.x, o-series) spend max_tokens on hidden reasoning
    # and can return an EMPTY answer. Set LLM_REASONING_EFFORT=low|none to control it.
    # Only sent when set, because some providers reject the parameter.
    if os.getenv("LLM_REASONING_EFFORT"):
        extra["reasoning_effort"] = os.getenv("LLM_REASONING_EFFORT")
    retries = retries or int(os.getenv("LLM_RETRIES", "2"))
    fallbacks = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]

    resp, used = None, None
    for candidate in [model] + [m for m in fallbacks if m != model]:
        for attempt in range(retries):
            try:
                resp = client.chat.completions.create(
                    model=candidate, messages=messages, temperature=temperature, max_tokens=max_tokens, **extra
                )
                used = candidate
                break
            except RateLimitError:  # free tiers: wait briefly, then move to the next model
                if attempt < retries - 1:
                    time.sleep(10 * (attempt + 1))
        if resp is not None:
            break
    if resp is None:
        raise RateLimited("All configured models are rate-limited (free-tier quota). Try again later "
                          "or add LLM_FALLBACK_MODELS.")
    LAST_MODEL_USED["name"] = f"{provider}:{used}"
    text = resp.choices[0].message.content or ""
    if not text.strip():
        raise RuntimeError(f"{used} returned an empty answer (finish_reason="
                           f"{resp.choices[0].finish_reason}); try LLM_REASONING_EFFORT=low or a higher max_tokens")
    return text


def chat_json(messages, **kw):
    """Ask for JSON and parse it robustly (models sometimes wrap it in ```json fences)."""
    raw = chat(messages, temperature=0, **kw)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"Model did not return JSON: {raw[:200]}")
    return json.loads(m.group(0))


def transcribe(audio_bytes, fmt="wav"):
    """
    Speech-to-text through the same chat model (Gemini and GPT-4o-class models accept audio).
    If the configured model doesn't accept audio, this raises and the UI says voice is unavailable.
    Swap-in alternative: Whisper via Groq's free tier (/audio/transcriptions).
    """
    import base64

    return chat([
        {"role": "system", "content": "Transcribe the speech exactly, in the language and script spoken "
                                      "(Hindi in Devanagari, English in English; Hinglish in Latin letters). "
                                      "Return ONLY the transcript, nothing else."},
        {"role": "user", "content": [
            {"type": "input_audio",
             "input_audio": {"data": base64.b64encode(audio_bytes).decode(), "format": fmt}},
        ]},
    ], temperature=0, max_tokens=2000).strip()


def model_name():
    """The configured primary model."""
    provider, _, model, _ = settings()
    return f"{provider}:{model}"


def last_model_used():
    """The model that actually answered the most recent call (may be a fallback)."""
    return LAST_MODEL_USED["name"] or model_name()
