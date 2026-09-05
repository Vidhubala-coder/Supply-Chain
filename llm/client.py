"""
llm/client.py
Robust Gemini API Wrapper with strict 15-second per-call timeout,
JSON extraction, and instant fallback handling.
"""

import os
import json
import re
import concurrent.futures
from typing import Dict, Any, Optional

DEFAULT_TIMEOUT_SECONDS = 15.0

def get_genai_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract clean JSON dictionary from text, handling markdown fences."""
    if not text:
        return None
    # Remove markdown fenced blocks if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback regex search for { ... }
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None

def _raw_generate(contents: str, system_instruction: str, model_name: str = "gemini-2.5-flash") -> Optional[str]:
    client = get_genai_client()
    if not client:
        return None
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        )
        return response.text
    except Exception as e:
        # Retry once with gemini-1.5-flash if 2.5 is unavailable
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=contents,
                config={
                    "system_instruction": system_instruction,
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            )
            return response.text
        except Exception:
            return None

def generate_json_with_timeout(
    prompt: str,
    system_instruction: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    model_name: str = "gemini-2.5-flash"
) -> Optional[Dict[str, Any]]:
    """
    Executes Gemini generation with an explicit per-call timeout.
    If call exceeds timeout or errors, returns None immediately so caller uses fallback.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_raw_generate, prompt, system_instruction, model_name)
        try:
            text_result = future.result(timeout=timeout)
            if text_result:
                return extract_json(text_result)
        except (concurrent.futures.TimeoutError, Exception):
            pass
    return None
