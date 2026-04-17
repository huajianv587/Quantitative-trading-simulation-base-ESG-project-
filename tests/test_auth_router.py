from fastapi.testclient import TestClient

import gateway.main as main_module


def test_auth_register_login_reset_verify_roundtrip():
    client = TestClient(main_module.app)
    email = "sqlite-auth-roundtrip@example.com"
    password = "Start123!"
    new_password = "Reset456!"

    register = client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "SQLite User"},
    )
    assert register.status_code in {200, 409}
    if register.status_code == 409:
        login_existing = client.post("/auth/login", json={"email": email, "password": password})
        if login_existing.status_code == 401:
            login_existing = client.post("/auth/login", json={"email": email, "password": new_password})
            assert login_existing.status_code == 200
            token = login_existing.json()["token"]
        else:
            token = login_existing.json()["token"]
    else:
        token = register.json()["token"]

    verify = client.get("/auth/verify", params={"token": token})
    assert verify.status_code == 200
    assert verify.json()["user"]["email"] == email

    reset_request = client.post("/auth/reset-password/request", json={"email": email})
    assert reset_request.status_code == 200
    reset_token = reset_request.json().get("_dev_token")
    assert reset_token

    reset_confirm = client.post(
        "/auth/reset-password/confirm",
        json={"token": reset_token, "new_password": new_password},
    )
    assert reset_confirm.status_code == 200

    login_after = client.post("/auth/login", json={"email": email, "password": new_password})
    assert login_after.status_code == 200
    assert login_after.json()["user"]["email"] == email


def test_auth_status_uses_sqlite_repository():
    client = TestClient(main_module.app)

    response = client.get("/auth/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "sqlite"
    assert payload["db_path"].endswith("auth.sqlite3")
