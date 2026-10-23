from copy import deepcopy

from fastapi.testclient import TestClient


def create(client: TestClient, record: dict) -> dict:
    response = client.post("/api/opportunities", json=record)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_metadata(client: TestClient) -> None:
    assert client.get("/api/health").json()["llm"] == "disabled"
    assert "funding" in client.get("/api/metadata").json()["fact_labels"]


def test_create_detail_unknowns_and_duplicate(client: TestClient, record: dict) -> None:
    created = create(client, record)
    assert created["synthetic"] is True
    assert created["created_at"].endswith("+00:00")
    assert created["facts"]["travel"] == {
        "value": None,
        "state": "unknown",
        "source_id": None,
        "excerpt": None,
    }
    assert client.get(f"/api/opportunities/{created['id']}").json() == created
    assert client.post("/api/opportunities", json=record).status_code == 409
    assert client.get("/api/opportunities/9999").status_code == 404


def test_import_is_repeatable_and_filtering_works(client: TestClient) -> None:
    assert len(client.post("/api/imports/demo").json()["created"]) == 6
    second = client.post("/api/imports/demo").json()
    assert len(second["skipped"]) == 6 and second["created"] == []
    response = client.get("/api/opportunities", params={"q": "ROBOTICS"}).json()
    assert response["total"] == 1
    assert response["items"][0]["country"] == "Japan"
    assert client.get("/api/opportunities?country=Sweden&funding=partial").json()["total"] == 0
    assert client.get("/api/opportunities?funding=tuition_and_stipend").json()["total"] == 3
    assert client.get("/api/opportunities?limit=2&offset=2").json()["items"][0]["id"] == 3
    assert client.get("/api/opportunities?category=job").json()["total"] == 0
    assert client.get("/api/opportunities?review=true").json()["total"] == 6
    assert client.get("/api/opportunities?limit=0").status_code == 422


def test_invalid_batch_has_no_partial_writes(client: TestClient, record: dict) -> None:
    invalid = deepcopy(record)
    invalid["external_id"] = "another-record"
    invalid["facts"]["deadline"]["value"] = "tomorrow"
    assert client.post("/api/imports", json={"opportunities": [record, invalid]}).status_code == 422
    assert client.get("/api/opportunities").json()["total"] == 0
    assert client.post("/api/imports", json={"opportunities": [record, record]}).status_code == 422


def test_fact_review_preserves_history_and_rejects_stale_writes(
    client: TestClient, record: dict
) -> None:
    created = create(client, record)
    endpoint = f"/api/opportunities/{created['id']}/facts/deadline"
    body = {
        "fact": {
            "value": "2027-02-01",
            "state": "verified",
            "source_id": "demo-handbook",
            "excerpt": "Synthetic deadline corrected to 2027-02-01.",
        },
        "expected_revision": 1,
        "actor": "Test reviewer",
        "reason": "Corrected sample deadline",
    }
    response = client.put(endpoint, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert response.json()["facts"]["deadline"]["state"] == "verified"
    assert client.put(endpoint, json=body).status_code == 409
    history = client.get(f"/api/opportunities/{created['id']}/history").json()
    assert len(history) == 2
    assert history[0]["before"]["facts"]["deadline"]["value"] == "2027-01-15"
    assert history[0]["after"]["facts"]["deadline"]["value"] == "2027-02-01"
    client.post("/api/imports/demo")
    assert client.get(f"/api/opportunities/{created['id']}").json()["revision"] == 2


def test_reviews_require_provenance_and_valid_typed_values(
    client: TestClient, record: dict
) -> None:
    row = create(client, record)
    base = f"/api/opportunities/{row['id']}/facts/"
    body = {
        "fact": {"state": "verified", "value": "yes"},
        "actor": "Tester",
        "reason": "Evidence test",
        "expected_revision": 1,
    }
    assert client.put(base + "proof_of_funds", json=body).status_code == 422
    body["fact"].update(source_id="made-up", excerpt="An invented source")
    assert client.put(base + "proof_of_funds", json=body).status_code == 422
    body["fact"].update(source_id="demo-handbook", value="invalid date")
    assert client.put(base + "deadline", json=body).status_code == 422
    assert client.get(f"/api/opportunities/{row['id']}").json()["revision"] == 1


def test_profile_and_shortlist_persist_across_requests(client: TestClient, record: dict) -> None:
    row = create(client, record)
    profile = {
        "name": "Researcher",
        "nationality": "UZ",
        "education": "bachelor",
        "gpa": 3.7,
        "ielts": 7.5,
        "interests": ["Artificial intelligence"],
        "preferred_countries": ["Sweden"],
        "requires_full_funding": True,
    }
    assert client.put("/api/profile", json=profile).status_code == 200
    assert client.get("/api/profile").json() == profile
    match = client.get(f"/api/opportunities/{row['id']}/match").json()
    assert match["score"] == 100
    assert match["eligibility"] == "needs_review"
    assert "admissions probability" in match["disclaimer"]
    endpoint = f"/api/applications/{row['id']}"
    assert client.put(endpoint, json={"status": "saved"}).status_code == 200
    assert (
        client.put(
            endpoint,
            json={
                "status": "preparing",
                "notes": "Read sources",
                "missing_requirements": ["IELTS certificate"],
            },
        ).status_code
        == 200
    )
    apps = client.get("/api/applications").json()
    assert len(apps) == 1 and apps[0]["status"] == "preparing"
    assert apps[0]["opportunity"]["id"] == row["id"]
    assert apps[0]["missing_requirements"] == ["IELTS certificate"]
    assert client.delete(endpoint).status_code == 204
    assert client.get("/api/applications").json() == []
    assert client.put("/api/applications/9999", json={}).status_code == 404


def test_optional_categories_are_supported(client: TestClient, record: dict) -> None:
    record["category"] = "fellowship"
    create(client, record)
    assert client.get("/api/opportunities?category=fellowship").json()["total"] == 1
