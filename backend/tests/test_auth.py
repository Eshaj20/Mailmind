def test_signup_login_and_me(client):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "esha@example.com", "password": "supersecret", "full_name": "Esha"},
    )
    assert signup.status_code == 201
    assert signup.json()["email"] == "esha@example.com"

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "esha@example.com", "password": "supersecret"},
    )
    assert login.status_code == 200

    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == "Esha"
