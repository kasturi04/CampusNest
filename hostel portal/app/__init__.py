import os
from flask import Flask, session, redirect, url_for, g
from app.config import Config
from app.database import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize Database
    db.init_app(app)
    
    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.admin import admin_bp
    from app.routes.staff import staff_bp
    from app.routes.complaints import complaints_bp
    from app.routes.attendance import attendance_bp
    from app.routes.reports import reports_bp
    from app.routes.ai_assistant import ai_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(ai_bp)
    
    # Inject user details into templates globally
    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        if user_id is None:
            g.user = None
            g.unread_notifications = []
        else:
            from app.models import User, Notification
            g.user = User.query.get(user_id)
            if g.user:
                g.unread_notifications = Notification.query.filter_by(user_id=user_id, is_read=False).order_by(Notification.created_at.desc()).all()
            else:
                g.unread_notifications = []
            
    # Default Route
    @app.route('/')
    def index():
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        role = session.get('role')
        if role == 'student':
            return redirect(url_for('student.dashboard'))
        elif role == 'admin' or role == 'super_admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'staff':
            return redirect(url_for('staff.dashboard'))
        return redirect(url_for('auth.login'))
        
    return app
