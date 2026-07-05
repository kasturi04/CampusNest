from flask import Blueprint, render_template, redirect, url_for, flash, request, session, g, jsonify
from functools import wraps
from app.database import db
from app.models import User, StudentProfile, Room

auth_bp = Blueprint('auth', __name__)

# Authentication Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            user_role = session.get('role')
            if user_role not in roles:
                flash('You are not authorized to view this page.', 'danger')
                # Redirect to role-appropriate page
                if user_role == 'student':
                    return redirect(url_for('student.dashboard'))
                elif user_role in ['admin', 'super_admin']:
                    return redirect(url_for('admin.dashboard'))
                elif user_role == 'staff':
                    return redirect(url_for('staff.dashboard'))
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        # Already logged in, redirect to correct dashboard
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Admin / Staff / Super Admin can login with username, Student with Roll Number (stored in username)
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Invalid username/roll number or password.', 'danger')
            return render_template('login.html')
            
        if user.role == 'student' and user.status == 'pending':
            flash('Your registration is pending approval by the Warden/Admin.', 'warning')
            return render_template('login.html')
            
        if user.role == 'student' and user.status == 'rejected':
            flash('Your registration has been rejected. Please contact the administrator.', 'danger')
            return render_template('login.html')
            
        # Set session details
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session['name'] = user.name
        
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('index'))
        
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Retrieve role (default to student if not provided)
        role = request.form.get('role', 'student')
        
        # Retrieve common form data
        name = request.form.get('student_name')
        phone = request.form.get('phone_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Input Validation
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
            
        if role == 'admin':
            username = request.form.get('username')
            if not username:
                flash('Username is required for Admin registration.', 'danger')
                return render_template('register.html')
                
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already registered.', 'danger')
                return render_template('register.html')
                
            # Create approved admin user
            new_user = User(
                username=username,
                role='admin',
                name=name,
                phone=phone,
                status='approved'
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            flash('Admin registration successful! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
            
        else: # student
            roll_number = request.form.get('roll_number')
            branch = request.form.get('branch')
            year = request.form.get('year')
            parent_phone = request.form.get('parent_phone_number')
            room_number = request.form.get('room_number')
            room_leader_name = request.form.get('room_leader_name')
            room_leader_phone = request.form.get('room_leader_phone_number')
            
            existing_user = User.query.filter_by(username=roll_number).first()
            if existing_user:
                flash('Roll number already registered.', 'danger')
                return render_template('register.html')
                
            try:
                year_int = int(year)
            except ValueError:
                flash('Invalid Year.', 'danger')
                return render_template('register.html')
                
            # Verify Room selection
            room = Room.query.filter_by(room_number=room_number).first()
            if not room:
                # Dynamically create Room
                try:
                    floor = int(room_number[0])
                except (ValueError, IndexError):
                    floor = 1
                room = Room(
                    room_number=room_number,
                    floor=floor,
                    room_type='Normal',
                    capacity=8,
                    status='Available'
                )
                db.session.add(room)
                db.session.flush()
            else:
                # Check room occupancy
                occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
                    .join(User)\
                    .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
                    .scalar()
                if occupied_count >= room.capacity:
                    flash(f'Selected Room {room_number} is already full.', 'danger')
                    return render_template('register.html')
                    
            # Create user with 'pending' status
            new_user = User(
                username=roll_number,
                role='student',
                name=name,
                phone=phone,
                status='pending'
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush() # Generate user id
            
            # Create student profile
            new_profile = StudentProfile(
                user_id=new_user.id,
                branch=branch,
                year=year_int,
                parent_phone=parent_phone,
                room_id=room.id if room else None,
                room_leader_name=room_leader_name,
                room_leader_phone=room_leader_phone
            )
            db.session.add(new_profile)
            db.session.commit()
            
            # Trigger Admin Notifications
            try:
                from app.models import Notification
                admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
                for admin_user in admins:
                    notif = Notification(
                        user_id=admin_user.id,
                        message=f"New Student Registered: {new_user.name} ({new_user.username}) is pending approval."
                    )
                    db.session.add(notif)
                db.session.commit()
            except Exception as notif_err:
                print(f"Notification error: {str(notif_err)}")
            
            flash('Registration successful! Your account is pending admin approval.', 'success')
            return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('index'))
        
    user = User.query.get(session['user_id'])
    if not user.check_password(current_password):
        flash('Incorrect current password.', 'danger')
        return redirect(url_for('index'))
        
    user.set_password(new_password)
    db.session.commit()
    flash('Password updated successfully.', 'success')
    return redirect(url_for('index'))

@auth_bp.route('/api/allocate-room')
def api_allocate_room():
    year = request.args.get('year', type=int)
    room_type = request.args.get('room_type')
    
    if not year:
        return jsonify({'success': False, 'reason': 'Year is required.'})
        
    from app.services.allocation_engine import suggest_room
    result = suggest_room(year, room_type)
    return jsonify(result)

@auth_bp.route('/api/available-rooms')
def api_available_rooms():
    year = request.args.get('year', type=int)
    room_type = request.args.get('room_type')
    
    query = Room.query.filter(Room.status != 'Maintenance')
    
    if year:
        if year == 1:
            query = query.filter(Room.floor == 1)
        elif year == 2:
            query = query.filter(Room.floor == 2)
        elif year in [3, 4]:
            query = query.filter(Room.floor == 3)
            
    if room_type and room_type != 'All':
        query = query.filter(Room.room_type == room_type)
        
    rooms = query.order_by(Room.room_number).all()
    
    result = []
    for room in rooms:
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
            .scalar()
        
        vacancy = room.capacity - occupied_count
        if vacancy > 0:
            result.append({
                'id': room.id,
                'room_number': room.room_number,
                'room_type': room.room_type,
                'floor': room.floor,
                'vacancy': vacancy,
                'capacity': room.capacity
            })
            
    return jsonify({'success': True, 'rooms': result})

@auth_bp.route('/api/room-occupancy')
def api_room_occupancy():
    room_number = request.args.get('room_number')
    if not room_number:
        return jsonify({'success': False, 'reason': 'Room number is required.'})
        
    room = Room.query.filter_by(room_number=room_number).first()
    if not room:
        return jsonify({'success': False, 'reason': f'Room {room_number} does not exist.'})
        
    occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
        .join(User)\
        .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
        .scalar()
        
    return jsonify({
        'success': True,
        'room_number': room_number,
        'occupied_count': occupied_count,
        'capacity': room.capacity,
        'vacancy': room.capacity - occupied_count
    })

@auth_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    from app.models import Notification
    Notification.query.filter_by(user_id=session['user_id'], is_read=False).update({Notification.is_read: True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(request.referrer or url_for('index'))

