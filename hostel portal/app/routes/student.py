from flask import Blueprint, render_template, redirect, url_for, flash, session, g, request
from app.database import db
from app.models import User, StudentProfile, Room, Attendance, Notice, Complaint
from app.routes.auth import login_required, role_required

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
@role_required(['student'])
def dashboard():
    student_id = session['user_id']
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    
    room = None
    roommates = []
    
    if profile:
        if profile.room_id:
            room = Room.query.get(profile.room_id)
            # Find roommates (excluding the current student)
            roommates = User.query.join(StudentProfile).filter(
                StudentProfile.room_id == profile.room_id,
                User.id != student_id,
                User.status == 'approved'
            ).all()
            
    # Fetch latest notices
    # Match student year for notice target audience
    student_year = profile.year if profile else 1
    year_map = {1: 'First Year', 2: 'Second Year', 3: 'Third Year', 4: 'Final Year'}
    target_audience = year_map.get(student_year, 'All')
    
    notices = Notice.query.filter(
        Notice.target_audience.in_(['All', target_audience])
    ).order_by(Notice.created_at.desc()).limit(5).all()
    
    # Fetch student's complaint statistics
    complaints = Complaint.query.filter_by(student_id=student_id).order_by(Complaint.created_at.desc()).limit(5).all()
    
    # Calculate attendance percentage
    total_days = Attendance.query.filter_by(student_id=student_id).count()
    present_days = Attendance.query.filter_by(student_id=student_id, status='Present').count()
    attendance_pct = (present_days / total_days * 100) if total_days > 0 else 0.0
    
    return render_template(
        'student_dashboard.html',
        profile=profile,
        room=room,
        roommates=roommates,
        notices=notices,
        complaints=complaints,
        attendance_pct=round(attendance_pct, 1)
    )

@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required(['student'])
def profile():
    student_id = session['user_id']
    user = User.query.get(student_id)
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.phone = request.form.get('phone')
        if profile:
            profile.parent_phone = request.form.get('parent_phone')
            profile.room_leader_name = request.form.get('room_leader_name')
            profile.room_leader_phone = request.form.get('room_leader_phone')
            
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('student.profile'))
        
    return render_template('student_profile.html', user=user, profile=profile)

@student_bp.route('/emergency-contacts')
@login_required
@role_required(['student'])
def emergency_contacts():
    from app.models import EmergencyContact
    contacts = EmergencyContact.query.all()
    return render_template('student_emergency_contacts.html', contacts=contacts)
