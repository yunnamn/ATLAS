"""Opt-in live smoke check through the running local API. May incur provider costs."""

import argparse
import json
import time
from typing import Any

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-model-requests",
        action="store_true",
        help="Explicitly authorize calls/costs at your configured provider",
    )
    parser.add_argument("--objective", required=True)
    parser.add_argument("--seed", action="append", default=[])
    parser.add_argument("--domain", action="append", default=[])
    args = parser.parse_args()
    if not args.allow_model_requests:
        parser.error(
            "Live calls are disabled. Supply --allow-model-requests only for an approved provider."
        )
    with httpx.Client(
        base_url="http://127.0.0.1:8000", trust_env=False, timeout=10, follow_redirects=False
    ) as client:
        capabilities = client.get("/api/research/capabilities")
        capabilities.raise_for_status()
        if not capabilities.json()["live_ready"]:
            raise SystemExit(
                "No enabled model endpoint. Configure the backend; nothing was started."
            )
        created = client.post(
            "/api/research/runs",
            json={
                "objective": args.objective,
                "mode": "live",
                "allow_model_requests": True,
                "seed_urls": args.seed,
                "allowed_domains": args.domain,
                "limits": {"max_documents": 3, "max_model_requests": 10, "max_seconds": 120},
            },
        )
        if created.status_code != 202:
            raise SystemExit(
                "Live run was not accepted. Check source scope and backend configuration."
            )
        run_id = created.json()["id"]
        print(json.dumps({"run_id": run_id, "status": "submitted", "live": True}))
        deadline = time.monotonic() + 155
        while time.monotonic() < deadline:
            status = client.get(f"/api/research/runs/{run_id}")
            status.raise_for_status()
            state: dict[str, Any] = status.json()
            if state["status"] not in ("pending", "running"):
                report_response = client.get(f"/api/research/runs/{run_id}/report")
                report_response.raise_for_status()
                report = report_response.json()
                references = {e["id"] for e in report["evidence"]}
                citations_resolve = all(
                    c["evidence_id"] in references and c["scope_evidence_id"] in references
                    for c in report["findings"]
                )
                worked = (
                    state["status"] == "completed"
                    and bool(report["findings"])
                    and (state["stats"].get("model_http_requests", 0) > 0 and citations_resolve)
                )
                print(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "status": state["status"],
                            "outcome": state["outcome"],
                            "findings": len(report["findings"]),
                            "stats": state["stats"],
                            "citations_resolve": citations_resolve,
                            "smoke_passed": worked,
                        }
                    )
                )
                raise SystemExit(0 if worked else 1)
            time.sleep(1)
        client.post(f"/api/research/runs/{run_id}/cancel")
        raise SystemExit(
            "Live smoke deadline reached; cancellation requested. Inspect the partial report."
        )


if __name__ == "__main__":
    main()
