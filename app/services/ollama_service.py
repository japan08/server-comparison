import json
import re
from typing import Any

import httpx

from app.core.config import get_settings


async def get_completion(prompt: str, model: str | None = None) -> str | None:
    """Get a single completion from Ollama. Returns None if Ollama is unreachable."""
    settings = get_settings()
    url = f"{settings.ollama_base_url}/api/generate"
    payload: dict[str, Any] = {
        "model": model or settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
    except (httpx.HTTPError, httpx.ConnectError, json.JSONDecodeError):
        return None


async def parse_query_to_params(query: str) -> dict[str, Any] | None:
    """
    Use Ollama to extract cpu, ram, budget, region from natural language.
    Returns dict with keys cpu (int), ram (float), budget (float), region (str), or None on failure.
    """
    prompt = f"""Extract from this user request for a cloud server the following and respond with ONLY a valid JSON object, no other text:
- cpu: integer, minimum vCPUs (default 2)
- ram: number, minimum RAM in GB (default 4)
- budget: number, maximum monthly budget in USD (default 50)
- region: string, continent or region name (default "Europe")

User request: {query}

JSON:"""
    text = await get_completion(prompt)
    if not text:
        return None
    text = text.strip()
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)
    try:
        data = json.loads(text)
        return {
            "cpu": int(data.get("cpu", 2)),
            "ram": float(data.get("ram", 4)),
            "budget": float(data.get("budget", 50)),
            "region": str(data.get("region", "Europe")).strip() or "Europe",
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def generate_explanation(recommendations: list[dict[str, Any]]) -> str | None:
    """Generate one short sentence explaining the recommendations. Returns None if Ollama fails."""
    if not recommendations:
        return None
    prompt = f"""In one short sentence, explain why these cloud instance options are a good fit. Be concise.

Options: {json.dumps(recommendations[:3], indent=0)}

Sentence:"""
    return await get_completion(prompt)
