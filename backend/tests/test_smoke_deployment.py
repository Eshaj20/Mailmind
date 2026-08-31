from scripts.smoke_deployment import _url


def test_smoke_url_join_handles_slashes():
    assert _url("https://api.example.com/api/v1", "/health") == "https://api.example.com/api/v1/health"
    assert _url("https://api.example.com/api/v1/", "healthz") == "https://api.example.com/api/v1/healthz"