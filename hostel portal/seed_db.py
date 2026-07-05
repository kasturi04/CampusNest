import os
import csv
from app import create_app, db
from app.models import User, StudentProfile, Room, EmergencyContact

app = create_app()

def parse_floor(floor_str):
    digits = ''.join(c for c in floor_str if c.isdigit())
    return int(digits) if digits else 1

def parse_room_type(rt_str):
    if 'Executive' in rt_str:
        return 'Executive'
    if 'AC' in rt_str:
        return 'AC'
    return 'Normal'

def seed_database():
    with app.app_context():
        print("Dropping existing tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        print("Seeding Admins...")
        # 1. Super Admin
        super_admin = User(
            username="superadmin",
            role="super_admin",
            name="System Root Admin",
            phone="9999999999",
            status="approved"
        )
        super_admin.set_password("password123")
        db.session.add(super_admin)
        
        # 2. Admin
        admin = User(
            username="admin",
            role="admin",
            name="Warden Chief",
            phone="8888888888",
            status="approved"
        )
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

        # Load and seed Rooms
        rooms_csv_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'rooms.csv')
        if os.path.exists(rooms_csv_path):
            print("Importing rooms from CSV...")
            with open(rooms_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = [h.strip() for h in next(reader)]
                
                room_no_idx = headers.index('Room No')
                floor_idx = headers.index('Floor')
                room_type_idx = headers.index('Room Type')
                capacity_idx = headers.index('Capacity')
                status_idx = headers.index('Status')
                warden_idx = headers.index('Incharge/Warden')
                
                for row in reader:
                    if not row or len(row) <= max(room_no_idx, floor_idx, room_type_idx):
                        continue
                    room_number = row[room_no_idx].strip()
                    floor_str = row[floor_idx].strip()
                    room_type_str = row[room_type_idx].strip()
                    capacity_str = row[capacity_idx].strip()
                    status = row[status_idx].strip()
                    warden = row[warden_idx].strip() if warden_idx < len(row) else 'KEERTHI'
                    
                    if not room_number:
                        continue
                        
                    room = Room(
                        room_number=room_number,
                        floor=parse_floor(floor_str),
                        room_type=parse_room_type(room_type_str),
                        capacity=int(capacity_str) if capacity_str.isdigit() else 8,
                        status=status if status else 'Available',
                        hostel_block=warden if warden else 'KEERTHI'
                    )
                    db.session.add(room)
            db.session.commit()
            print("Rooms imported successfully!")
        else:
            print("rooms.csv not found!")

        # Helper: Build room leaders lookup map by reading student CSVs first
        room_leaders = {}
        student_csvs = [
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'student_data.csv'),
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'final_year_data.csv')
        ]
        
        for path in student_csvs:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    headers = [h.strip() for h in next(reader)]
                    
                    room_no_idx = headers.index('Room No') if 'Room No' in headers else -1
                    name_idx = headers.index('Student Name') if 'Student Name' in headers else -1
                    phone_idx = headers.index('Student Phone') if 'Student Phone' in headers else -1
                    leader_idx = headers.index('Room Leader') if 'Room Leader' in headers else -1
                    leader_phone_idx = headers.index('Leader Phone') if 'Leader Phone' in headers else -1
                    
                    for row in reader:
                        if not row or len(row) <= max(room_no_idx, name_idx, leader_idx):
                            continue
                        room_no = row[room_no_idx].strip()
                        name = row[name_idx].strip()
                        phone = row[phone_idx].strip() if phone_idx != -1 else ""
                        is_leader = row[leader_idx].strip().lower()
                        leader_phone = row[leader_phone_idx].strip() if leader_phone_idx != -1 else ""
                        
                        if room_no and ('lead' in is_leader or is_leader == 'leads'):
                            room_leaders[room_no] = (name, leader_phone if leader_phone else phone)

        # Helper to seed students from a given CSV
        def import_students(csv_path, year_val):
            if not os.path.exists(csv_path):
                print(f"{os.path.basename(csv_path)} not found.")
                return
            
            print(f"Importing students from {os.path.basename(csv_path)}...")
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = [h.strip() for h in next(reader)]
                
                room_no_idx = headers.index('Room No')
                col_idx = headers.index('College Block')
                pro_idx = headers.index('Program')
                htno_idx = headers.index('Hall Ticket No')
                name_idx = headers.index('Student Name')
                father_idx = headers.index('Father Name') if 'Father Name' in headers else -1
                phone_idx = headers.index('Student Phone') if 'Student Phone' in headers else -1
                
                for row in reader:
                    if not row or len(row) <= max(room_no_idx, htno_idx, name_idx):
                        continue
                    room_no = row[room_no_idx].strip()
                    col = row[col_idx].strip()
                    pro = row[pro_idx].strip()
                    htno = row[htno_idx].strip()
                    name = row[name_idx].strip()
                    father_name = row[father_idx].strip() if father_idx != -1 else "N/A"
                    phone = row[phone_idx].strip() if phone_idx != -1 else "N/A"
                    
                    if not htno or not name:
                        continue
                        
                    # Check if user already exists
                    existing = User.query.filter_by(username=htno).first()
                    if existing:
                        continue
                        
                    # Find room
                    room = Room.query.filter_by(room_number=room_no).first()
                    
                    # Create student User
                    student = User(
                        username=htno,
                        role='student',
                        name=name,
                        phone=phone if phone else "N/A",
                        status='approved'
                    )
                    student.set_password("password123")
                    db.session.add(student)
                    db.session.flush()
                    
                    # Room leader lookup
                    leader_name, leader_phone = room_leaders.get(room_no, ("N/A", "N/A"))
                    
                    # Create Profile
                    profile = StudentProfile(
                        user_id=student.id,
                        branch=f"{col} - {pro}" if (col and pro) else (col if col else "N/A"),
                        year=year_val,
                        parent_phone="N/A",
                        room_id=room.id if room else None,
                        room_leader_name=leader_name,
                        room_leader_phone=leader_phone,
                        collage_status="IN CLG",
                        tuition_fee_status="paid",
                        hostel_fee_status="paid",
                        remarks=f"Father Name: {father_name}"
                    )
                    db.session.add(profile)
            db.session.commit()
            print(f"Students from {os.path.basename(csv_path)} imported successfully!")

        # Import 3rd Year and Final Year students
        import_students(student_csvs[0], 3)
        import_students(student_csvs[1], 4)

        # Import Vacated students
        vacated_csv_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'vacated_students.csv')
        if os.path.exists(vacated_csv_path):
            print("Importing vacated students...")
            with open(vacated_csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                headers = [h.strip() for h in next(reader)]
                
                roll_idx = headers.index('ROLL NO')
                room_no_idx = headers.index('ROOM NO')
                name_idx = headers.index('NAME OF THE STUDENT')
                phone_idx = headers.index('PH NO') if 'PH NO' in headers else -1
                reason_idx = headers.index('REASON FOR VACATING') if 'REASON FOR VACATING' in headers else -1
                address_idx = headers.index('ADDRESS THEY ARE STAYING') if 'ADDRESS THEY ARE STAYING' in headers else -1
                month_idx = headers.index('VACATED MONTH&YEAR') if 'VACATED MONTH&YEAR' in headers else -1
                remarks_idx = headers.index('REMARKS') if 'REMARKS' in headers else -1
                
                for row in reader:
                    if not row or len(row) <= max(roll_idx, name_idx):
                        continue
                    roll = row[roll_idx].strip()
                    room_no = row[room_no_idx].strip()
                    name = row[name_idx].strip()
                    phone = row[phone_idx].strip() if phone_idx != -1 else "N/A"
                    reason = row[reason_idx].strip() if reason_idx != -1 else ""
                    address = row[address_idx].strip() if address_idx != -1 else ""
                    month = row[month_idx].strip() if month_idx != -1 else ""
                    remarks_val = row[remarks_idx].strip() if remarks_idx != -1 else ""
                    
                    if not roll or not name:
                        continue
                        
                    existing = User.query.filter_by(username=roll).first()
                    if existing:
                        continue
                        
                    student = User(
                        username=roll,
                        role='student',
                        name=name,
                        phone=phone if phone else "N/A",
                        status='approved'
                    )
                    student.set_password("password123")
                    db.session.add(student)
                    db.session.flush()
                    
                    remark_text = f"Vacated. Reason: {reason} | Stay Address: {address} | Month: {month} | Remarks: {remarks_val}"
                    profile = StudentProfile(
                        user_id=student.id,
                        branch="N/A",
                        year=4 if roll.startswith('23') else 3,
                        parent_phone="N/A",
                        room_id=None, # Vacated means no room
                        room_leader_name="N/A",
                        room_leader_phone="N/A",
                        collage_status="VACATED",
                        tuition_fee_status="paid",
                        hostel_fee_status="paid",
                        remarks=remark_text
                    )
                    db.session.add(profile)
            db.session.commit()
            print("Vacated students imported successfully!")
        else:
            print("vacated_students.csv not found.")

        # Seed Mock Students for Year 1 and Year 2 to prevent empty pages
        print("Seeding mock students for Year 1 and Year 2...")
        mock_students = [
            {"username": "26B21A0501", "name": "Aditya Vardhan", "year": 1, "room_no": "106", "branch": "CSM"},
            {"username": "26B21A0502", "name": "Bhavana Reddy", "year": 1, "room_no": "106", "branch": "CAI"},
            {"username": "26B21A0503", "name": "Chaitanya Krishna", "year": 1, "room_no": "106", "branch": "AID"},
            {"username": "26B21A0504", "name": "Divya Sri", "year": 1, "room_no": "106", "branch": "CSD"},
            {"username": "25B21A0501", "name": "Eswar Prasad", "year": 2, "room_no": "238", "branch": "CSM"},
            {"username": "25B21A0502", "name": "Fathima Begum", "year": 2, "room_no": "238", "branch": "CAI"},
            {"username": "25B21A0503", "name": "Ganesh Kumar", "year": 2, "room_no": "238", "branch": "AID"},
            {"username": "25B21A0504", "name": "Harini Priya", "year": 2, "room_no": "238", "branch": "CSD"},
        ]
        for ms in mock_students:
            existing = User.query.filter_by(username=ms["username"]).first()
            if not existing:
                student = User(
                    username=ms["username"],
                    role='student',
                    name=ms["name"],
                    phone="9876543210",
                    status='approved'
                )
                student.set_password("password123")
                db.session.add(student)
                db.session.flush()
                room = Room.query.filter_by(room_number=ms["room_no"]).first()
                profile = StudentProfile(
                    user_id=student.id,
                    branch=ms["branch"],
                    year=ms["year"],
                    parent_phone="9012345678",
                    room_id=room.id if room else None,
                    room_leader_name="N/A",
                    room_leader_phone="N/A",
                    collage_status="IN CLG",
                    tuition_fee_status="paid",
                    hostel_fee_status="paid",
                    remarks="Mock seeded student"
                )
                db.session.add(profile)
        db.session.commit()
        print("Mock students seeded successfully!")

        # Update room status based on occupants
        rooms = Room.query.all()
        for room in rooms:
            occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
                .join(User)\
                .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
                .scalar()
            if occupied_count >= room.capacity:
                room.status = 'Full'
            elif occupied_count > 0:
                room.status = 'Available' # Part occupied
            else:
                room.status = 'Available' # Empty
        db.session.commit()
        print("Room statuses updated successfully!")

        print("Generating documents...")
        from generate_documents import generate_all
        generate_all()
        
        print("Building AI RAG Vector Index...")
        from app.services.rag_engine import build_vector_store
        build_vector_store()
        print("AI RAG Vector Index compiled successfully!")

        print("Seeding Emergency Contacts...")
        contacts = [
            EmergencyContact(name="Pravalika Mam", role="4th Year Coordinator", phone="+91 98851 40848"),
            EmergencyContact(name="Keerthana Mam", role="Coordinator", phone="+91 83749 34547"),
            EmergencyContact(name="Doctor", role="Medical Emergency", phone="+91 98480 95182"),
            EmergencyContact(name="Dharani Mam", role="Hostel Warden", phone="+91 81064 36976"),
            EmergencyContact(name="Aparna", role="Student Coordinator", phone="+91 95056 01286")
        ]
        db.session.bulk_save_objects(contacts)
        db.session.commit()
        print("Emergency Contacts seeded successfully!")

if __name__ == "__main__":
    seed_database()
