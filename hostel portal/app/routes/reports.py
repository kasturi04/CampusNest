import google.generativeai as genai
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request, session, jsonify
from app.routes.auth import login_required, role_required
from app.database import db
from app.models import User, StudentProfile, Room, Attendance, Complaint
from app.config import Config
from datetime import datetime
from app.services.report_generator import (
    generate_student_list_excel, generate_student_list_pdf,
    generate_attendance_excel, generate_attendance_pdf,
    generate_occupancy_excel, generate_occupancy_pdf,
    generate_complaint_excel, generate_complaint_pdf
)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/dashboard')
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def dashboard():
    return render_template('reports_dashboard.html')

@reports_bp.route('/download/<report_type>/<format_type>')
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def download(report_type, format_type):
    filters = request.args.to_dict()
    try:
        if report_type == 'student_list':
            if format_type == 'excel':
                file_data = generate_student_list_excel(filters)
                filename = "Filtered_Student_List_Report.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif format_type == 'pdf':
                file_data = generate_student_list_pdf(filters)
                filename = "Filtered_Student_List_Report.pdf"
                mimetype = "application/pdf"
            else:
                flash("Invalid format requested.", "danger")
                return redirect(url_for('reports.dashboard'))
                
        elif report_type == 'attendance':
            if format_type == 'excel':
                file_data = generate_attendance_excel(filters)
                filename = "Filtered_Attendance_Report.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif format_type == 'pdf':
                file_data = generate_attendance_pdf(filters)
                filename = "Filtered_Attendance_Report.pdf"
                mimetype = "application/pdf"
            else:
                flash("Invalid format requested.", "danger")
                return redirect(url_for('reports.dashboard'))
                
        elif report_type == 'occupancy':
            if format_type == 'excel':
                file_data = generate_occupancy_excel(filters)
                filename = "Filtered_Room_Occupancy_Report.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif format_type == 'pdf':
                file_data = generate_occupancy_pdf(filters)
                filename = "Filtered_Room_Occupancy_Report.pdf"
                mimetype = "application/pdf"
            else:
                flash("Invalid format requested.", "danger")
                return redirect(url_for('reports.dashboard'))
                
        elif report_type == 'complaint':
            if format_type == 'excel':
                file_data = generate_complaint_excel(filters)
                filename = "Filtered_Complaints_Report.xlsx"
                mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif format_type == 'pdf':
                file_data = generate_complaint_pdf(filters)
                filename = "Filtered_Complaints_Report.pdf"
                mimetype = "application/pdf"
            else:
                flash("Invalid format requested.", "danger")
                return redirect(url_for('reports.dashboard'))
                
        else:
            flash("Invalid report type requested.", "danger")
            return redirect(url_for('reports.dashboard'))
            
        return send_file(
            file_data,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for('reports.dashboard'))

@reports_bp.route('/view/<report_type>')
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def view_report(report_type):
    filters = request.args.to_dict()
    # Map friendly title names
    titles = {
        'student_list': 'Student Directory Report',
        'attendance': 'Attendance Log Report',
        'occupancy': 'Room Occupancy Report',
        'complaint': 'Maintenance Complaints Report'
    }
    title = titles.get(report_type, 'Report Viewer')
    
    # We pass the filters and report type to the HTML to render the stream
    return render_template(
        'reports_view.html',
        report_type=report_type,
        title=title,
        filters=filters
    )

@reports_bp.route('/pdf_stream/<report_type>')
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def pdf_stream(report_type):
    filters = request.args.to_dict()
    try:
        if report_type == 'student_list':
            file_data = generate_student_list_pdf(filters)
        elif report_type == 'attendance':
            file_data = generate_attendance_pdf(filters)
        elif report_type == 'occupancy':
            file_data = generate_occupancy_pdf(filters)
        elif report_type == 'complaint':
            file_data = generate_complaint_pdf(filters)
        else:
            return "Invalid report type", 400
            
        return send_file(
            file_data,
            mimetype="application/pdf"
        )
    except Exception as e:
        return f"Error streaming PDF: {str(e)}", 500

@reports_bp.route('/summarize/<report_type>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin', 'staff'])
def summarize(report_type):
    filters = request.args.to_dict()
    
    api_key = Config.GEMINI_API_KEY
    if not api_key or "your_gemini_api_key" in api_key:
        demo_summary = f"""
### [Demo Mode] AI Report Summary

A valid Gemini API Key is not configured in your `.env` file. Showing offline analytical breakdown:

#### 1. Report Details:
- **Report Type**: {report_type.replace('_', ' ').capitalize()}
- **Context Status**: Filters are active and the generated PDF/Excel documents contain the corresponding database records.

#### 2. General Observations:
- Filter search fields (e.g. Student Name, Roll Number, Room Number, Block) are applied directly to the SQLite query.
- Use the top actions to print or download the formatted report.

---
> [!TIP]
> **Enable Gemini AI Summary**: Replace `your_gemini_api_key_here` in your [`.env` file](file:///c:/Users/kastu/OneDrive/Desktop/hostel%20portal/.env) with a valid key from Google AI Studio.
"""
        return jsonify({
            'success': True,
            'response': demo_summary
        })
        
    genai.configure(api_key=api_key)
    
    records_context = ""
    
    try:
        if report_type == 'student_list':
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
            records_context = f"REPORT TYPE: Student Directory\nTotal Filtered Students: {len(students)}\n\nSample Records:\n"
            records_context += "\n".join([
                f"- Name: {s.name}, Roll: {s.username}, Year: {s.student_profile.year if s.student_profile else 'N/A'}, "
                f"Branch: {s.student_profile.branch if s.student_profile else 'N/A'}, "
                f"Room: {s.student_profile.room.room_number if (s.student_profile and s.student_profile.room) else 'Unallocated'}, "
                f"Status: {s.status}" for s in students[:50]
            ])
            
        elif report_type == 'attendance':
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
                    
            records = query.all()
            total_records = len(records)
            present_count = sum(1 for r in records if r.status == 'Present')
            absent_count = sum(1 for r in records if r.status == 'Absent')
            pct = (present_count / total_records * 100) if total_records > 0 else 0.0
            
            records_context = (
                f"REPORT TYPE: Attendance Log\n"
                f"Total Filtered Records: {total_records}\n"
                f"Present: {present_count}, Absent: {absent_count}\n"
                f"Attendance Percentage: {round(pct, 1)}%\n\n"
                f"Sample Logs:\n"
            )
            records_context += "\n".join([
                f"- Date: {r.attendance_date.strftime('%Y-%m-%d')}, Name: {r.student.name}, "
                f"Roll: {r.student.username}, Status: {r.status}, Remarks: {r.remarks or 'None'}" for r in records[:50]
            ])
            
        elif report_type == 'occupancy':
            query = db.session.query(Room)
            if filters.get('room_number'):
                query = query.filter(Room.room_number.like(f"%{filters['room_number']}%"))
            if filters.get('block'):
                query = query.filter(Room.hostel_block == filters['block'])
            if filters.get('floor'):
                query = query.filter(Room.floor == int(filters['floor']))
                
            rooms = query.all()
            total_rooms = len(rooms)
            total_capacity = sum(r.capacity for r in rooms)
            
            occupancy_data = []
            for r in rooms:
                occupied_beds = db.session.query(db.func.count(StudentProfile.user_id))\
                    .join(User)\
                    .filter(StudentProfile.room_id == r.id, User.status == 'approved')\
                    .scalar()
                occupancy_data.append({
                    'room_number': r.room_number,
                    'capacity': r.capacity,
                    'occupied': occupied_beds,
                    'block': r.hostel_block
                })
                
            total_occupied = sum(o['occupied'] for o in occupancy_data)
            vacant = total_capacity - total_occupied
            occ_pct = (total_occupied / total_capacity * 100) if total_capacity > 0 else 0.0
            
            records_context = (
                f"REPORT TYPE: Room Occupancy Summary\n"
                f"Total Rooms: {total_rooms}\n"
                f"Total Capacity (Beds): {total_capacity}\n"
                f"Occupied Beds: {total_occupied}, Vacant Beds: {vacant}\n"
                f"Hostel Occupancy Rate: {round(occ_pct, 1)}%\n\n"
                f"Rooms Details:\n"
            )
            records_context += "\n".join([
                f"- Room {o['room_number']} ({o['block']}): Capacity: {o['capacity']}, Occupied: {o['occupied']}, "
                f"Vacant: {o['capacity'] - o['occupied']}" for o in occupancy_data[:50]
            ])
            
        elif report_type == 'complaint':
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
                
            complaints = query.all()
            pending = sum(1 for c in complaints if c.status == 'Pending')
            resolved = sum(1 for c in complaints if c.status == 'Resolved')
            assigned = sum(1 for c in complaints if c.status == 'Assigned')
            progress = sum(1 for c in complaints if c.status == 'In Progress')
            
            records_context = (
                f"REPORT TYPE: Maintenance Complaints\n"
                f"Total Complaints: {len(complaints)}\n"
                f"Pending: {pending}, Assigned: {assigned}, In Progress: {progress}, Resolved: {resolved}\n\n"
                f"Complaints details:\n"
            )
            records_context += "\n".join([
                f"- ID: {c.id}, Student: {c.student.name}, Category: {c.category}, Title: {c.title}, "
                f"Status: {c.status}, Date: {c.created_at.strftime('%Y-%m-%d')}" for c in complaints[:50]
            ])
            
        else:
            return jsonify({'success': False, 'response': 'Invalid report type for AI summary.'}), 400

        # Feed to Gemini
        prompt = f"""
You are the HostelOS AI Report Summarizer.
Analyze the following filtered database statistics and records, and compile a professional high-level report summary.

STATISTICS AND RECORDS CONTEXT:
{records_context}

Please generate a summary containing:
1. A clear breakdown of the **Total counts** and ratios (e.g. Present vs Absent, Occupancy Rate, Resolved/Pending Complaints).
2. Key **Observations** or trends noticed (e.g. which rooms have highest absentees or pending tickets, occupancy block comparison, etc.).
3. Actionable **Suggestions / Recommendations** for the Hostel Warden or Administrator.

Format the response using clean, bold markdown headers and lists. Do not write introductory chatter. Keep the output neat and concise.
"""
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return jsonify({
            'success': True,
            'response': response.text
        })
        
    except Exception as e:
        err_msg = str(e)
        if "API_KEY_INVALID" in err_msg or "key not valid" in err_msg.lower():
            demo_summary = f"""
### [Demo Mode] AI Report Summary

The configured Gemini API key appears to be invalid. Showing offline analytical breakdown:

#### 1. Report Details:
- **Report Type**: {report_type.replace('_', ' ').capitalize()}

---
> [!WARNING]
> **Invalid API Key**: Please update your [`.env` file](file:///c:/Users/kastu/OneDrive/Desktop/hostel%20portal/.env) with a valid key from Google AI Studio.
"""
            return jsonify({
                'success': True,
                'response': demo_summary
            })
            
        return jsonify({
            'success': False,
            'response': f"Failed to generate summary: {err_msg}"
        }), 500
