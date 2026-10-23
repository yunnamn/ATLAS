import threading
import time

from atlas.research.demo import DEMO_OBJECTIVE, DemoProvider


def wait_terminal(client, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/research/runs/{run_id}")
        assert response.status_code == 200
        if response.json()["status"] not in ("pending", "running"):
            return response.json()
        time.sleep(0.01)
    raise AssertionError("Local fixture run did not finish within five seconds")


def test_nonblocking_demo_api_persists_plan_progress_evidence_and_report(client) -> None:
    response = client.post("/api/research/runs", json={"objective": DEMO_OBJECTIVE})
    assert response.status_code == 202
    run_id = response.json()["id"]
    state = wait_terminal(client, run_id)
    assert state["status"] == "completed" and state["mode"] == "demo"
    assert len(state["plans"]) == 2
    assert [s["sequence"] for s in state["steps"]] == list(range(1, len(state["steps"]) + 1))
    assert all(s["checkpoint"]["run_id"] == run_id for s in state["steps"])
    report = client.get(f"/api/research/runs/{run_id}/report").json()
    assert report["outcome"] == "complete" and report["synthetic"]
    evidence = client.get(f"/api/research/runs/{run_id}/evidence").json()
    assert len(evidence["documents"]) == 2 and evidence["claims"]
    source = client.get(f"/api/research/runs/{run_id}/documents/{evidence['documents'][0]['id']}")
    assert source.status_code == 200 and "SYNTHETIC" in source.json()["text"]
    assert client.get("/api/research/runs").json()[0]["id"] == run_id
    assert client.get(f"/api/research/runs/{run_id}").json()["plans"] == state["plans"]
    assert client.get(f"/api/research/runs/{run_id}/documents/not-attached").status_code == 404
    assert (
        client.get("/api/opportunities").json()["total"] == 0
    )  # No silent promotion to reviewed records.


def test_insufficient_evidence_api_preserves_an_unknown(client) -> None:
    created = client.post(
        "/api/research/runs", json={"objective": DEMO_OBJECTIVE, "demo_scenario": "insufficient"}
    )
    run_id = created.json()["id"]
    assert wait_terminal(client, run_id)["outcome"] == "partial"
    report = client.get(f"/api/research/runs/{run_id}/report").json()
    assert report["unanswered_questions"][0]["field"] == "proof_of_funds"


def test_cancellation_api_interrupts_active_work_and_retains_partial_report(
    client, monkeypatch
) -> None:
    started = threading.Event()
    original = DemoProvider.generate

    def slow(self, output, task, payload, budget):
        if task == "PLAN":
            started.set()
            while True:
                budget.check()
                time.sleep(0.01)
        return original(self, output, task, payload, budget)

    monkeypatch.setattr(DemoProvider, "generate", slow)
    created = client.post("/api/research/runs", json={"objective": DEMO_OBJECTIVE})
    run_id = created.json()["id"]
    assert started.wait(2)
    assert client.get(f"/api/research/runs/{run_id}/report").status_code == 409
    assert client.post(f"/api/research/runs/{run_id}/cancel").status_code == 202
    final = wait_terminal(client, run_id)
    assert final["status"] == "cancelled"
    assert client.get(f"/api/research/runs/{run_id}/report").json()["outcome"] == "partial"
    assert client.post(f"/api/research/runs/{run_id}/cancel").status_code == 202


def test_live_mode_cannot_activate_a_model_implicitly_and_demo_never_fetches_custom_urls(
    client,
) -> None:
    assert client.get("/api/research/capabilities").json()["live_ready"] is False
    assert (
        client.post(
            "/api/research/runs", json={"objective": DEMO_OBJECTIVE, "mode": "live"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/research/runs",
            json={"objective": DEMO_OBJECTIVE, "mode": "live", "allow_model_requests": True},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/research/runs",
            json={"objective": DEMO_OBJECTIVE, "seed_urls": ["https://example.edu/"]},
        ).status_code
        == 422
    )
    assert client.get("/api/research/runs/missing").status_code == 404
    assert client.post("/api/research/runs/missing/cancel").status_code == 404
