from atlas.research.demo import DEMO_OBJECTIVE
from tests.research.test_api import wait_terminal


def investigate(client, scenario="funding_gap"):
    run_id = client.post(
        "/api/research/runs",
        json={
            "objective": DEMO_OBJECTIVE,
            "demo_scenario": scenario,
        },
    ).json()["id"]
    wait_terminal(client, run_id)
    scope = client.get(f"/api/research/runs/{run_id}/report").json()["findings"][0]["scope"]
    return run_id, scope


def identity(external_id="research-demo-approved"):
    return {
        "external_id": external_id,
        "title": "Lumen AI Master's",
        "institution": "Lumen Institute",
        "country": "Synthetic demonstration",
        "summary": "Human-reviewed synthetic research demonstration.",
    }


def approval(**overrides):
    return {
        "expected_revision": 1,
        "selected_fields": ["tuition", "proof_of_funds"],
        "actor": "Test reviewer",
        "reason": "Compared exact source passages and conditions",
        "confirm_source_review": True,
        **overrides,
    }


def test_proposal_requires_explicit_approval_and_only_saves_selected_fields(client) -> None:
    run_id, scope = investigate(client)
    url = f"/api/research/runs/{run_id}/proposals"
    response = client.post(url, json={"scope": scope, "identity": identity()})
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert client.get("/api/opportunities").json()["total"] == 0
    assert proposal["status"] == "pending"
    assert {c["field"] for c in proposal["content"]["changes"]} >= {
        "tuition",
        "stipend",
        "language_requirements",
    }
    endpoint = url + f"/{proposal['id']}/approve"
    missing_consent = approval()
    del missing_consent["confirm_source_review"]
    assert client.post(endpoint, json=missing_consent).status_code == 422
    approved = client.post(endpoint, json=approval())
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    row = client.get("/api/opportunities").json()["items"][0]
    assert row["synthetic"]
    assert row["facts"]["tuition"]["state"] == "verified"
    assert row["facts"]["proof_of_funds"]["value"] == "no"
    assert row["facts"]["stipend"]["state"] == "unknown"
    assert row["facts"]["funding"]["state"] == "unknown"
    assert all(s["content_sha256"] and not s["official_asserted"] for s in row["sources"])
    changes = client.get(f"/api/opportunities/{row['id']}/history").json()
    assert changes[0]["actor"] == "Test reviewer" and proposal["id"] in changes[0]["reason"]
    assert client.post(endpoint, json=approval()).status_code == 409
    assert client.get("/api/opportunities").json()["total"] == 1
    assert client.get(url).json()[0]["approval"]["selected_fields"] == ["proof_of_funds", "tuition"]


def test_stale_update_is_atomic_and_preserves_confirmed_data(client, record) -> None:
    target = client.post("/api/opportunities", json=record).json()
    run_id, scope = investigate(client)
    url = f"/api/research/runs/{run_id}/proposals"
    request = {
        "scope": scope,
        "target_opportunity_id": target["id"],
        "expected_opportunity_revision": 1,
    }
    proposal = client.post(url, json=request).json()
    changed = client.put(
        f"/api/opportunities/{target['id']}/facts/deadline",
        json={
            "expected_revision": 1,
            "actor": "Existing reviewer",
            "reason": "Preserve this new correction",
            "fact": {"value": "2028-01-01", "state": "unverified"},
        },
    )
    assert changed.status_code == 200
    response = client.post(url + f"/{proposal['id']}/approve", json=approval())
    assert response.status_code == 409
    preserved = client.get(f"/api/opportunities/{target['id']}").json()
    assert preserved["revision"] == 2 and preserved["facts"]["deadline"]["value"] == "2028-01-01"
    assert client.get(url).json()[0]["status"] == "pending"
    fresh = client.post(url, json={**request, "expected_opportunity_revision": 2}).json()
    result = client.post(
        url + f"/{fresh['id']}/approve", json=approval(selected_fields=["stipend"])
    )
    assert result.status_code == 200, result.text
    row = client.get(f"/api/opportunities/{target['id']}").json()
    assert row["revision"] == 3 and row["facts"]["tuition"] == preserved["facts"]["tuition"]
    assert row["facts"]["deadline"]["value"] == "2028-01-01"
    assert row["facts"]["stipend"]["state"] == "verified"
    assert len(client.get(f"/api/opportunities/{target['id']}/history").json()) == 3


def test_synthetic_research_cannot_modify_a_real_record(client, record) -> None:
    record["synthetic"] = False
    target = client.post("/api/opportunities", json=record).json()
    run_id, scope = investigate(client)
    response = client.post(
        f"/api/research/runs/{run_id}/proposals",
        json={
            "scope": scope,
            "target_opportunity_id": target["id"],
            "expected_opportunity_revision": 1,
        },
    )
    assert response.status_code == 409 and "Synthetic" in response.text
    assert client.get(f"/api/opportunities/{target['id']}").json()["revision"] == 1


def test_conflicting_fields_and_duplicate_identity_cannot_overwrite_records(client, record) -> None:
    run_id, scope = investigate(client, "conflict")
    url = f"/api/research/runs/{run_id}/proposals"
    proposal = client.post(url, json={"scope": scope, "identity": identity()}).json()
    assert {"tuition_funding", "deadline"} <= {c["field"] for c in proposal["content"]["blocked"]}
    response = client.post(
        url + f"/{proposal['id']}/approve", json=approval(selected_fields=["tuition"])
    )
    assert response.status_code == 422
    assert client.get("/api/opportunities").json()["total"] == 0
    client.post("/api/opportunities", json=record)
    duplicate = client.post(
        url, json={"scope": scope, "identity": identity(record["external_id"])}
    ).json()
    response = client.post(
        url + f"/{duplicate['id']}/approve", json=approval(selected_fields=["stipend"])
    )
    assert response.status_code == 409
    assert client.get("/api/opportunities").json()["total"] == 1
    assert client.get(url).json()[0]["status"] == "pending"


def test_proposals_cannot_cross_run_boundaries_or_accept_actions_in_data(client) -> None:
    first, scope = investigate(client)
    second, _ = investigate(client)
    url = f"/api/research/runs/{first}/proposals"
    assert (
        client.post(url, json={"scope": scope, "identity": identity(), "approve": True}).status_code
        == 422
    )
    proposal = client.post(url, json={"scope": scope, "identity": identity()}).json()
    assert (
        client.post(
            f"/api/research/runs/{second}/proposals/{proposal['id']}/approve", json=approval()
        ).status_code
        == 404
    )
