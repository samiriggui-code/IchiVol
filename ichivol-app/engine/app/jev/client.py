"""Client HTTP JEV — observation uniquement."""
import os
import httpx

def evaluate(state: str, questions: dict) -> dict:
    url = os.getenv("JEV_URL", "http://jevos-v4:8017").rstrip("/")
    key = os.getenv("JEV_API_KEY", "")
    if not key:
        return {"ok": False, "error": "jev_key_missing"}
    payload = {"model": "jev-latest", "state": state, "questions": questions}
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url + "/v1/systemone", json=payload, headers={"Authorization": "Bearer " + key})
            response.raise_for_status()
            return {"ok": True, "result": response.json()}
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "error": type(exc).__name__}
