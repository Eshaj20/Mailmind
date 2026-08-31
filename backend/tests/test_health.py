def test_health_endpoints_are_deployable(client):
    for path in ("/api/v1/healthz", "/api/v1/health"):
        response = client.get(path)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}