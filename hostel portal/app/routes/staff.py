from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from app.database import db
from app.models import User, Complaint, ComplaintAssignment
from app.routes.auth import login_required, role_required

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.route('/dashboard')
@login_required
@role_required(['staff'])
def dashboard():
    staff_id = session['user_id']
    
    # Query all complaints assigned to this staff member
    assignments = ComplaintAssignment.query.filter_by(staff_id=staff_id).all()
    
    # Sort them by complaint status: put unresolved ones first
    assigned_tickets = []
    resolved_tickets = []
    
    for ass in assignments:
        c = ass.complaint
        ticket = {
            'assignment_id': ass.id,
            'complaint_id': c.id,
            'student_name': c.student.name if c.student else "Unknown Student",
            'student_phone': c.student.phone if c.student else "N/A",
            'category': c.category,
            'title': c.title,
            'description': c.description,
            'status': c.status,
            'assigned_at': ass.assigned_at,
            'resolved_at': ass.resolved_at,
            'staff_notes': ass.staff_notes
        }
        if c.status == 'Resolved':
            resolved_tickets.append(ticket)
        else:
            assigned_tickets.append(ticket)
            
    return render_template(
        'staff_dashboard.html',
        assigned_tickets=assigned_tickets,
        resolved_tickets=resolved_tickets
    )

@staff_bp.route('/ticket/update/<int:assignment_id>', methods=['POST'])
@login_required
@role_required(['staff'])
def update_ticket(assignment_id):
    assignment = ComplaintAssignment.query.get_or_404(assignment_id)
    complaint = assignment.complaint
    
    new_status = request.form.get('status')
    staff_notes = request.form.get('staff_notes')
    
    if new_status not in ['Assigned', 'In Progress', 'Resolved']:
        flash('Invalid status selected.', 'danger')
        return redirect(url_for('staff.dashboard'))
        
    complaint.status = new_status
    assignment.staff_notes = staff_notes
    
    if new_status == 'Resolved':
        from datetime import datetime
        assignment.resolved_at = datetime.utcnow()
        
    db.session.commit()
    flash(f'Ticket #{complaint.id} status updated to {new_status}.', 'success')
    return redirect(url_for('staff.dashboard'))
