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
