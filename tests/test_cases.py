import json
import pytest
from app import app, db
from models.user import User
from models.task import Task


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'  # Use a test database
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # Create a test manager user with a password (the model will hash it)
            manager = User(username="manager", password="managerpassword", role="manager")
            db.session.add(manager)
            # Create two test worker users with passwords (the model will hash them)
            worker1 = User(username="worker1", password="worker1password", role="worker")
            worker2 = User(username="worker2", password="worker2password", role="worker")
            db.session.add(worker1)
            db.session.add(worker2)
            db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()


def login(client, username, password):
    response = client.post('/login', json={"username": username, "password": password})
    return json.loads(response.data)


def create_task(client, title, description, due_date, priority, status, assigned_to, manager_token):
    response = client.post('/tasks', json={
        "title": title,
        "description": description,
        "due_date": due_date,
        "priority": priority,
        "status": status,
        "assigned_to": assigned_to
    }, headers={"Authorization": f"Bearer {manager_token}"})
    return json.loads(response.data)


def test_login(client):
    response = login(client, "manager", "managerpassword")
    assert response.get("access_token")
    assert response["access_token"].startswith("eyJ")


def test_create_task(client):
    manager_token = login(client, "manager", "managerpassword")["access_token"]
    response = create_task(client, "Test Task", "This is a test task", "2023-12-31", 1, "pending", "worker1",
                           manager_token)
    assert response.get("id")
    assert response.get("title") == "Test Task"


def test_get_tasks(client):
    manager_token = login(client, "manager", "managerpassword")["access_token"]
    worker1_token = login(client, "worker1", "worker1password")["access_token"]
    worker2_token = login(client, "worker2", "worker2password")["access_token"]

    # Create tasks assigned to different workers
    create_task(client, "Task 1", "Task 1 description", "2023-12-31", 1, "pending", "worker1", manager_token)
    create_task(client, "Task 2", "Task 2 description", "2023-12-31", 2, "pending", "worker2", manager_token)

    # Retrieve tasks for worker1
    response = client.get('/tasks', headers={"Authorization": f"Bearer {worker1_token}"})
    tasks = json.loads(response.data)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Task 1"

    # Retrieve tasks for worker2
    response = client.get('/tasks', headers={"Authorization": f"Bearer {worker2_token}"})
    tasks = json.loads(response.data)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Task 2"


def test_delete_task(client):
    manager_token = login(client, "manager", "managerpassword")["access_token"]
    worker1_token = login(client, "worker1", "worker1password")["access_token"]

    # Create a task assigned to worker1
    task = create_task(client, "Task to Delete", "Task description", "2023-12-31", 1, "pending", "worker1",
                       manager_token)

    # Attempt to delete the task as worker1 (should fail)
    response = client.delete(f'/tasks/{task["id"]}', headers={"Authorization": f"Bearer {worker1_token}"})
    assert response.status_code == 403

    # Delete the task as a manager (should succeed)
    response = client.delete(f'/tasks/{task["id"]}', headers={"Authorization": f"Bearer {manager_token}"})
    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main()
