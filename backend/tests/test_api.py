from fastapi.testclient import TestClient


def create_run(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/test-runs",
        json={"source_drive": "C:\\TestLogs", "run_status": "completed"},
    )
    assert response.status_code == 201
    return response.json()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_test_run_crud_and_cascade(client: TestClient) -> None:
    run = create_run(client)
    result = client.post(
        "/api/v1/test-results",
        json={
            "run_id": run["id"],
            "test_name": "checkout.test_payment",
            "status": "pass",
            "execution_time": 1.42,
            "flakiness_score": 0.1,
        },
    )
    assert result.status_code == 201

    insight = client.post(
        "/api/v1/ai-test-insights",
        json={
            "run_id": run["id"],
            "degradation_warning": None,
            "proactive_fixes": [{"action": "Monitor payment latency"}],
            "summary": "Stable execution",
        },
    )
    assert insight.status_code == 201

    updated = client.patch(
        f"/api/v1/test-runs/{run['id']}",
        json={"run_status": "archived"},
    )
    assert updated.status_code == 200
    assert updated.json()["run_status"] == "archived"

    deleted = client.delete(f"/api/v1/test-runs/{run['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/test-results/{result.json()['id']}").status_code == 404
    assert client.get(
        f"/api/v1/ai-test-insights/{insight.json()['id']}"
    ).status_code == 404


def test_child_resources_require_existing_run(client: TestClient) -> None:
    response = client.post(
        "/api/v1/test-results",
        json={
            "run_id": 999,
            "test_name": "missing.run",
            "status": "fail",
            "execution_time": 0,
            "flakiness_score": 0,
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Test run not found"


def test_commit_impact_crud_and_uniqueness(client: TestClient) -> None:
    payload = {
        "commit_hash": "abc1234567890",
        "branch": "main",
        "summary": "Payment validation changed",
        "regression_risk_level": "high",
        "suggested_automated_tests": ["checkout.test_payment"],
        "suggested_manual_tests": [
            {"title": "Declined card", "steps": ["Submit a declined card"]}
        ],
    }
    created = client.post("/api/v1/commit-impacts", json=payload)
    assert created.status_code == 201
    impact_id = created.json()["id"]

    duplicate = client.post("/api/v1/commit-impacts", json=payload)
    assert duplicate.status_code == 409

    fetched = client.get(f"/api/v1/commit-impacts/{impact_id}")
    assert fetched.status_code == 200
    assert fetched.json()["suggested_automated_tests"] == [
        "checkout.test_payment"
    ]

    deleted = client.delete(f"/api/v1/commit-impacts/{impact_id}")
    assert deleted.status_code == 204


def test_result_validation(client: TestClient) -> None:
    run = create_run(client)
    response = client.post(
        "/api/v1/test-results",
        json={
            "run_id": run["id"],
            "test_name": "invalid.score",
            "status": "unknown",
            "execution_time": -1,
            "flakiness_score": 1.5,
        },
    )
    assert response.status_code == 422

    null_update = client.patch(
        f"/api/v1/test-runs/{run['id']}",
        json={"run_status": None},
    )
    assert null_update.status_code == 422


def test_resource_lists_support_frontend_filters(client: TestClient) -> None:
    first_run = create_run(client)
    second_run = create_run(client)
    for run, test_name in (
        (first_run, "checkout.test_payment"),
        (second_run, "profile.test_update"),
    ):
        response = client.post(
            "/api/v1/test-results",
            json={
                "run_id": run["id"],
                "test_name": test_name,
                "status": "pass",
                "execution_time": 0.5,
                "flakiness_score": 0,
            },
        )
        assert response.status_code == 201

    filtered = client.get(
        "/api/v1/test-results",
        params={"run_id": second_run["id"]},
    )

    assert filtered.status_code == 200
    assert [item["test_name"] for item in filtered.json()] == [
        "profile.test_update"
    ]
    runs = client.get("/api/v1/test-runs").json()
    assert runs[0]["id"] == second_run["id"]


def test_cors_allows_configured_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/test-runs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:3000"
    )
