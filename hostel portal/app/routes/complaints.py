from flask import Blueprint, render_template, redirect, url_for, flash, request, session, g
from datetime import datetime
from app.database import db
from app.models import User, Complaint, ComplaintAssignment
from app.routes.auth import login_required, role_required

complaints_bp = Blueprint('complaints', __name__, url_prefix='/complaints')

# Helper category-to-username mapping for routing
ROUTING_MAP = {
    'Fan': 'electrician',
    'Electrical': 'electrician',
    'Water': 'plumber',
    'Plumbing': 'plumber',
    'Mess': 'mess_incharge',
    'Cleaning': 'cleaner'
}

@complaints_bp.route('/submit', methods=['GET', 'POST'])
@login_required
@role_required(['student'])
def submit():
    if request.method == 'POST':
        description = request.form.get('description')
        category = request.form.get('category', 'Other')
        title = request.form.get('title')
        
        # If title is not provided, generate a clean short summary from the description
        if not title and description:
            clean_desc = description.strip()
            title = clean_desc[:47] + "..." if len(clean_desc) > 50 else clean_desc
        elif not title:
            title = "Complaint to Warden"
            
        student_id = session['user_id']
        
        # Create Complaint Ticket
        new_complaint = Complaint(
            student_id=student_id,
            category=category,
            title=title,
            description=description,
            status='Pending'
        )
        db.session.add(new_complaint)
        db.session.flush() # Populate complaint ID
        
        # Route directly to the Warden / Admin
        admin_user = User.query.filter_by(role='admin').first()
        if admin_user:
            new_complaint.status = 'Pending'
            assignment = ComplaintAssignment(
                complaint_id=new_complaint.id,
                staff_id=admin_user.id
            )
            db.session.add(assignment)
            
            # Send Notification to Warden(s)
            from app.models import Notification
            wardens = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
            for warden in wardens:
                notif = Notification(
                    user_id=warden.id,
                    message=f"New complaint #{new_complaint.id} submitted by {g.user.name}: {title}"
                )
                db.session.add(notif)
                
            db.session.commit()
            flash(f'Complaint submitted successfully! Ticket #{new_complaint.id} has been sent to the Warden/Admin for review.', 'success')
        else:
            db.session.commit()
            flash(f'Complaint submitted successfully! Ticket #{new_complaint.id} created.', 'success')
                
        return redirect(url_for('student.dashboard'))
        
    return render_template('complaint_submit.html')

@complaints_bp.route('/list')
@login_required
def list_tickets():
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    if user_role == 'student':
        # Students see only their complaints
        tickets = Complaint.query.filter_by(student_id=user_id).order_by(Complaint.created_at.desc()).all()
        return render_template('student_complaints.html', tickets=tickets)
    elif user_role in ['admin', 'super_admin']:
        # Admins see all complaints
        tickets = Complaint.query.order_by(Complaint.created_at.desc()).all()
        # Fetch staff list for manual re-assignment if needed
        staff_list = User.query.filter_by(role='staff').all()
        return render_template('admin_complaints.html', tickets=tickets, staff_list=staff_list)
        
    return redirect(url_for('index'))

@complaints_bp.route('/assign/<int:complaint_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def assign_ticket(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    staff_id = int(request.form.get('staff_id'))
    
    staff = User.query.get_or_404(staff_id)
    
    # Check if assignment already exists
    assignment = ComplaintAssignment.query.filter_by(complaint_id=complaint_id).first()
    if assignment:
        assignment.staff_id = staff.id
        assignment.assigned_at = datetime.utcnow()
    else:
        assignment = ComplaintAssignment(
            complaint_id=complaint_id,
            staff_id=staff.id
        )
        db.session.add(assignment)
        
    complaint.status = 'Assigned'
    
    # Send Notification to Student
    from app.models import Notification
    student_notif = Notification(
        user_id=complaint.student_id,
        message=f"Your complaint #{complaint.id} ('{complaint.title}') has been assigned to staff member {staff.name}."
    )
    db.session.add(student_notif)
    
    # Send Notification to Staff
    staff_notif = Notification(
        user_id=staff.id,
        message=f"You have been assigned a new complaint #{complaint.id}: '{complaint.title}'."
    )
    db.session.add(staff_notif)
    
    db.session.commit()
    flash(f'Ticket #{complaint.id} successfully assigned to {staff.name}.', 'success')
    return redirect(url_for('complaints.list_tickets'))

@complaints_bp.route('/resolve/<int:complaint_id>', methods=['POST'])
@login_required
@role_required(['student'])
def resolve_ticket(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    
    # Security check: Ensure the logged-in student owns this complaint
    if complaint.student_id != session['user_id']:
        flash('You are not authorized to update this ticket.', 'danger')
        return redirect(url_for('student.dashboard'))
        
    complaint.status = 'Resolved'
    
    # Update resolution timestamp on assignment if exists
    assignment = ComplaintAssignment.query.filter_by(complaint_id=complaint.id).first()
    if assignment:
        assignment.resolved_at = datetime.utcnow()
        if not assignment.staff_notes:
            assignment.staff_notes = "Resolved and confirmed by student."
            
    # Send Notification to Warden(s)
    from app.models import Notification
    wardens = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    for warden in wardens:
        notif = Notification(
            user_id=warden.id,
            message=f"Complaint #{complaint.id} has been marked as Resolved by student {g.user.name}."
        )
        db.session.add(notif)
        
    db.session.commit()
    flash(f'Ticket #{complaint.id} has been marked as Resolved and Completed!', 'success')
    
    ref = request.referrer
    if ref and ('/complaints/list' in ref or '/complaints/list' in ref):
        return redirect(url_for('complaints.list_tickets'))
    return redirect(url_for('student.dashboard'))

@complaints_bp.route('/admin-resolve/<int:complaint_id>', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def admin_resolve_ticket(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    remarks = request.form.get('remarks', 'Problem Solved').strip()
    if not remarks:
        remarks = 'Problem Solved'
        
    complaint.status = 'Resolved'
    
    # Get or create assignment
    assignment = ComplaintAssignment.query.filter_by(complaint_id=complaint.id).first()
    if assignment:
        assignment.resolved_at = datetime.utcnow()
        assignment.staff_notes = remarks
        assignment.staff_id = None  # Remove assigned staff
    else:
        assignment = ComplaintAssignment(
            complaint_id=complaint.id,
            staff_id=None,
            resolved_at=datetime.utcnow(),
            staff_notes=remarks
        )
        db.session.add(assignment)
        
    # Send Notification to Student
    from app.models import Notification
    student_notif = Notification(
        user_id=complaint.student_id,
        message=f"Your complaint #{complaint.id} ('{complaint.title}') has been resolved by Admin with remarks: {remarks}."
    )
    db.session.add(student_notif)
    
    db.session.commit()
    flash(f'Ticket #{complaint.id} has been marked as Resolved and assigned staff removed.', 'success')
    return redirect(url_for('complaints.list_tickets'))
