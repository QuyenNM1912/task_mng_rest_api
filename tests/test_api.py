import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

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


def register_and_login(email="test@example.com", password="secret123"):
    client.post("/register", json={"email": email, "password": password})
    res = client.post("/login", json={"email": email, "password": password})
    return res.json()["access_token"]


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
    token = register_and_login()
    res = client.get("/me", headers=auth_header(token))
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


def test_get_me_unauthorized():
    res = client.get("/me")
    assert res.status_code == 403


# ── Task Tests ────────────────────────────────────────────────────────────────

def test_create_task():
    token = register_and_login()
    res = client.post("/tasks", json={"title": "Buy milk"}, headers=auth_header(token))
    assert res.status_code == 201
    assert res.json()["title"] == "Buy milk"
    assert res.json()["status"] == "todo"


def test_get_tasks_paginated():
    token = register_and_login()
    for i in range(5):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_header(token))
    res = client.get("/tasks?page=1&limit=3", headers=auth_header(token))
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert len(data["tasks"]) == 3


def test_update_task():
    token = register_and_login()
    task_id = client.post("/tasks", json={"title": "Old"}, headers=auth_header(token)).json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "New", "status": "done"}, headers=auth_header(token))
    assert res.status_code == 200
    assert res.json()["title"] == "New"
    assert res.json()["status"] == "done"


def test_delete_task():
    token = register_and_login()
    task_id = client.post("/tasks", json={"title": "To delete"}, headers=auth_header(token)).json()["id"]
    res = client.delete(f"/tasks/{task_id}", headers=auth_header(token))
    assert res.status_code == 204


def test_cannot_access_other_users_task():
    token1 = register_and_login("user1@example.com", "pass1")
    token2 = register_and_login("user2@example.com", "pass2")
    task_id = client.post("/tasks", json={"title": "Private"}, headers=auth_header(token1)).json()["id"]
    res = client.delete(f"/tasks/{task_id}", headers=auth_header(token2))
    assert res.status_code == 404