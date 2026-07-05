from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from datetime import datetime, date
from app.database import db
from app.models import User, StudentProfile, Attendance, Room
from app.routes.auth import login_required, role_required

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@attendance_bp.route('/mark', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def mark():
    selected_year = request.args.get('year', type=int, default=1)
    selected_date_str = request.args.get('date', default=date.today().strftime('%Y-%m-%d'))
    
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()
        selected_date_str = selected_date.strftime('%Y-%m-%d')
        
    if request.method == 'POST':
        # Get all approved students for the selected year
        students = User.query.join(StudentProfile).filter(
            User.role == 'student',
            User.status == 'approved',
            StudentProfile.year == selected_year
        ).all()
        
        marked_by = session['user_id']
        
        for student in students:
            status = request.form.get(f'status_{student.id}', 'Present')
            remarks = request.form.get(f'remarks_{student.id}', '')
            
            # Check if record already exists for this date and student
            att_record = Attendance.query.filter_by(
                student_id=student.id,
                attendance_date=selected_date
            ).first()
            
            if att_record:
                att_record.status = status
                att_record.remarks = remarks
                att_record.marked_by_id = marked_by
            else:
                new_att = Attendance(
                    student_id=student.id,
                    marked_by_id=marked_by,
                    attendance_date=selected_date,
                    status=status,
                    remarks=remarks
                )
                db.session.add(new_att)
                
        db.session.commit()
        flash(f'Attendance for Year {selected_year} marked successfully for {selected_date_str}!', 'success')
        return redirect(url_for('attendance.mark', year=selected_year, date=selected_date_str))
        
    # GET: fetch students and their attendance status for this date, sorted room-wise
    students = User.query.join(StudentProfile).outerjoin(Room, StudentProfile.room_id == Room.id).filter(
        User.role == 'student',
        User.status == 'approved',
        StudentProfile.year == selected_year
    ).order_by(Room.room_number, User.name).all()
    
    student_records = []
    for s in students:
        att = Attendance.query.filter_by(student_id=s.id, attendance_date=selected_date).first()
        student_records.append({
            'student': s,
            'status': att.status if att else 'Present', # Default to Present
            'remarks': att.remarks if att else ''
        })
        
    return render_template(
        'attendance_mark.html',
        students=student_records,
        year=selected_year,
        date_str=selected_date_str
    )

@attendance_bp.route('/analytics')
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def analytics():
    # 1. Overall stats for today
    today = date.today()
    total_students_count = User.query.filter_by(role='student', status='approved').count()
    
    today_records = Attendance.query.filter_by(attendance_date=today).all()
    present_today = sum(1 for r in today_records if r.status == 'Present')
    absent_today = sum(1 for r in today_records if r.status == 'Absent')
    
    pct_today = (present_today / total_students_count * 100) if total_students_count > 0 else 0.0
    overall = {
        'total': total_students_count,
        'present': present_today,
        'absent': absent_today,
        'pct': round(pct_today, 1)
    }

    # 2. Year-wise stats
    year_stats = {}
    for yr in [1, 2, 3, 4]:
        students_yr = User.query.join(StudentProfile).filter(
            User.role == 'student',
            User.status == 'approved',
            StudentProfile.year == yr
        ).all()
        yr_total = len(students_yr)
        student_ids = [s.id for s in students_yr]
        
        if student_ids:
            yr_records = Attendance.query.filter(
                Attendance.student_id.in_(student_ids),
                Attendance.attendance_date == today
            ).all()
            yr_present = sum(1 for r in yr_records if r.status == 'Present')
            yr_absent = sum(1 for r in yr_records if r.status == 'Absent')
        else:
            yr_present = 0
            yr_absent = 0
            
        yr_pct = (yr_present / yr_total * 100) if yr_total > 0 else 0.0
        year_stats[yr] = {
            'total': yr_total,
            'present': yr_present,
            'absent': yr_absent,
            'pct': round(yr_pct, 1)
        }

    # 3. Block-wise stats
    blocks = db.session.query(Room.hostel_block).distinct().all()
    block_names = [b[0] for b in blocks if b[0]]
    if not block_names:
        block_names = ['KEERTHI']
        
    block_stats = {}
    for blk in block_names:
        students_blk = User.query.join(StudentProfile).join(Room, StudentProfile.room_id == Room.id).filter(
            User.role == 'student',
            User.status == 'approved',
            Room.hostel_block == blk
        ).all()
        blk_total = len(students_blk)
        student_ids = [s.id for s in students_blk]
        
        if student_ids:
            blk_records = Attendance.query.filter(
                Attendance.student_id.in_(student_ids),
                Attendance.attendance_date == today
            ).all()
            blk_present = sum(1 for r in blk_records if r.status == 'Present')
            blk_absent = sum(1 for r in blk_records if r.status == 'Absent')
        else:
            blk_present = 0
            blk_absent = 0
            
        blk_pct = (blk_present / blk_total * 100) if blk_total > 0 else 0.0
        block_stats[blk] = {
            'total': blk_total,
            'present': blk_present,
            'absent': blk_absent,
            'pct': round(blk_pct, 1)
        }

    # 4. Floor-wise stats
    floor_stats = {}
    for flr in [1, 2, 3, 4]:
        students_flr = User.query.join(StudentProfile).join(Room, StudentProfile.room_id == Room.id).filter(
            User.role == 'student',
            User.status == 'approved',
            Room.floor == flr
        ).all()
        flr_total = len(students_flr)
        student_ids = [s.id for s in students_flr]
        
        if student_ids:
            flr_records = Attendance.query.filter(
                Attendance.student_id.in_(student_ids),
                Attendance.attendance_date == today
            ).all()
            flr_present = sum(1 for r in flr_records if r.status == 'Present')
            flr_absent = sum(1 for r in flr_records if r.status == 'Absent')
        else:
            flr_present = 0
            flr_absent = 0
            
        flr_pct = (flr_present / flr_total * 100) if flr_total > 0 else 0.0
        floor_stats[flr] = {
            'total': flr_total,
            'present': flr_present,
            'absent': flr_absent,
            'pct': round(flr_pct, 1)
        }

    # 5. Room-wise absentees details
    rooms = Room.query.order_by(Room.room_number).all()
    room_stats = []
    for r in rooms:
        residents = User.query.join(StudentProfile).filter(
            User.role == 'student',
            User.status == 'approved',
            StudentProfile.room_id == r.id
        ).all()
        
        resident_count = len(residents)
        vacant_beds = r.capacity - resident_count
        
        resident_ids = [s.id for s in residents]
        r_present = 0
        r_absent = 0
        absent_students = []
        
        if resident_ids:
            r_records = Attendance.query.filter(
                Attendance.student_id.in_(resident_ids),
                Attendance.attendance_date == today
            ).all()
            
            record_map = {rec.student_id: rec.status for rec in r_records}
            for res in residents:
                status = record_map.get(res.id, 'Present')
                if status == 'Present':
                    r_present += 1
                elif status == 'Absent':
                    r_absent += 1
                    absent_students.append({
                        'name': res.name,
                        'roll_number': res.username
                    })
        
        room_stats.append({
            'room_number': r.room_number,
            'capacity': r.capacity,
            'residents_count': resident_count,
            'present': r_present,
            'absent': r_absent,
            'vacant_beds': vacant_beds,
            'absent_students': absent_students
        })

    # 6. Trend data for past 7 days
    import datetime as dt
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        day = date.today() - dt.timedelta(days=i)
        trend_labels.append(day.strftime('%b %d'))
        
        day_total = Attendance.query.filter_by(attendance_date=day).count()
        day_present = Attendance.query.filter_by(attendance_date=day, status='Present').count()
        
        day_pct = (day_present / day_total * 100) if day_total > 0 else 0.0
        trend_data.append(round(day_pct, 1))

    return render_template(
        'attendance_analytics.html',
        overall=overall,
        year_stats=year_stats,
        block_stats=block_stats,
        floor_stats=floor_stats,
        room_stats=room_stats,
        trend_labels=trend_labels,
        trend_data=trend_data
    )
