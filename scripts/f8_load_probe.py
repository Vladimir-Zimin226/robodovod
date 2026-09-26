"""F8 read-only HTTP profile; requires a disposable local backend."""

from __future__ import annotations

import json
import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("F8_BASE_URL", "http://127.0.0.1:8008")
target = urlparse(BASE)
assert target.hostname == "127.0.0.1" and target.port in {8008, 8009}
PATHS = ("/api/catalog/models?limit=20", "/api/catalog/defaults", "/api/projects")
USERS = 50
ROUNDS = int(os.getenv("F8_ROUNDS", "3"))
CONCURRENCY = int(os.getenv("F8_CONCURRENCY", "10"))


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * pct))]


def prepare_user(index: int, batch: str) -> requests.Session:
    session = requests.Session()
    email = f"f8-load-{batch}-{index}@example.invalid"
    password = "f8-disposable-long-passphrase"
    if os.getenv("F8_REUSE_BATCH"):
        logged = session.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=60)
        assert logged.status_code == 200, (email, logged.status_code)
        return session
    registered = session.post(f"{BASE}/api/auth/register", json={"email": email, "password": password,
                                                                     "name": f"Load {index}"}, timeout=60)
    assert registered.status_code == 201, (email, registered.status_code, registered.text[:200])
    csrf = registered.json()["csrf_token"]
    created = session.post(f"{BASE}/api/projects", headers={"X-CSRF-Token": csrf},
                           json={"name": f"F8 load {index}"}, timeout=60)
    assert created.status_code == 201, (email, created.status_code, created.text[:200])
    return session


def user(session: requests.Session) -> list[dict]:
    measurements = []
    for _ in range(ROUNDS):
        for path in PATHS:
            start = time.perf_counter()
            response = session.get(BASE + path, timeout=20)
            elapsed = (time.perf_counter() - start) * 1000
            measurements.append({"path": path.split("?")[0], "status": response.status_code,
                                 "latency_ms": round(elapsed, 2)})
            assert response.status_code == 200, (path, response.status_code)
    return measurements


def main() -> None:
    batch = os.getenv("F8_REUSE_BATCH") or uuid.uuid4().hex[:8]
    sessions = [prepare_user(i, batch) for i in range(USERS)]
    start = time.perf_counter()
    all_measurements = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for future in as_completed(pool.submit(user, session) for session in sessions):
            all_measurements.extend(future.result())
    summary = {}
    for path in sorted({item["path"] for item in all_measurements}):
        values = [item["latency_ms"] for item in all_measurements if item["path"] == path]
        summary[path] = {"count": len(values), "median_ms": round(statistics.median(values), 2),
                         "p95_ms": percentile(values, .95), "max_ms": max(values)}
    report = {"mode": "local disposable PostgreSQL; 50 registered users, one project each",
              "configuration": f"Windows local PostgreSQL 17 / FastAPI uvicorn at {target.port} / no YC",
              "user_count": USERS, "rounds": ROUNDS, "http_request_count": len(all_measurements),
              "concurrency": CONCURRENCY,
              "registration_and_project_creation_excluded_from_timed_window": True,
              "reused_prepared_users": bool(os.getenv("F8_REUSE_BATCH")),
              "elapsed_s": round(time.perf_counter() - start, 2), "paths": summary,
              "target_p95_ms": 1000, "target_met": all(item["p95_ms"] <= 1000 for item in summary.values())}
    output = ROOT / "docs" / "delivery" / "f8" / "load-probe.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
