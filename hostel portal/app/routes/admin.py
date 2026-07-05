from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from app.database import db
from app.models import User, StudentProfile, Room, Attendance, Notice, Complaint, EmergencyContact
from app.routes.auth import login_required, role_required
from app.services.allocation_engine import suggest_room

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from datetime import date, datetime

@admin_bp.route('/dashboard')
@login_required
@role_required(['admin', 'super_admin'])
def dashboard():
    # Trigger Attendance Not Taken Alert
    try:
        today_date = date.today()
        attendance_taken_today = Attendance.query.filter_by(attendance_date=today_date).count() > 0
        if not attendance_taken_today:
            from app.models import Notification
            notif_exists = Notification.query.filter(
                Notification.message.like("%Attendance has not been marked for today%"),
                Notification.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            ).first()
            if not notif_exists:
                admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
                for admin_user in admins:
                    notif_att = Notification(
                        user_id=admin_user.id,
                        message=f"Alert: Attendance has not been marked for today ({today_date.strftime('%Y-%m-%d')}) yet."
                    )
                    db.session.add(notif_att)
                db.session.commit()
    except Exception as att_err:
        print(f"Attendance warning error: {str(att_err)}")

    # 1. Pending student count
    pending_students = User.query.filter_by(role='student', status='pending').all()
    pending_approvals_count = len(pending_students)
    
    # 2. Key KPIs
    total_rooms = Room.query.count()
    total_beds = db.session.query(db.func.sum(Room.capacity)).scalar() or 0
    occupied_beds = User.query.filter_by(role='student', status='approved').count()
    total_students = occupied_beds
    available_beds = total_beds - occupied_beds
    
    # Occupied vs Available Rooms
    occupied_rooms = Room.query.join(StudentProfile).join(User).filter(User.status == 'approved').distinct().count()
    available_rooms = total_rooms - occupied_rooms
    
    # 3. Floor-wise Occupancy Data
    floor_occupancy = {}
    for floor in [1, 2, 3]:
        total_f_beds = db.session.query(db.func.sum(Room.capacity)).filter(Room.floor == floor).scalar() or 0
        occ_f_beds = User.query.join(StudentProfile).join(Room).filter(Room.floor == floor, User.role == 'student', User.status == 'approved').count()
        floor_occupancy[floor] = {
            'total': total_f_beds,
            'occupied': occ_f_beds,
            'pct': round((occ_f_beds / total_f_beds * 100), 1) if total_f_beds > 0 else 0.0
        }
        
    # 4. Year-wise student distribution
    year_distribution = {1: 0, 2: 0, 3: 0, 4: 0}
    year_data = db.session.query(StudentProfile.year, db.func.count(StudentProfile.user_id))\
        .join(User).filter(User.status == 'approved').group_by(StudentProfile.year).all()
    for yr, count in year_data:
        if yr in year_distribution:
            year_distribution[yr] = count
            
    # 5. Complaint statistics
    complaint_stats = {
        'total': Complaint.query.count(),
        'pending': Complaint.query.filter_by(status='Pending').count(),
        'assigned': Complaint.query.filter_by(status='Assigned').count(),
        'in_progress': Complaint.query.filter_by(status='In Progress').count(),
        'resolved': Complaint.query.filter_by(status='Resolved').count()
    }
    
    # 6. Notices for display
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(5).all()

    # 7. Additional KPIs
    executive_rooms = Room.query.filter_by(room_type='Executive').count()
    normal_rooms = Room.query.filter_by(room_type='Normal').count()
    ac_rooms = Room.query.filter_by(room_type='AC').count()
    occupancy_pct = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0
    
    today = date.today()
    attendance_today = Attendance.query.filter_by(attendance_date=today, status='Present').count()
    absent_today = Attendance.query.filter_by(attendance_date=today, status='Absent').count()
    
    return render_template(
        'admin_dashboard.html',
        pending_students=pending_students,
        pending_approvals_count=pending_approvals_count,
        total_students=total_students,
        total_rooms=total_rooms,
        occupied_rooms=occupied_rooms,
        available_rooms=available_rooms,
        total_beds=total_beds,
        occupied_beds=occupied_beds,
        available_beds=available_beds,
        floor_occupancy=floor_occupancy,
        year_distribution=year_distribution,
        complaint_stats=complaint_stats,
        notices=notices,
        executive_rooms=executive_rooms,
        normal_rooms=normal_rooms,
        ac_rooms=ac_rooms,
        occupancy_pct=occupancy_pct,
        attendance_today=attendance_today,
        absent_today=absent_today
    )

# Student Approval Handlers
@admin_bp.route('/students/pending')
@login_required
@role_required(['admin', 'super_admin'])
def view_pending():
    pending = User.query.filter_by(role='student', status='pending').all()
    pending_details = []
    for s in pending:
        p = s.student_profile
        requested_room = Room.query.get(p.room_id) if (p and p.room_id) else None
        pending_details.append({
            'user': s,
            'profile': p,
            'requested_room': requested_room
        })
    return render_template('admin_pending_students.html', students=pending_details)

@admin_bp.route('/students/approve/<int:user_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def approve_student(user_id):
    student = User.query.get_or_404(user_id)
    profile = student.student_profile
    
    # Allow admin to override/set room in the post form
    room_number = request.form.get('room_number')
    
    if room_number:
        room = Room.query.filter_by(room_number=room_number).first()
        if not room:
            flash(f'Room {room_number} does not exist.', 'danger')
            return redirect(url_for('admin.view_pending'))
            
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
            .scalar()
        if occupied_count >= room.capacity:
            flash(f'Room {room_number} is already full.', 'danger')
            return redirect(url_for('admin.view_pending'))
            
        profile.room_id = room.id
    else:
        # If no room selection, auto-run engine to allocate
        rec = suggest_room(profile.year)
        if rec['success']:
            profile.room_id = rec['room_id']
        else:
            flash(f'Could not auto-allocate: {rec["reason"]}. Allocate manually before approval.', 'danger')
            return redirect(url_for('admin.view_pending'))
            
    student.status = 'approved'
    db.session.commit()
    
    # Trigger Student Approval Notification
    try:
        from app.models import Notification
        notif = Notification(
            user_id=student.id,
            message=f"Congratulations! Your registration has been approved. You are assigned to Room {profile.room.room_number if (profile and profile.room) else 'N/A'}."
        )
        db.session.add(notif)
        db.session.commit()

        # Check if room is now full
        if profile and profile.room_id:
            room = Room.query.get(profile.room_id)
            occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
                .join(User)\
                .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
                .scalar()
            if occupied_count >= room.capacity:
                admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
                for admin_user in admins:
                    notif_room_full = Notification(
                        user_id=admin_user.id,
                        message=f"Room Alert: Room {room.room_number} is now fully occupied."
                    )
                    db.session.add(notif_room_full)
                db.session.commit()
    except Exception as notif_err:
        print(f"Approval/Room-full notification error: {str(notif_err)}")
        
    flash(f'Student {student.name} approved successfully!', 'success')
    return redirect(url_for('admin.view_pending'))

@admin_bp.route('/students/reject/<int:user_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def reject_student(user_id):
    student = User.query.get_or_404(user_id)
    student.status = 'rejected'
    
    # Free up allocated room
    profile = student.student_profile
    if profile:
        profile.room_id = None
        
    db.session.commit()
    flash(f'Student {student.name} registration rejected.', 'warning')
    return redirect(url_for('admin.view_pending'))

@admin_bp.route('/students/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'super_admin'])
def edit_student(user_id):
    student = User.query.get_or_404(user_id)
    profile = student.student_profile
    
    if request.method == 'POST':
        student.name = request.form.get('name')
        student.phone = request.form.get('phone')
        profile.branch = request.form.get('branch')
        profile.year = int(request.form.get('year'))
        profile.parent_phone = request.form.get('parent_phone')
        profile.room_leader_name = request.form.get('room_leader_name')
        profile.room_leader_phone = request.form.get('room_leader_phone')
        profile.collage_status = request.form.get('collage_status', 'N/A')
        profile.tuition_fee_status = request.form.get('tuition_fee_status', 'N/A')
        profile.hostel_fee_status = request.form.get('hostel_fee_status', 'N/A')
        profile.remarks = request.form.get('remarks', '')
        
        db.session.commit()
        flash('Student details updated successfully.', 'success')
        return redirect(url_for('admin.view_pending') if student.status == 'pending' else url_for('admin.list_students'))
        
    return render_template('admin_edit_student.html', student=student, profile=profile)

@admin_bp.route('/students')
@login_required
@role_required(['admin', 'super_admin'])
def list_students():
    students = User.query.filter_by(role='student', status='approved').all()
    # Add room objects
    student_details = []
    for s in students:
        p = s.student_profile
        room = Room.query.get(p.room_id) if (p and p.room_id) else None
        student_details.append({
            'user': s,
            'profile': p,
            'room': room
        })
    return render_template('admin_student_list.html', students=student_details)


# Rooms Management
@admin_bp.route('/rooms', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'super_admin'])
def manage_rooms():
    if request.method == 'POST':
        # Add new room
        room_number = request.form.get('room_number')
        floor = int(request.form.get('floor'))
        room_type = request.form.get('room_type')
        capacity = int(request.form.get('capacity'))
        hostel_block = request.form.get('hostel_block', 'KEERTHI')
        
        # Validation
        existing = Room.query.filter_by(room_number=room_number).first()
        if existing:
            flash(f'Room {room_number} already exists.', 'danger')
            return redirect(url_for('admin.manage_rooms'))
            
        new_room = Room(
            room_number=room_number,
            floor=floor,
            room_type=room_type,
            capacity=capacity,
            status='Available',
            hostel_block=hostel_block
        )
        db.session.add(new_room)
        db.session.commit()
        flash(f'Room {room_number} added successfully!', 'success')
        return redirect(url_for('admin.manage_rooms'))
        
    rooms = Room.query.order_by(Room.room_number).all()
    room_details = []
    for r in rooms:
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == r.id, User.status == 'approved')\
            .scalar()
        room_details.append({
            'room': r,
            'total_beds': r.capacity,
            'occupied_beds': occupied_count,
            'available_beds': r.capacity - occupied_count
        })
        
    return render_template('admin_rooms.html', rooms=room_details)

@admin_bp.route('/rooms/delete/<int:room_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    # Check if any approved student is in this room
    occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
        .join(User)\
        .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
        .scalar()
    if occupied_count > 0:
        flash(f'Cannot delete Room {room.room_number}. There are currently occupied spaces.', 'danger')
        return redirect(url_for('admin.manage_rooms'))
        
    db.session.delete(room)
    db.session.commit()
    flash(f'Room {room.room_number} deleted successfully.', 'success')
    return redirect(url_for('admin.manage_rooms'))

@admin_bp.route('/rooms/edit/<int:room_id>', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'super_admin'])
def edit_room(room_id):
    room = Room.query.get_or_404(room_id)
    if request.method == 'POST':
        room.room_type = request.form.get('room_type')
        room.status = request.form.get('status')
        room.hostel_block = request.form.get('hostel_block', 'KEERTHI')
        new_capacity = int(request.form.get('capacity'))
        
        # Check if current occupied spaces exceed new capacity
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
            .scalar()
            
        if new_capacity < occupied_count:
            flash(f'Cannot reduce capacity to {new_capacity}. Currently {occupied_count} residents are in this room.', 'danger')
            return redirect(url_for('admin.edit_room', room_id=room.id))
            
        room.capacity = new_capacity
        db.session.commit()
        flash(f'Room {room.room_number} updated successfully.', 'success')
        return redirect(url_for('admin.manage_rooms'))
        
    return render_template('admin_edit_room.html', room=room)

# Room Transfers & Releases
@admin_bp.route('/rooms/transfer', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'super_admin'])
def transfer_room():
    if request.method == 'POST':
        student_id = int(request.form.get('student_id'))
        target_room_number = request.form.get('room_number')
        
        student = User.query.get_or_404(student_id)
        profile = student.student_profile
        
        room = Room.query.filter_by(room_number=target_room_number).first()
        if not room:
            flash(f'Room {target_room_number} does not exist.', 'danger')
            return redirect(url_for('admin.transfer_room'))
            
        # Check target room capacity
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
            .scalar()
        if occupied_count >= room.capacity:
            flash(f'Room {target_room_number} is already full.', 'danger')
            return redirect(url_for('admin.transfer_room'))
            
        # Perform Transfer
        profile.room_id = room.id
        db.session.commit()
        
        # Trigger Student Room Changed Notification
        try:
            from app.models import Notification
            notif = Notification(
                user_id=student.id,
                message=f"Room Changed: You have been transferred to Room {target_room_number}."
            )
            db.session.add(notif)
            db.session.commit()

            # Check if target room is now full
            occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
                .join(User)\
                .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
                .scalar()
            if occupied_count >= room.capacity:
                admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
                for admin_user in admins:
                    notif_room_full = Notification(
                        user_id=admin_user.id,
                        message=f"Room Alert: Room {room.room_number} is now fully occupied."
                    )
                    db.session.add(notif_room_full)
                db.session.commit()
        except Exception as notif_err:
            print(f"Room transfer/Room-full notification error: {str(notif_err)}")
            
        flash(f'Student {student.name} transferred to room {target_room_number} successfully!', 'success')
        return redirect(url_for('admin.list_students'))
        
    # GET: fetch all approved students and available rooms
    students = User.query.filter_by(role='student', status='approved').all()
    # List of rooms with vacancies
    rooms = Room.query.all()
    vacancies = []
    for r in rooms:
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == r.id, User.status == 'approved')\
            .scalar()
        if occupied_count < r.capacity:
            vacancies.append({'room': r, 'vacant_spaces': r.capacity - occupied_count})
            
    return render_template('admin_room_transfer.html', students=students, vacancies=vacancies)

@admin_bp.route('/rooms/release/<int:student_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def release_room(student_id):
    student = User.query.get_or_404(student_id)
    profile = student.student_profile
    
    if profile and profile.room_id:
        profile.room_id = None
        db.session.commit()
        flash(f'Room vacated for student {student.name}.', 'success')
    else:
        flash(f'Student {student.name} does not hold an allocated room.', 'warning')
        
    return redirect(url_for('admin.list_students'))


# Post Notices
@admin_bp.route('/notices/post', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def post_notice():
    title = request.form.get('title')
    content = request.form.get('content')
    target = request.form.get('target_audience')
    
    new_notice = Notice(
        title=title,
        content=content,
        created_by_id=session['user_id'],
        target_audience=target
    )
    db.session.add(new_notice)
    db.session.commit()
    flash('Notice posted successfully!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/students/profile/<int:user_id>')
@login_required
@role_required(['admin', 'super_admin'])
def view_student_profile(user_id):
    student = User.query.get_or_404(user_id)
    profile = student.student_profile
    room = Room.query.get(profile.room_id) if (profile and profile.room_id) else None
    
    # Calculate attendance stats
    total_days = Attendance.query.filter_by(student_id=student.id).count()
    present_days = Attendance.query.filter_by(student_id=student.id, status='Present').count()
    absent_days = Attendance.query.filter_by(student_id=student.id, status='Absent').count()
    attendance_pct = round((present_days / total_days * 100), 1) if total_days > 0 else 0.0
    
    # Histories
    attendance_history = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.attendance_date.desc()).limit(10).all()
    complaints = Complaint.query.filter_by(student_id=student.id).order_by(Complaint.created_at.desc()).all()
    
    return render_template(
        'admin_student_profile.html',
        student=student,
        profile=profile,
        room=room,
        attendance_pct=attendance_pct,
        present_days=present_days,
        absent_days=absent_days,
        attendance_history=attendance_history,
        complaints=complaints
    )

@admin_bp.route('/search')
@login_required
@role_required(['admin', 'super_admin'])
def search():
    query_str = request.args.get('q', '').strip()
    
    student_results = []
    room_results = []
    complaint_results = []
    
    if query_str:
        # Search students by name, roll number, or phone
        student_results = User.query.join(StudentProfile, isouter=True).filter(
            User.role == 'student',
            (User.name.like(f"%{query_str}%") | 
             User.username.like(f"%{query_str}%") | 
             User.phone.like(f"%{query_str}%") |
             StudentProfile.parent_phone.like(f"%{query_str}%") |
             StudentProfile.room_leader_name.like(f"%{query_str}%") |
             StudentProfile.branch.like(f"%{query_str}%"))
        ).all()
        
        # Search rooms by room number
        room_results = Room.query.filter(Room.room_number.like(f"%{query_str}%")).all()
        
        # Search complaints by ID or category or title
        complaint_queries = Complaint.query.filter(
            (Complaint.category.like(f"%{query_str}%") | 
             Complaint.title.like(f"%{query_str}%"))
        )
        if query_str.isdigit():
            complaint_queries = complaint_queries.or_(Complaint.id == int(query_str))
        complaint_results = complaint_queries.all()
        
    return render_template(
        'admin_search_results.html',
        query=query_str,
        students=student_results,
        rooms=room_results,
        complaints=complaint_results
    )

@admin_bp.route('/emergency-contacts')
@login_required
@role_required(['admin', 'super_admin'])
def emergency_contacts():
    contacts = EmergencyContact.query.all()
    return render_template('admin_emergency_contacts.html', contacts=contacts)

@admin_bp.route('/emergency-contacts/add', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def add_contact():
    name = request.form.get('name', '').strip()
    role = request.form.get('role', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if not name or not role or not phone:
        flash("All fields are required.", "danger")
        return redirect(url_for('admin.emergency_contacts'))
        
    new_contact = EmergencyContact(name=name, role=role, phone=phone)
    db.session.add(new_contact)
    db.session.commit()
    flash(f"Emergency Contact '{name}' added successfully.", "success")
    return redirect(url_for('admin.emergency_contacts'))

@admin_bp.route('/emergency-contacts/edit/<int:contact_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def edit_contact(contact_id):
    contact = EmergencyContact.query.get_or_404(contact_id)
    name = request.form.get('name', '').strip()
    role = request.form.get('role', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if not name or not role or not phone:
        flash("All fields are required.", "danger")
        return redirect(url_for('admin.emergency_contacts'))
        
    contact.name = name
    contact.role = role
    contact.phone = phone
    db.session.commit()
    flash(f"Emergency Contact '{name}' updated successfully.", "success")
    return redirect(url_for('admin.emergency_contacts'))

@admin_bp.route('/emergency-contacts/delete/<int:contact_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def delete_contact(contact_id):
    contact = EmergencyContact.query.get_or_404(contact_id)
    name = contact.name
    db.session.delete(contact)
    db.session.commit()
    flash(f"Emergency Contact '{name}' deleted successfully.", "success")
    return redirect(url_for('admin.emergency_contacts'))
