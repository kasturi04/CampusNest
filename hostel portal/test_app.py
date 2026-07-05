import unittest
from app import create_app, db
from app.models import User, StudentProfile, Room, Complaint, Attendance
from app.services.allocation_engine import suggest_room
from datetime import date

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret'
    GEMINI_API_KEY = ''

class HostelOSTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app using TestConfig to keep test environment isolated
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Seed basic rooms for allocation tests
        # Floor 1: Room 101 (AC, 8 capacity)
        # Floor 2: Room 201 (Normal, 8 capacity)
        r101 = Room(room_number="101", floor=1, room_type="AC", capacity=8, status="Available")
        r201 = Room(room_number="201", floor=2, room_type="Normal", capacity=8, status="Available")
        db.session.add(r101)
        db.session.add(r201)
        db.session.commit()
        
        # Seed an admin user
        self.admin = User(username="admin", role="admin", name="Admin Test", phone="1234")
        self.admin.set_password("adminpw")
        db.session.add(self.admin)
        
        # Seed a staff electrician user
        self.electrician = User(username="electrician", role="staff", name="Electrician Test", phone="12345")
        self.electrician.set_password("staffpw")
        db.session.add(self.electrician)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_student_registration_flow(self):
        # Test registering a student
        response = self.client.post('/register', data={
            'student_name': 'Test Student',
            'roll_number': 'ROLL123',
            'branch': 'CSM',
            'year': '1',
            'phone_number': '1111111111',
            'parent_phone_number': '2222222222',
            'room_number': '101',
            'room_leader_name': 'Leader Name',
            'room_leader_phone_number': '3333333333',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        
        # Check student created
        student = User.query.filter_by(username='ROLL123').first()
        self.assertIsNotNone(student)
        self.assertEqual(student.status, 'pending') # Must be pending
        
        # Confirm student cannot login while pending
        login_res = self.client.post('/login', data={
            'username': 'ROLL123',
            'password': 'password123',
            'role': 'student'
        })
        self.assertIn(b'pending approval', login_res.data)

    def test_admin_registration_flow(self):
        # Test registering an admin
        response = self.client.post('/register', data={
            'role': 'admin',
            'student_name': 'Test Warden',
            'phone_number': '5555555555',
            'username': 'warden_test',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        
        # Check admin created
        admin = User.query.filter_by(username='warden_test').first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.role, 'admin')
        self.assertEqual(admin.status, 'approved') # Must be approved immediately
        
        # Confirm admin can login directly
        login_res = self.client.post('/login', data={
            'username': 'warden_test',
            'password': 'password123',
            'role': 'admin'
        }, follow_redirects=True)
        self.assertIn(b'Welcome back, Test Warden!', login_res.data)

    def test_smart_allocation_engine(self):
        # Year 1 Student requesting AC
        rec1 = suggest_room(1, "AC")
        self.assertTrue(rec1['success'])
        self.assertEqual(rec1['room_number'], '101')
        
        # Year 2 Student requesting Normal
        rec2 = suggest_room(2, "Normal")
        self.assertTrue(rec2['success'])
        self.assertEqual(rec2['room_number'], '201')

    def test_complaint_auto_routing(self):
        # Create student and assign bed
        student = User(username='ROLL777', role='student', name='Test Resident', phone='5555', status='approved')
        student.set_password('pw')
        db.session.add(student)
        db.session.commit()
        
        # Simulate filing an electrical complaint
        with self.client.session_transaction() as sess:
            sess['user_id'] = student.id
            sess['role'] = 'student'
            sess['name'] = student.name
            
        res = self.client.post('/complaints/submit', data={
            'category': 'Electrical',
            'title': 'Light flicker',
            'description': 'Light in room flickers constantly.'
        }, follow_redirects=True)
        
        # Check routing
        complaint = Complaint.query.filter_by(student_id=student.id).first()
        self.assertIsNotNone(complaint)
        self.assertEqual(complaint.status, 'Pending')
        self.assertEqual(complaint.assignment.staff.username, 'admin')

        # Check notification was created for admin
        from app.models import Notification
        notif = Notification.query.filter_by(user_id=self.admin.id).first()
        self.assertIsNotNone(notif)
        self.assertIn("Test Resident", notif.message)

        # Test resolving complaint
        res_resolve = self.client.post(f'/complaints/resolve/{complaint.id}', follow_redirects=True)
        self.assertEqual(complaint.status, 'Resolved')
        self.assertEqual(complaint.assignment.staff_notes, "Resolved and confirmed by student.")

        # Check resolve notification was created for admin
        res_notif = Notification.query.filter(Notification.user_id == self.admin.id, Notification.message.contains('Resolved')).first()
        self.assertIsNotNone(res_notif)

    def test_attendance_marking(self):
        student = User(username='ROLL888', role='student', name='Test Resident 2', phone='5555', status='approved')
        student.set_password('pw')
        db.session.add(student)
        db.session.flush()
        profile = StudentProfile(user_id=student.id, branch='CS', year=1, parent_phone='1234')
        db.session.add(profile)
        db.session.commit()
        
        # Mark present
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin.id
            sess['role'] = 'admin'
            
        res = self.client.post(f'/attendance/mark?year=1&date={date.today().strftime("%Y-%m-%d")}', data={
            f'status_{student.id}': 'Present',
            f'remarks_{student.id}': 'On time'
        }, follow_redirects=True)
        
        att = Attendance.query.filter_by(student_id=student.id).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.status, 'Present')
        self.assertEqual(att.remarks, 'On time')

    def test_student_emergency_contacts_access(self):
        from app.models import EmergencyContact
        contact = EmergencyContact(name="Test Coord", role="Test Role", phone="12345")
        db.session.add(contact)
        db.session.commit()

        student = User(username='STUDENT999', role='student', name='Test Student999', phone='5555', status='approved')
        student.set_password('pw')
        db.session.add(student)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['user_id'] = student.id
            sess['role'] = 'student'
            sess['name'] = student.name

        response = self.client.get('/student/emergency-contacts')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Coord', response.data)
        self.assertIn(b'Test Role', response.data)
        self.assertIn(b'12345', response.data)

        # Check student cannot POST to admin emergency contacts route
        add_res = self.client.post('/admin/emergency-contacts/add', data={
            'name': 'Hack Name',
            'role': 'Hack Role',
            'phone': '00000'
        })
        self.assertEqual(add_res.status_code, 302)

    def test_admin_emergency_contacts_crud(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin.id
            sess['role'] = 'admin'
            sess['name'] = self.admin.name

        response = self.client.post('/admin/emergency-contacts/add', data={
            'name': 'New Admin Contact',
            'role': 'Admin Role',
            'phone': '99999'
        }, follow_redirects=True)
        self.assertIn(b'New Admin Contact', response.data)

        from app.models import EmergencyContact
        contact = EmergencyContact.query.filter_by(name='New Admin Contact').first()
        self.assertIsNotNone(contact)

        edit_res = self.client.post(f'/admin/emergency-contacts/edit/{contact.id}', data={
            'name': 'Updated Admin Contact',
            'role': 'Updated Role',
            'phone': '88888'
        }, follow_redirects=True)
        self.assertIn(b'Updated Admin Contact', edit_res.data)

        delete_res = self.client.post(f'/admin/emergency-contacts/delete/{contact.id}', follow_redirects=True)
        self.assertIn(b'deleted successfully', delete_res.data)
        self.assertIsNone(EmergencyContact.query.get(contact.id))

if __name__ == '__main__':
    unittest.main()
