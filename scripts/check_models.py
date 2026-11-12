"""Check configured Gemini and Gemma models against Google's live list of available models."""

import sys
from pathlib import Path

import httpx

# Add apps/backend to sys.path so backend imports resolve
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps" / "backend"))

from app.config import settings


def main() -> int:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.")
        return 1

    configured_models = settings.TEXT_MODELS
    print(f"Checking {len(configured_models)} configured Gemini and Gemma models...")

    url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"
    headers = {"x-goog-api-key": api_key}

    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            print(
                f"ERROR: API request failed with status {resp.status_code}: {resp.text}"
            )
            return 1
        data = resp.json()

    available_models: set[str] = set()
    for item in data.get("models", []):
        methods = item.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            name = item.get("name", "").removeprefix("models/")
            if name:
                available_models.add(name)

    missing_count = 0
    print("\n--- Configured Models ---")
    for model in configured_models:
        if model in available_models:
            print(f"[OK]      {model}")
        else:
            print(f"[MISSING] {model}")
            missing_count += 1

    unconfigured = sorted(
        m
        for m in available_models
        if m not in configured_models
        and ("gemini" in m.lower() or "gemma" in m.lower())
    )
    if unconfigured:
        print(
            f"\n--- Available Gemini and Gemma Models Not Configured ({len(unconfigured)}) ---"
        )
        for m in unconfigured:
            print(f"  {m}")

    if missing_count > 0:
        print(f"\nFailure: {missing_count} configured model(s) are MISSING.")
        return 1

    print("\nSuccess: All configured models are available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
