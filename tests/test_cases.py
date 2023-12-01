import json
import pytest
from app import app, db


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'  # Use an in-memory SQLite database for testing
    with app.app_context():
        db.create_all()
    client = app.test_client()
    yield client
    with app.app_context():
        db.drop_all()


def register_user(client, username, password, role='worker'):
    return client.post('/register', json={'username': username, 'password': password, 'role': role})


def login_user(client, username, password):
    return client.post('/login', json={'username': username, 'password': password})


def create_task(client, token, title, description, due_date, priority=1, status='pending', assigned_to=1):
    headers = {'Authorization': f'Bearer {token}'}
    task_data = {
        'title': title,
        'description': description,
        'due_date': due_date,
        'priority': priority,
        'status': status,
        'assigned_to': assigned_to
    }
    return client.post('/tasks', json=task_data, headers=headers)


def test_register_and_login(client):
    response = register_user(client, 'test_user', '27015Juve')
    assert response.status_code == 201

    response = login_user(client, 'test_user', '27015Juve')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'access_token' in data


def test_create_task(client):
    register_user(client, 'test_manager', '27015Juve', 'manager')
    login_response = login_user(client, 'test_manager', '27015Juve')
    assert login_response.status_code == 200
    login_data = json.loads(login_response.data)
    access_token = login_data['access_token']

    response = create_task(client, access_token, 'Test Task', 'Task description', '2023-12-31')
    assert response.status_code == 201


def test_get_tasks(client):
    register_user(client, 'test_worker', '27015Juve', 'manager')
    login_response = login_user(client, 'test_worker', '27015Juve')
    assert login_response.status_code == 200
    login_data = json.loads(login_response.data)
    access_token = login_data['access_token']

    create_task(client, access_token, 'Test Task', 'Task description', '2023-12-31')

    headers = {'Authorization': f'Bearer {access_token}'}
    response = client.get('/tasks', headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1


def create_test_user_and_login(client, username, password, role='worker'):
    register_user(client, username, password, role)
    login_response = login_user(client, username, password)
    assert login_response.status_code == 200
    login_data = json.loads(login_response.data)
    access_token = login_data['access_token']
    return access_token


def test_get_user(client):
    access_token = create_test_user_and_login(client, 'test_user_get', '27015Juve', 'worker')

    headers = {'Authorization': f'Bearer {access_token}'}
    response = client.get('/users/1', headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'username' in data
    assert 'role' in data


def test_update_user(client):
    access_token = create_test_user_and_login(client, 'test_user_update', '27015Juve', 'worker')

    new_password = '27015Juven'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = client.put('/users/1', json={'password': new_password}, headers=headers)
    assert response.status_code == 200

    login_response = login_user(client, 'test_user_update', new_password)
    assert login_response.status_code == 200


def test_delete_user(client):
    access_token = create_test_user_and_login(client, 'test_user_delete', '27015Juve', 'worker')

    headers = {'Authorization': f'Bearer {access_token}'}
    response = client.delete('/users/1', headers=headers)
    assert response.status_code == 200

    login_response = login_user(client, 'test_user_delete', '27015Juve')
    assert login_response.status_code == 401


def test_mark_task_completed(client):
    manager_access_token = create_test_user_and_login(client, 'test_manager', '27015Juve', 'manager')

    create_task(client, manager_access_token, 'Test Task', 'Task description', '2023-12-31')

    headers = {'Authorization': f'Bearer {manager_access_token}'}
    response = client.get('/tasks', headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    task_id = data[0]['id']

    response = client.put(f'/tasks/{task_id}/complete', headers=headers)
    assert response.status_code == 200

    response = client.get(f'/tasks/{task_id}', headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'completed'


def test_task_operations(client):
    manager_access_token = create_test_user_and_login(client, 'test_manager', '27015Juve', 'manager')

    create_task(client, manager_access_token, 'Test Task', 'Task description', '2023-12-31')

    headers = {'Authorization': f'Bearer {manager_access_token}'}
    response = client.get('/tasks', headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    task_id = data[0]['id']

    updated_title = 'Updated Task Title'
    updated_description = 'Updated Task Description'
    updated_status = 'in_progress'
    response = client.put(f'/tasks/{task_id}',
                          json={'title': updated_title, 'description': updated_description, 'status': updated_status},
                          headers=headers)
    assert response.status_code == 200

    response = client.get(f'/tasks/{task_id}', headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['title'] == updated_title
    assert data['description'] == updated_description
    assert data['status'] == updated_status

    response = client.delete(f'/tasks/{task_id}', headers=headers)
    assert response.status_code == 200

    response = client.get(f'/tasks/{task_id}', headers=headers)
    assert response.status_code == 404


if __name__ == '__main__':
    pytest.main()
