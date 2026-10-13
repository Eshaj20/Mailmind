# This is a test file for the authentication endpoints of the FastAPI application.
def test_signup_login_and_me(client):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "esha@example.com", "password": "supersecret", "full_name": "Esha"},
    )
    # Assert that the signup request was successful and returned the expected email
    assert signup.status_code == 201
    assert signup.json()["email"] == "esha@example.com"

# Test the login endpoint with the newly created user
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "esha@example.com", "password": "supersecret"},
    )
    # Assert that the login request was successful and returned an access token
    assert login.status_code == 200

# Test the /me endpoint to retrieve the current user's information
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    
    # Assert that the /me request was successful and returned the expected full name
    assert me.status_code == 200
    assert me.json()["full_name"] == "Esha"


def test_signup_is_restricted_when_beta_allowlist_is_configured(client, monkeypatch):
    from app.api.routes import auth

    monkeypatch.setattr(auth.settings, "beta_allowed_emails", "allowed@example.com")
    blocked = client.post(
        "/api/v1/auth/signup",
        json={"email": "blocked@example.com", "password": "supersecret"},
    )
    allowed = client.post(
        "/api/v1/auth/signup",
        json={"email": "allowed@example.com", "password": "supersecret"},
    )

    assert blocked.status_code == 403
    assert allowed.status_code == 201


def test_password_reset_changes_password_once(client, monkeypatch):
    from app.api.routes import auth
    from app.models.user import PasswordResetToken

    client.post(
        "/api/v1/auth/signup",
        json={"email": "reset@example.com", "password": "old-password", "full_name": "Reset User"},
    )
    sent_links: list[str] = []
    monkeypatch.setattr(auth, "password_reset_delivery_is_configured", lambda: True)
    monkeypatch.setattr(auth, "send_password_reset_email", lambda _email, link: sent_links.append(link))

    requested = client.post("/api/v1/auth/password-reset/request", json={"email": "reset@example.com"})
    assert requested.status_code == 200
    assert len(sent_links) == 1
    token = sent_links[0].split("token=", maxsplit=1)[1]

    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "password": "new-password"},
    )
    assert confirmed.status_code == 200
    assert client.post("/api/v1/auth/login", data={"username": "reset@example.com", "password": "new-password"}).status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "another-password"}).status_code == 400
    assert client.app.dependency_overrides
    assert PasswordResetToken
