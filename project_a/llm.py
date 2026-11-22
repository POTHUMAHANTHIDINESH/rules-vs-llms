"""Thin Gemini REST client (stdlib only) + a FakeLLM for plumbing tests.

Env: GEMINI_API_KEY (required for real runs), GEMINI_MODEL (default gemini-2.5-flash),
GEMINI_RPM (default 10, free-tier friendly), GEMINI_PRICE_IN / GEMINI_PRICE_OUT (USD per 1M tokens;
defaults are the public paid-tier list prices for gemini-2.5-flash at the time of writing - VERIFY and override).
"""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

PRICE_IN = float(os.environ.get("GEMINI_PRICE_IN", "0.30"))
PRICE_OUT = float(os.environ.get("GEMINI_PRICE_OUT", "2.50"))


@dataclass
class LLMResult:
    text: str
    in_tokens: int
    out_tokens: int
    latency_s: float

    @property
    def cost_usd(self) -> float:
        return (self.in_tokens * PRICE_IN + self.out_tokens * PRICE_OUT) / 1e6


class LLMUnavailable(RuntimeError):
    pass


class GeminiClient:
    _last_call = 0.0

    def __init__(self, model: str = None, api_key: str = None):
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.key = api_key or os.environ.get("GEMINI_API_KEY")
        self.min_gap = 60.0 / float(os.environ.get("GEMINI_RPM", "10"))
        if not self.key:
            raise LLMUnavailable("GEMINI_API_KEY not set")

    def generate(self, prompt: str, system: str = None, json_mode: bool = True,
                 temperature: float = 0.0, retries: int = 5) -> LLMResult:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
               f"?key={self.key}")
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        data = json.dumps(body).encode()
        for attempt in range(retries):
            wait = self.min_gap - (time.time() - GeminiClient._last_call)
            if wait > 0:
                time.sleep(wait)
            t0 = time.time()
            GeminiClient._last_call = t0
            try:
                req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    out = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503) and attempt < retries - 1:
                    time.sleep(min(60, 2 ** attempt * 5))
                    continue
                raise LLMUnavailable(f"HTTP {e.code}: {e.read()[:200]!r}")
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMUnavailable(str(e))
        lat = time.time() - t0
        try:
            text = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise LLMUnavailable(f"empty/blocked response: {str(out)[:200]}")
        u = out.get("usageMetadata", {})
        return LLMResult(text, u.get("promptTokenCount", 0),
                         u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0), lat)


class FakeLLM:
    """Returns canned text. ONLY for unit-testing plumbing; never used for reported measurements."""

    def __init__(self, responder):
        self.responder = responder

    def generate(self, prompt, system=None, json_mode=True, temperature=0.0, retries=0):
        return LLMResult(self.responder(prompt), len(prompt) // 4, 100, 0.0)


def get_client_or_none():
    try:
        return GeminiClient()
    except LLMUnavailable:
        return None
