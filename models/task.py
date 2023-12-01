from models.user import db
from datetime import date


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    due_date = db.Column(db.Date, default=date.today)
    priority = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='pending')
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, title, description, assigned_to, created_by, due_date=None, priority=1, status='pending'):
        self.title = title
        self.description = description
        self.assigned_to = assigned_to
        self.created_by = created_by
        self.due_date = due_date if due_date is not None else date.today()
        self.priority = priority
        self.status = status
