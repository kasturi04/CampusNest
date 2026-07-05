from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False) # Roll number for student, username for others
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'super_admin', 'admin', 'staff', 'student'
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    status = db.Column(db.String(20), default='approved') # 'pending', 'approved', 'rejected'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'name': self.name,
            'phone': self.phone,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    branch = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False) # 1, 2, 3, 4
    parent_phone = db.Column(db.String(15), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True)
    room_leader_name = db.Column(db.String(100), nullable=True)
    room_leader_phone = db.Column(db.String(15), nullable=True)
    collage_status = db.Column(db.String(30), nullable=True, default='N/A')
    tuition_fee_status = db.Column(db.String(20), nullable=True, default='N/A')
    hostel_fee_status = db.Column(db.String(20), nullable=True, default='N/A')
    remarks = db.Column(db.Text, nullable=True)

class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    floor = db.Column(db.Integer, nullable=False) # 0 for Ground, 1 for First, 2 for Second, 3 for Third
    room_type = db.Column(db.String(20), nullable=False) # 'Normal', 'Executive', 'AC'
    capacity = db.Column(db.Integer, nullable=False) # 3, 7, 8, 10
    status = db.Column(db.String(20), default='Available') # 'Available', 'Full', 'Reserved', 'Maintenance'
    hostel_block = db.Column(db.String(30), nullable=False, default='KEERTHI')
    
    # Relationships
    residents = db.relationship('StudentProfile', backref='room')

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    marked_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False) # 'Present', 'Absent', 'Leave'
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], backref='attendance_records')
    marked_by = db.relationship('User', foreign_keys=[marked_by_id])

class Complaint(db.Model):
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category = db.Column(db.String(30), nullable=False) # 'Fan', 'Electrical', 'Water', 'Plumbing', 'Mess', 'Cleaning', 'Other'
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending') # 'Pending', 'Assigned', 'In Progress', 'Resolved'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], backref='complaints')
    assignment = db.relationship('ComplaintAssignment', backref='complaint', uselist=False, cascade="all, delete-orphan")

class ComplaintAssignment(db.Model):
    __tablename__ = 'complaint_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    staff_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    staff = db.relationship('User', foreign_keys=[staff_id], backref='assigned_complaints')

class Notice(db.Model):
    __tablename__ = 'notices'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    target_audience = db.Column(db.String(20), default='All') # 'All', 'First Year', 'Second Year', 'Third Year', 'Final Year'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='notices')

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(30), nullable=False) # 'student_list', 'attendance', 'occupancy', 'complaint'
    file_path = db.Column(db.String(255), nullable=False)
    file_format = db.Column(db.String(10), nullable=False) # 'pdf', 'excel'
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', backref='reports')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

class EmergencyContact(db.Model):
    __tablename__ = 'emergency_contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'phone': self.phone
        }
