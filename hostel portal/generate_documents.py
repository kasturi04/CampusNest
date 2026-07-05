import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DOCS_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'static', 'assets', 'documents')
os.makedirs(DOCS_DIR, exist_ok=True)

def create_pdf(filename, title, content_paragraphs):
    filepath = os.path.join(DOCS_DIR, filename)
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=15
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        spaceAfter=10
    )
    
    elements = [
        Paragraph(title, title_style),
        Spacer(1, 10)
    ]
    
    for p in content_paragraphs:
        elements.append(Paragraph(p, body_style))
        
    doc.build(elements)
    print(f"Created documentation: {filename}")

def generate_student_directory_pdf():
    import csv
    csv_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'student_data.csv')
    if not os.path.exists(csv_path):
        print("student_data.csv not found, skipping PDF generation.")
        return
        
    filepath = os.path.join(DOCS_DIR, "student_directory.pdf")
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=15
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )
    
    elements = [
        Paragraph("HostelOS Student Enrollment & Fee Directory", title_style),
        Spacer(1, 10)
    ]
    
    table_data = [["Room", "Roll No", "Name", "Phone", "College Status", "Hostel Fee", "Tuition Fee"]]
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)
        headers = [h.strip() for h in headers]
        
        room_idx = headers.index('Room No') if 'Room No' in headers else (headers.index('ROOM NO') if 'ROOM NO' in headers else 0)
        htno_idx = headers.index('Hall Ticket No') if 'Hall Ticket No' in headers else (headers.index('HTNO') if 'HTNO' in headers else 4)
        name_idx = headers.index('Student Name') if 'Student Name' in headers else (headers.index('NAME') if 'NAME' in headers else 5)
        phone_idx = headers.index('Student Phone') if 'Student Phone' in headers else (headers.index('phn no') if 'phn no' in headers else 6)
        clg_idx = headers.index('clg status') if 'clg status' in headers else 7
        hostel_fee_idx = headers.index('hostel fee') if 'hostel fee' in headers else 9
        tuition_fee_idx = headers.index('tution fee') if 'tution fee' in headers else 8
        
        for row in reader:
            if not row or len(row) <= max(room_idx, htno_idx, name_idx, phone_idx):
                continue
            room = row[room_idx].strip()
            htno = row[htno_idx].strip()
            name = row[name_idx].strip()
            phone = row[phone_idx].strip()
            clg_status = row[clg_idx].strip() if clg_idx < len(row) else "N/A"
            hostel_fee = row[hostel_fee_idx].strip() if hostel_fee_idx < len(row) else "N/A"
            tuition_fee = row[tuition_fee_idx].strip() if tuition_fee_idx < len(row) else "N/A"
            
            if not htno or not name:
                continue
                
            table_data.append([
                Paragraph(room, body_style),
                Paragraph(htno, body_style),
                Paragraph(name, body_style),
                Paragraph(phone, body_style),
                Paragraph(clg_status, body_style),
                Paragraph(hostel_fee, body_style),
                Paragraph(tuition_fee, body_style)
            ])
            
    # Include final year data if available
    final_csv_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'final_year_data.csv')
    if os.path.exists(final_csv_path):
        with open(final_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
            headers = [h.strip() for h in headers]
            
            room_idx = headers.index('Room No') if 'Room No' in headers else (headers.index('room') if 'room' in headers else 1)
            htno_idx = headers.index('Hall Ticket No') if 'Hall Ticket No' in headers else (headers.index('roll number') if 'roll number' in headers else 5)
            name_idx = headers.index('Student Name') if 'Student Name' in headers else (headers.index('name of student') if 'name of student' in headers else 6)
            phone_idx = headers.index('Student Phone') if 'Student Phone' in headers else (headers.index('student number') if 'student number' in headers else 8)
            
            for row in reader:
                if not row or len(row) <= max(room_idx, htno_idx, name_idx, phone_idx):
                    continue
                room = row[room_idx].strip()
                htno = row[htno_idx].strip()
                name = row[name_idx].strip()
                phone = row[phone_idx].strip()
                
                if not htno or not name:
                    continue
                    
                table_data.append([
                    Paragraph(room, body_style),
                    Paragraph(htno, body_style),
                    Paragraph(name, body_style),
                    Paragraph(phone, body_style),
                    Paragraph("IN CLG", body_style),
                    Paragraph("paid", body_style),
                    Paragraph("paid", body_style)
                ])
            
    # Table styling
    t = Table(table_data, colWidths=[40, 80, 140, 75, 65, 60, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    
    elements.append(t)
    doc.build(elements)
    print("Created student directory PDF for RAG.")

def generate_all():
    # 1. Hostel Rules
    create_pdf(
        "hostel_rules.pdf",
        "HostelOS Official Hostel Rules and Regulations Handbook",
        [
            "1. CURFEW: All students must be inside the hostel premises by 9:30 PM. Gate registers will be locked, and late entry will result in a warning letter to parents and a fine of Rs 500.",
            "2. SILENT HOURS: Strict silence must be observed from 10:00 PM to 6:00 AM. High-volume music, playing instruments, or loud group gatherings during these hours are strictly prohibited.",
            "3. ELECTRICAL APPLIANCES: Students are not permitted to use heavy electrical appliances like heaters, induction cooktops, iron presses, or personal coolers inside room sockets. Use of unauthorized appliances will lead to confiscation.",
            "4. CLEANLINESS: Every student is responsible for keeping their room clean and tidy. Wardens will carry out weekly cleanliness inspections on Saturday mornings.",
            "5. DISCIPLINE: Consumption of alcohol, drugs, or smoking inside the hostel complex is a expellable offense. Zero-tolerance policy is active."
        ]
    )
    
    # 2. Admission Guidelines
    create_pdf(
        "admission_guidelines.pdf",
        "HostelOS Admission Guidelines and Enrollment Procedures",
        [
            "1. ELIGIBILITY: Hostel accommodation is provided based on college enrollment status. Active roll number and branch registration are mandatory.",
            "2. FLOOR ALLOCATION POLICY: To maintain structured discipline, First Year students (new admissions) are allocated to the First Floor. Second Year students are allocated to the Second Floor. Third Year and Final Year (Fourth Year) students are allocated to the Third Floor.",
            "3. DOCUMENTS REQUIRED: During check-in, students must produce: (a) Hostel Fee payment receipt, (b) College admission card, (c) Two passport size photos, (d) Copy of Parent identification card.",
            "4. ROOM PREFERENCES: Room types (AC, Executive, Normal) are subject to availability and will be allocated based on request priority combined with automatic availability calculations."
        ]
    )
    
    # 3. Visitor Policies
    create_pdf(
        "visitor_policies.pdf",
        "HostelOS Visitor and Guest Accommodation Policy",
        [
            "1. VISITING HOURS: Visitors are permitted only between 4:00 PM and 7:00 PM in the hostel common reception area.",
            "2. ENTRY SIGN-IN: All parents, relatives, or college friends visiting a student must sign their name and purpose of visit in the Main Gate register before entering the lobby.",
            "3. ROOM ACCESS: No male visitors are permitted inside female wing rooms, and vice versa. Friends are not allowed in student bedrooms.",
            "4. OVERNIGHT GUESTS: Overnight guest stays in student rooms are strictly prohibited. Parents requesting accommodation must book guest rooms 48 hours in advance through the Warden office, subject to a charge of Rs 800 per night."
        ]
    )
    
    # 4. Leave Rules
    create_pdf(
        "leave_rules.pdf",
        "HostelOS Student Leave and Absence Regulations",
        [
            "1. PRIOR APPROVAL: Any student planning to travel out of the hostel overnight must submit a Leave Request through the portal or Warden slip at least 24 hours prior to departure.",
            "2. PARENTAL CONSENT: Weekend out-of-town leaves require parental authentication. Parents must send an SMS confirmation or call the Warden from their registered phone number before leave is approved.",
            "3. NIGHT OUTS: Maximum of 3 night-outs are allowed per month under academic reasons or emergency travel.",
            "4. MISSING WITHOUT PERMISSION: Being absent from night attendance without an approved leave ticket will count as a disciplinary breach."
        ]
    )
    
    # 5. Complaint Procedures
    create_pdf(
        "complaint_procedures.pdf",
        "HostelOS Maintenance Complaint Filing and SLA Procedures",
        [
            "1. TICKET FILING: Students must submit all electrical, plumbing, mess, and cleaning issues through the Complaint section of the HostelOS Portal.",
            "2. AUTOMATIC ROUTING: Tickets are auto-routed: Fan/Light issues go to the Electrician; water/leakage issues go to the Plumber; food or dining complaints go to the Mess Incharge; room sweep/washroom complaints go to the Cleaning Staff; other administrative issues route to the Warden/Admin.",
            "3. SLA RESOLUTION TIMES: Electrical and plumbing issues are resolved within 12-24 hours. Cleaning tickets are addressed within 4 hours. Administrative issues are reviewed by the Warden within 2 working days.",
            "4. FEEDBACK: Once staff marks the ticket as 'Resolved', students can view updates and logs directly from their dashboard."
        ]
    )
    
    # 6. Student Directory from CSV
    generate_student_directory_pdf()

if __name__ == "__main__":
    generate_all()
