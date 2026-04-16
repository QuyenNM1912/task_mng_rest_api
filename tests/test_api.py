import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from app.main import app
from app.database import Base, get_db

# Set test environment variables
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def register_and_login(email="test@example.com", password="secret123", role="user"):
    client.post("/register", json={"email": email, "password": password, "role": role})
    res = client.post("/login", json={"email": email, "password": password})
    return res.json()["access_token"], res.json()["refresh_token"]


def register_admin_and_login(email="admin@example.com", password="admin123"):
    return register_and_login(email, password, "admin")


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth Tests ────────────────────────────────────────────────────────────────

def test_register_success():
    res = client.post("/register", json={"email": "a@b.com", "password": "pass123"})
    assert res.status_code == 201
    assert res.json()["email"] == "a@b.com"


def test_register_duplicate_email():
    client.post("/register", json={"email": "a@b.com", "password": "pass123"})
    res = client.post("/register", json={"email": "a@b.com", "password": "pass123"})
    assert res.status_code == 400


def test_login_success():
    client.post("/register", json={"email": "a@b.com", "password": "pass123"})
    res = client.post("/login", json={"email": "a@b.com", "password": "pass123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    client.post("/register", json={"email": "a@b.com", "password": "pass123"})
    res = client.post("/login", json={"email": "a@b.com", "password": "wrong"})
    assert res.status_code == 401


def test_get_me():
    token, _ = register_and_login()
    res = client.get("/me", headers=auth_header(token))
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


def test_get_me_unauthorized():
    res = client.get("/me")
    assert res.status_code == 403


def test_refresh_token():
    _, refresh_token = register_and_login()
    res = client.post("/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert "refresh_token" in res.json()


def test_refresh_token_invalid():
    res = client.post("/refresh", json={"refresh_token": "invalid"})
    assert res.status_code == 401


# ── Admin Tests ───────────────────────────────────────────────────────────────

def test_admin_update_user_role():
    # Create admin and user
    admin_token, _ = register_admin_and_login()
    user_res = client.post("/register", json={"email": "user@test.com", "password": "pass", "role": "user"})
    user_id = user_res.json()["id"]
    
    # Admin updates user role
    res = client.put(f"/admin/users/{user_id}/role", 
                     json={"role": "admin"}, 
                     headers=auth_header(admin_token))
    assert res.status_code == 200
    
    # Verify role changed
    user_token, _ = register_and_login("user@test.com", "pass")
    me_res = client.get("/me", headers=auth_header(user_token))
    assert me_res.json()["role"] == "admin"


def test_admin_get_all_tasks():
    # Create admin and some tasks
    admin_token, _ = register_admin_and_login()
    user_token, _ = register_and_login("user@test.com", "pass")
    client.post("/tasks", json={"title": "User task"}, headers=auth_header(user_token))
    
    res = client.get("/tasks/admin/tasks", headers=auth_header(admin_token))
    assert res.status_code == 200
    assert len(res.json()["tasks"]) >= 1


def test_admin_update_any_task():
    # Create user task
    user_token, _ = register_and_login()
    task_res = client.post("/tasks", json={"title": "Original"}, headers=auth_header(user_token))
    task_id = task_res.json()["id"]
    
    # Admin updates it
    admin_token, _ = register_admin_and_login()
    res = client.put(f"/tasks/admin/tasks/{task_id}", 
                     json={"title": "Updated by admin"}, 
                     headers=auth_header(admin_token))
    assert res.status_code == 200
    assert res.json()["title"] == "Updated by admin"


def test_admin_delete_any_task():
    # Create user task
    user_token, _ = register_and_login()
    task_res = client.post("/tasks", json={"title": "To delete"}, headers=auth_header(user_token))
    task_id = task_res.json()["id"]
    
    # Admin deletes it
    admin_token, _ = register_admin_and_login()
    res = client.delete(f"/tasks/admin/tasks/{task_id}", headers=auth_header(admin_token))
    assert res.status_code == 200


def test_user_cannot_access_admin_routes():
    user_token, _ = register_and_login()
    res = client.get("/tasks/admin/tasks", headers=auth_header(user_token))
    assert res.status_code == 403


# ── Task Tests ────────────────────────────────────────────────────────────────

def test_create_task():
    token, _ = register_and_login()
    res = client.post("/tasks", json={"title": "Buy milk"}, headers=auth_header(token))
    assert res.status_code == 201
    assert res.json()["title"] == "Buy milk"
    assert res.json()["status"] == "todo"


def test_get_tasks_paginated():
    token, _ = register_and_login()
    for i in range(5):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
    res = client.get("/tasks?page=1&limit=3", headers=auth_header(token))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert len(data["tasks"]) == 3


def test_update_task():
    token, _ = register_and_login()
    task_id = client.post("/tasks", json={"title": "Old"}, headers=auth_header(token)).json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "New", "status": "done"}, headers=auth_header(token))
    assert res.status_code == 200
    assert res.json()["title"] == "New"
    assert res.json()["status"] == "done"


def test_delete_task():
    token, _ = register_and_login()
    task_id = client.post("/tasks", json={"title": "To delete"}, headers=auth_header(token)).json()["id"]
    res = client.delete(f"/tasks/{task_id}", headers=auth_header(token))
    assert res.status_code == 204


def test_cannot_access_other_users_task():
    token1, _ = register_and_login("user1@example.com", "pass1")
    token2, _ = register_and_login("user2@example.com", "pass2")
    task_id = client.post("/tasks", json={"title": "Private"}, headers=auth_header(token1)).json()["id"]
    res = client.delete(f"/tasks/{task_id}", headers=auth_header(token2))
    assert res.status_code == 404