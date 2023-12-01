from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_swagger_ui import get_swaggerui_blueprint
from werkzeug.security import generate_password_hash
from models.user import User, db
from models.task import Task
from flask_migrate import Migrate
from werkzeug.security import check_password_hash
from flask_cors import CORS
from datetime import timedelta, datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123@localhost/tasks'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your_secret_key_here'
CORS(app)
db.init_app(app)
jwt = JWTManager(app)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=20)

with app.app_context():
    db.create_all()

migrate = Migrate(app, db)
scheduler = BackgroundScheduler()


def check_task_due_dates():
    with app.app_context():
        current_date = datetime.now()
        overdue_tasks = Task.query.filter(Task.due_date < current_date, Task.status != 'completed').all()

        for task in overdue_tasks:
            task.status = 'failed'
            db.session.commit()


scheduler.add_job(check_task_due_dates, 'interval', days=1)
scheduler.start()


@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    role = request.json.get('role', 'worker')

    if username is None or password is None:
        return jsonify({"msg": "Missing username or password"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "Username already exists"}), 400

    user = User(username=username, password=password, role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({"msg": "User created successfully"}), 201


@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password_hash, password):
        access_token = create_access_token(identity=user.id,
                                           additional_claims={"username": username, "role": user.role})
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "Bad username or password"}), 401


@app.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get(user_id)
    if user:
        return jsonify({"username": user.username, "role": user.role})
    else:
        return jsonify({"message": "User not found"}), 404


@app.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    new_password = request.json.get('password')
    if new_password:
        user.password_hash = generate_password_hash(new_password)

    db.session.commit()
    return jsonify({"message": "User updated successfully"})


@app.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"})


@app.route('/tasks', methods=['POST'])
@jwt_required()
def add_task():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id).first()
    if user.role != 'manager':
        return jsonify({"msg": "Only managers can create tasks"}), 403

    title = request.json.get('title')
    description = request.json.get('description')
    due_date = request.json.get('due_date')
    priority = request.json.get('priority', 1)
    status = request.json.get('status', 'pending')
    assigned_to = request.json.get('assigned_to')

    task = Task(title=title, description=description, due_date=due_date, priority=priority, status=status,
                assigned_to=assigned_to, created_by=user.id)
    db.session.add(task)
    db.session.commit()
    return jsonify(
        {"id": task.id, "title": task.title, "description": task.description, "assigned_to": task.assigned_to}), 201


@app.route('/tasks/all', methods=['GET'])
@jwt_required()
def get_all_tasks():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id).first()

    if not user or user.role != 'manager':
        return jsonify({'message': 'Access denied'}), 403

    tasks = Task.query.all()
    return jsonify([
        {"id": task.id, "title": task.title, "description": task.description,
         "due_date": task.due_date.strftime('%Y-%m-%d'), "priority": task.priority, "status": task.status}
        for task in tasks])


@app.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id).first()
    tasks = Task.query.filter_by(assigned_to=user.id).all()
    return jsonify([{"id": task.id, "title": task.title, "description": task.description, "due_date": task.due_date,
                     "priority": task.priority, "status": task.status} for task in tasks])


@app.route('/tasks/<int:task_id>/complete', methods=['PUT'])
@jwt_required()
def mark_task_completed(task_id):
    task = Task.query.filter_by(id=task_id).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id).first()

    if user.role != 'manager':
        return jsonify({"msg": "Only managers can mark tasks as completed"}), 403

    task.status = 'completed'
    db.session.commit()
    return jsonify({"msg": "Task marked as completed"})


@app.route('/users/worker', methods=['GET'])
@jwt_required()
def get_worker_users():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id).first()

    if not user or user.role != 'manager':
        return jsonify({'message': 'Access denied'}), 403

    worker_users = User.query.filter_by(role='worker').all()
    worker_user_data = [{"user_id": user.id, "username": user.username} for user in worker_users]

    return jsonify(worker_user_data)


@app.route('/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def task_operations(task_id):
    task = Task.query.filter_by(id=task_id).first()
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if request.method == 'GET':
        return jsonify({"id": task.id, "title": task.title, "description": task.description, "due_date": task.due_date,
                        "priority": task.priority, "status": task.status})

    if request.method == 'PUT':
        task.title = request.json.get('title', task.title)
        task.description = request.json.get('description', task.description)
        task.status = request.json.get('status', task.status)
        db.session.commit()
        return jsonify({"msg": "Task updated successfully"})

    if request.method == 'DELETE':
        db.session.delete(task)
        db.session.commit()
        return jsonify({'message': 'Task deleted'})



SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={'app_name': "Task Management API"})
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
print("Flask App Name:", app.name)
if __name__ == '__main__':
    app.run(debug=True)
