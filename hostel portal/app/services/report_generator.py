import io
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models import User, StudentProfile, Room, Attendance, Complaint, ComplaintAssignment
from app.database import db

def generate_student_list_excel(filters=None):
    if filters is None:
        filters = {}
    
    query = db.session.query(User).filter(User.role == 'student')
    query = query.join(StudentProfile, isouter=True).join(Room, StudentProfile.room_id == Room.id, isouter=True)
    
    if filters.get('student_name'):
        query = query.filter(User.name.like(f"%{filters['student_name']}%"))
    if filters.get('roll_number'):
        query = query.filter(User.username.like(f"%{filters['roll_number']}%"))
    if filters.get('year'):
        query = query.filter(StudentProfile.year == int(filters['year']))
    if filters.get('branch'):
        query = query.filter(StudentProfile.branch.like(f"%{filters['branch']}%"))
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
        
    students = query.all()
    data = []
    for s in students:
        p = s.student_profile
        room = Room.query.get(p.room_id) if (p and p.room_id) else None
        data.append({
            "Name": s.name,
            "Roll Number": s.username,
            "Branch": p.branch if p else "N/A",
            "Year": p.year if p else "N/A",
            "Student Phone": s.phone,
            "Parent Phone": p.parent_phone if p else "N/A",
            "Room Number": room.room_number if room else "Unallocated",
            "Room Leader": p.room_leader_name if (p and p.room_leader_name) else "N/A",
            "Status": s.status.capitalize()
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Students')
    output.seek(0)
    return output

def generate_student_list_pdf(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(User).filter(User.role == 'student')
    query = query.join(StudentProfile, isouter=True).join(Room, StudentProfile.room_id == Room.id, isouter=True)
    
    if filters.get('student_name'):
        query = query.filter(User.name.like(f"%{filters['student_name']}%"))
    if filters.get('roll_number'):
        query = query.filter(User.username.like(f"%{filters['roll_number']}%"))
    if filters.get('year'):
        query = query.filter(StudentProfile.year == int(filters['year']))
    if filters.get('branch'):
        query = query.filter(StudentProfile.branch.like(f"%{filters['branch']}%"))
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
        
    students = query.all()
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1, # Center
        spaceAfter=15
    )
    
    elements = [
        Paragraph("HostelOS - Student Registration Directory", title_style),
        Spacer(1, 15)
    ]
    
    table_data = [["Roll No", "Student Name", "Year", "Branch", "Room No", "Status"]]
    for s in students:
        p = s.student_profile
        room = Room.query.get(p.room_id) if (p and p.room_id) else None
        room_number = room.room_number if room else 'N/A'
        table_data.append([
            s.username,
            s.name,
            str(p.year) if p else "N/A",
            p.branch if p else "N/A",
            room_number,
            s.status.capitalize()
        ])
        
    t = Table(table_data, colWidths=[80, 160, 40, 80, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
    ]))
    
    elements.append(t)
    doc.build(elements)
    output.seek(0)
    return output

def generate_attendance_excel(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(Attendance).join(User, Attendance.student_id == User.id).join(StudentProfile, StudentProfile.user_id == User.id, isouter=True).join(Room, StudentProfile.room_id == Room.id, isouter=True)
    
    if filters.get('student_name'):
        query = query.filter(User.name.like(f"%{filters['student_name']}%"))
    if filters.get('roll_number'):
        query = query.filter(User.username.like(f"%{filters['roll_number']}%"))
    if filters.get('year'):
        query = query.filter(StudentProfile.year == int(filters['year']))
    if filters.get('branch'):
        query = query.filter(StudentProfile.branch.like(f"%{filters['branch']}%"))
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
    if filters.get('date'):
        try:
            d_val = datetime.strptime(filters['date'], '%Y-%m-%d').date()
            query = query.filter(Attendance.attendance_date == d_val)
        except Exception:
            pass
            
    records = query.order_by(Attendance.attendance_date.desc()).all()
    data = []
    for r in records:
        data.append({
            "Date": r.attendance_date.strftime('%Y-%m-%d'),
            "Roll Number": r.student.username,
            "Student Name": r.student.name,
            "Year": r.student.student_profile.year if r.student.student_profile else "N/A",
            "Attendance Status": r.status,
            "Remarks": r.remarks or "",
            "Marked By": r.marked_by.name if r.marked_by else "System"
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance')
    output.seek(0)
    return output

def generate_attendance_pdf(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(Attendance).join(User, Attendance.student_id == User.id).join(StudentProfile, StudentProfile.user_id == User.id, isouter=True).join(Room, StudentProfile.room_id == Room.id, isouter=True)
    
    if filters.get('student_name'):
        query = query.filter(User.name.like(f"%{filters['student_name']}%"))
    if filters.get('roll_number'):
        query = query.filter(User.username.like(f"%{filters['roll_number']}%"))
    if filters.get('year'):
        query = query.filter(StudentProfile.year == int(filters['year']))
    if filters.get('branch'):
        query = query.filter(StudentProfile.branch.like(f"%{filters['branch']}%"))
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
    if filters.get('date'):
        try:
            d_val = datetime.strptime(filters['date'], '%Y-%m-%d').date()
            query = query.filter(Attendance.attendance_date == d_val)
        except Exception:
            pass
            
    records = query.order_by(Attendance.attendance_date.desc()).all()
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,
        spaceAfter=15
    )
    
    elements = [
        Paragraph("HostelOS - Attendance Log Report", title_style),
        Spacer(1, 15)
    ]
    
    table_data = [["Date", "Roll No", "Student Name", "Year", "Status", "Remarks"]]
    for r in records:
        table_data.append([
            r.attendance_date.strftime('%Y-%m-%d'),
            r.student.username,
            r.student.name,
            str(r.student.student_profile.year) if r.student.student_profile else "N/A",
            r.status,
            r.remarks or ""
        ])
        
    t = Table(table_data, colWidths=[80, 80, 160, 40, 60, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
    ]))
    
    elements.append(t)
    doc.build(elements)
    output.seek(0)
    return output

def generate_occupancy_excel(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(Room)
    
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
    if filters.get('floor'):
        query = query.filter(Room.floor == int(filters['floor']))
        
    rooms = query.all()
    data = []
    for r in rooms:
        occupied_beds = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == r.id, User.status == 'approved')\
            .scalar()
        data.append({
            "Room Number": r.room_number,
            "Floor": r.floor,
            "Room Type": r.room_type,
            "Capacity": r.capacity,
            "Occupied Beds": occupied_beds,
            "Available Beds": r.capacity - occupied_beds,
            "Status": r.status
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Occupancy')
    output.seek(0)
    return output

def generate_occupancy_pdf(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(Room)
    
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
    if filters.get('floor'):
        query = query.filter(Room.floor == int(filters['floor']))
        
    rooms = query.all()
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,
        spaceAfter=15
    )
    
    elements = [
        Paragraph("HostelOS - Room Occupancy Report", title_style),
        Spacer(1, 15)
    ]
    
    table_data = [["Room No", "Floor", "Room Type", "Capacity", "Occupied Beds", "Available Beds", "Status"]]
    for r in rooms:
        occupied_beds = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == r.id, User.status == 'approved')\
            .scalar()
        table_data.append([
            r.room_number,
            str(r.floor),
            r.room_type,
            str(r.capacity),
            str(occupied_beds),
            str(r.capacity - occupied_beds),
            r.status
        ])
        
    t = Table(table_data, colWidths=[80, 50, 90, 60, 80, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
    ]))
    
    elements.append(t)
    doc.build(elements)
    output.seek(0)
    return output

def generate_complaint_excel(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(Complaint).join(User, Complaint.student_id == User.id).join(StudentProfile, StudentProfile.user_id == User.id, isouter=True).join(Room, StudentProfile.room_id == Room.id, isouter=True)
    
    if filters.get('student_name'):
        query = query.filter(User.name.like(f"%{filters['student_name']}%"))
    if filters.get('roll_number'):
        query = query.filter(User.username.like(f"%{filters['roll_number']}%"))
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
    if filters.get('category'):
        query = query.filter(Complaint.category == filters['category'])
    if filters.get('status'):
        query = query.filter(Complaint.status == filters['status'])
        
    complaints = query.order_by(Complaint.created_at.desc()).all()
    data = []
    for c in complaints:
        assigned_staff = c.assignment.staff.name if (c.assignment and c.assignment.staff) else "Unassigned"
        resolved_date = c.assignment.resolved_at.strftime('%Y-%m-%d %H:%M') if (c.assignment and c.assignment.resolved_at) else "N/A"
        
        data.append({
            "Ticket ID": c.id,
            "Date Submitted": c.created_at.strftime('%Y-%m-%d %H:%M'),
            "Student Name": c.student.name if c.student else "Unknown",
            "Category": c.category,
            "Title": c.title,
            "Description": c.description,
            "Status": c.status,
            "Assigned Staff": assigned_staff,
            "Date Resolved": resolved_date
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Complaints')
    output.seek(0)
    return output

def generate_complaint_pdf(filters=None):
    if filters is None:
        filters = {}
        
    query = db.session.query(Complaint).join(User, Complaint.student_id == User.id).join(StudentProfile, StudentProfile.user_id == User.id, isouter=True).join(Room, StudentProfile.room_id == Room.id, isouter=True)
    
    if filters.get('student_name'):
        query = query.filter(User.name.like(f"%{filters['student_name']}%"))
    if filters.get('roll_number'):
        query = query.filter(User.username.like(f"%{filters['roll_number']}%"))
    if filters.get('room_number'):
        query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
    if filters.get('block'):
        query = query.filter(Room.hostel_block == filters['block'])
    if filters.get('category'):
        query = query.filter(Complaint.category == filters['category'])
    if filters.get('status'):
        query = query.filter(Complaint.status == filters['status'])
        
    complaints = query.order_by(Complaint.created_at.desc()).all()
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,
        spaceAfter=15
    )
    
    elements = [
        Paragraph("HostelOS - Maintenance Complaint Tickets Report", title_style),
        Spacer(1, 15)
    ]
    
    table_data = [["ID", "Date", "Student Name", "Category", "Complaint Title", "Status", "Staff"]]
    for c in complaints:
        assigned_staff = c.assignment.staff.name.split(' ')[0] if (c.assignment and c.assignment.staff) else "None"
        table_data.append([
            str(c.id),
            c.created_at.strftime('%Y-%m-%d'),
            c.student.name if c.student else "N/A",
            c.category,
            c.title,
            c.status,
            assigned_staff
        ])
        
    t = Table(table_data, colWidths=[30, 80, 110, 80, 140, 60, 50])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
    ]))
    
    elements.append(t)
    doc.build(elements)
    output.seek(0)
    return output
