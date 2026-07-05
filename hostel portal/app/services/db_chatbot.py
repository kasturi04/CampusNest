import google.generativeai as genai
from flask import current_app
from app.database import db
from sqlalchemy import text
from app.config import Config
import re
from datetime import date

DB_SCHEMA_INFO = """
You are an expert SQLite developer for HostelOS (a Hostel Management System).
Write a valid SQLite SELECT query that answers the user's question.
Do NOT output any markdown formatting (like ```sql), explanation, or other text. Output ONLY the raw SQL query.
If the question is a greeting, small talk, or completely unrelated to querying hostel records, start your response with 'CHAT: ' followed by your response.

Here are the database tables and columns:

1. rooms
   - id (INTEGER, PRIMARY KEY)
   - room_number (TEXT, unique room identifier e.g., '101', '201')
   - floor (INTEGER, floor level e.g. 1 for 1st, 2 for 2nd)
   - room_type (TEXT, 'Normal', 'Executive', 'AC')
   - capacity (INTEGER, total beds available in the room)
   - status (TEXT, 'Available', 'Full', 'Reserved', 'Maintenance')
   - hostel_block (TEXT, block name e.g., 'KEERTHI')

2. users
   - id (INTEGER, PRIMARY KEY)
   - username (TEXT, UNIQUE. This is the Roll Number for student accounts, and name/username for others)
   - role (TEXT, 'super_admin', 'admin', 'staff', 'student')
   - name (TEXT, full name of the user)
   - phone (TEXT, student or user mobile number)
   - status (TEXT, registration status: 'pending', 'approved', 'rejected')
   - created_at (DATETIME, registration date)

3. student_profiles (extended details for students, joins users on user_id)
   - user_id (INTEGER, PRIMARY KEY, FOREIGN KEY to users.id)
   - branch (TEXT, branch/program of study, e.g., 'CSM', 'CAI')
   - year (INTEGER, year of study: 1, 2, 3, 4)
   - parent_phone (TEXT, parents' contact number)
   - room_id (INTEGER, FOREIGN KEY to rooms.id, room the student is staying in)
   - room_leader_name (TEXT, name of the room leader)
   - room_leader_phone (TEXT, phone number of the room leader)
   - collage_status (TEXT, college status: 'IN CLG', 'VACATED', etc.)
   - tuition_fee_status (TEXT, 'paid', 'unpaid')
   - hostel_fee_status (TEXT, 'paid', 'unpaid')
   - remarks (TEXT, admin notes or general remarks)

4. attendance
   - id (INTEGER, PRIMARY KEY)
   - student_id (INTEGER, FOREIGN KEY to users.id)
   - marked_by_id (INTEGER, FOREIGN KEY to users.id)
   - attendance_date (DATE, the date of attendance e.g. '2026-07-03')
   - status (TEXT, 'Present', 'Absent', 'Leave')
   - remarks (TEXT)

5. complaints
   - id (INTEGER, PRIMARY KEY)
   - student_id (INTEGER, FOREIGN KEY to users.id)
   - category (TEXT, e.g., 'Fan', 'Electrical', 'Water', 'Plumbing', 'Mess', 'Cleaning', 'Other')
   - title (TEXT)
   - description (TEXT)
   - status (TEXT, 'Pending', 'Assigned', 'In Progress', 'Resolved')
   - created_at (DATETIME)
   - updated_at (DATETIME)

6. complaint_assignments
   - id (INTEGER, PRIMARY KEY)
   - complaint_id (INTEGER, FOREIGN KEY to complaints.id)
   - staff_id (INTEGER, FOREIGN KEY to users.id)
   - assigned_at (DATETIME)
   - resolved_at (DATETIME)
   - staff_notes (TEXT)

Important SQLite constraints & guidance:
- When calculating room vacancy, it is capacity minus count of approved students in that room:
  vacancy = capacity - (SELECT COUNT(*) FROM student_profiles sp JOIN users u ON sp.user_id = u.id WHERE sp.room_id = rooms.id AND u.status = 'approved')
- When filtering for approved students, always verify: role = 'student' AND status = 'approved'
- Today's date can be fetched using DATE('now') or date in YYYY-MM-DD format.
- To do case-insensitive string matches, use LIKE '%name%'.
- Join tables carefully.
- For student details search by roll number, write a SELECT query that gathers information from users, student_profiles, rooms, attendance, and complaints tables if required to return all requested fields.
"""

def parse_query_offline(query_str):
    q = query_str.lower().strip()
    
    # 1. How many students are staying in the hostel?
    if "how many students" in q and "staying" in q or "total students" in q:
        sql = "SELECT COUNT(*) FROM users WHERE role='student' AND status='approved'"
        res = db.session.execute(text(sql)).scalar()
        return f"There are currently **{res}** approved students staying in the hostel."
        
    # 2. How many rooms are vacant?
    if "how many rooms" in q and "vacant" in q or "vacant rooms count" in q:
        sql = """
            SELECT COUNT(*) FROM rooms 
            WHERE (
                SELECT COUNT(*) FROM student_profiles 
                JOIN users ON student_profiles.user_id = users.id 
                WHERE student_profiles.room_id = rooms.id AND users.status = 'approved'
            ) < rooms.capacity
        """
        res = db.session.execute(text(sql)).scalar()
        return f"There are **{res}** rooms with at least one vacant bed in the hostel."

    # 3. Which rooms are full?
    if "rooms" in q and "full" in q:
        sql = """
            SELECT room_number FROM rooms 
            WHERE (
                SELECT COUNT(*) FROM student_profiles 
                JOIN users ON student_profiles.user_id = users.id 
                WHERE student_profiles.room_id = rooms.id AND users.status = 'approved'
            ) >= rooms.capacity
        """
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "None of the hostel rooms are completely full."
        rooms_list = ", ".join([r[0] for r in rows])
        return f"The following rooms are fully occupied: **{rooms_list}**."

    # 4. Show all Executive rooms.
    if "executive" in q and "rooms" in q:
        sql = "SELECT room_number, hostel_block FROM rooms WHERE room_type='Executive'"
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "There are no Executive rooms configured in the database."
        rooms_list = ", ".join([f"Room {r[0]} ({r[1]} Block)" for r in rows])
        return f"Executive rooms: **{rooms_list}**."

    # 5. Show all Normal rooms.
    if "normal" in q and "rooms" in q:
        sql = "SELECT room_number, hostel_block FROM rooms WHERE room_type='Normal'"
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "There are no Normal rooms configured in the database."
        rooms_list = ", ".join([f"Room {r[0]} ({r[1]} Block)" for r in rows])
        return f"Normal rooms: **{rooms_list}**."

    # 6. Show all AC rooms.
    if "ac" in q and "rooms" in q:
        sql = "SELECT room_number, hostel_block FROM rooms WHERE room_type='AC'"
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "There are no AC rooms configured in the database."
        rooms_list = ", ".join([f"Room {r[0]} ({r[1]} Block)" for r in rows])
        return f"AC rooms: **{rooms_list}**."

    # 7. Show all rooms in Keerthi Block.
    if "keerthi" in q:
        sql = "SELECT room_number FROM rooms WHERE hostel_block='KEERTHI'"
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "No rooms found in Keerthi Block."
        rooms_list = ", ".join([r[0] for r in rows])
        return f"Rooms in Keerthi Block: **{rooms_list}**."

    # 8. Which students are in Room X?
    match_room = re.search(r'room\s+(\d+)', q)
    if match_room and ("student" in q or "who is in" in q or "who are in" in q):
        room_no = match_room.group(1)
        sql = f"""
            SELECT name, username FROM users 
            JOIN student_profiles ON users.id = student_profiles.user_id 
            JOIN rooms ON student_profiles.room_id = rooms.id 
            WHERE rooms.room_number = '{room_no}' AND users.status = 'approved'
        """
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return f"There are no approved students assigned to Room {room_no}."
        students_list = ", ".join([f"{r[0]} ({r[1]})" for r in rows])
        return f"Students in Room {room_no}: **{students_list}**."

    # 10. Which rooms have vacant beds?
    if "vacant beds" in q or "rooms with vacant beds" in q:
        sql = """
            SELECT room_number, capacity - (
                SELECT COUNT(*) FROM student_profiles 
                JOIN users ON student_profiles.user_id = users.id 
                WHERE student_profiles.room_id = rooms.id AND users.status = 'approved'
            ) AS vacant FROM rooms WHERE vacant > 0
        """
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "No rooms have vacant beds available."
        rooms_list = ", ".join([f"Room {r[0]} ({r[1]} vacant)" for r in rows])
        return f"Rooms with vacant beds: **{rooms_list}**."

    # 11. Show all pending complaints / complaints pending
    if "pending complaints" in q or ("complaints" in q and "pending" in q):
        sql = "SELECT id, title, category FROM complaints WHERE status='Pending'"
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "There are no pending complaints tickets."
        complaints_list = "\n".join([f"- Ticket #{r[0]}: **{r[1]}** (Category: {r[2]})" for r in rows])
        return f"Pending complaints:\n{complaints_list}"

    # 12. How many students are absent today?
    if "absent today" in q or "absent students today" in q:
        sql = f"SELECT COUNT(*) FROM attendance WHERE status='Absent' AND attendance_date = '{date.today().strftime('%Y-%m-%d')}'"
        res = db.session.execute(text(sql)).scalar()
        return f"There are **{res}** students absent today ({date.today().strftime('%Y-%m-%d')})."

    # 13. Show absent students in Final Year.
    if "absent" in q and ("final year" in q or "4th year" in q):
        sql = f"""
            SELECT name, username FROM users 
            JOIN student_profiles ON users.id = student_profiles.user_id 
            JOIN attendance ON users.id = attendance.student_id 
            WHERE attendance.status='Absent' AND student_profiles.year = 4 
            AND attendance.attendance_date = '{date.today().strftime('%Y-%m-%d')}'
        """
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "There are no absent Final Year students today."
        students_list = ", ".join([f"{r[0]} ({r[1]})" for r in rows])
        return f"Absent Final Year students today: **{students_list}**."

    # 14. Which rooms have absent students today?
    if "rooms" in q and "absent" in q:
        sql = f"""
            SELECT DISTINCT room_number FROM rooms 
            JOIN student_profiles ON rooms.id = student_profiles.room_id 
            JOIN users ON student_profiles.user_id = users.id 
            JOIN attendance ON users.id = attendance.student_id 
            WHERE attendance.status='Absent' AND attendance.attendance_date = '{date.today().strftime('%Y-%m-%d')}'
        """
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "No rooms have absent students today."
        rooms_list = ", ".join([r[0] for r in rows])
        return f"Rooms with absent students today: **{rooms_list}**."

    # 15. Show attendance percentage for each year.
    if "attendance percentage" in q:
        years = [1, 2, 3, 4]
        response_parts = []
        for yr in years:
            sql_total = f"""
                SELECT COUNT(*) FROM attendance 
                JOIN student_profiles ON attendance.student_id = student_profiles.user_id 
                WHERE student_profiles.year = {yr}
            """
            sql_present = f"""
                SELECT COUNT(*) FROM attendance 
                JOIN student_profiles ON attendance.student_id = student_profiles.user_id 
                WHERE student_profiles.year = {yr} AND attendance.status = 'Present'
            """
            total = db.session.execute(text(sql_total)).scalar() or 0
            present = db.session.execute(text(sql_present)).scalar() or 0
            pct = round((present / total * 100), 1) if total > 0 else 0.0
            response_parts.append(f"- Year {yr}: **{pct}%** ({present}/{total} logs)")
        return "Attendance percentage for each year:\n" + "\n".join(response_parts)

    # 16. Which room has the highest occupancy?
    if "highest occupancy" in q or "occupancy room" in q:
        sql = """
            SELECT room_number, (
                SELECT COUNT(*) FROM student_profiles 
                JOIN users ON student_profiles.user_id = users.id 
                WHERE student_profiles.room_id = rooms.id AND users.status = 'approved'
            ) AS occupied FROM rooms 
            ORDER BY occupied DESC LIMIT 1
        """
        row = db.session.execute(text(sql)).fetchone()
        if not row:
            return "No occupancy records found."
        return f"Room with highest occupancy: **Room {row[0]}** (occupied spaces: {row[1]})."

    # 17. Show available rooms for Final Year students.
    if "available rooms" in q and ("final year" in q or "4th year" in q):
        sql = """
            SELECT room_number FROM rooms 
            WHERE floor = 4 AND (
                SELECT COUNT(*) FROM student_profiles 
                JOIN users ON student_profiles.user_id = users.id 
                WHERE student_profiles.room_id = rooms.id AND users.status = 'approved'
            ) < rooms.capacity
        """
        rows = db.session.execute(text(sql)).fetchall()
        if not rows:
            return "No available rooms found for Final Year students."
        rooms_list = ", ".join([r[0] for r in rows])
        return f"Available rooms for Final Year students: **{rooms_list}**."

    # 18. General greeting/help message
    if q in ["hello", "hi", "hey", "help", "who are you", "what can you do"]:
        return (
            "Hello! I am CampusNest Live DB AI, your Hostel Management Assistant.\n\n"
            "In Demo Mode, I can query the live database to answer questions like:\n"
            "- *How many students are staying in the hostel?*\n"
            "- *How many rooms are vacant?*\n"
            "- *Which rooms are full?*\n"
            "- *Show all Executive rooms.*\n"
            "- *Show all rooms in Keerthi Block.*\n"
            "- *Which students are in Room 301?*\n"
            "- *Which rooms have vacant beds?*\n"
            "- *Show all pending complaints.*\n"
            "- *How many students are absent today?*\n"
            "- *Show absent students in Final Year.*\n"
            "- *Which rooms have absent students today?*\n"
            "- *Show attendance percentage for each year.*\n"
            "- *Which room has the highest occupancy?*\n"
            "- *Show available rooms for Final Year students.*"
        )

    # General configuration alert
    return (
        "Gemini API connection error or API Key is missing. "
        "Please check your internet connection or configure a valid GEMINI_API_KEY in your `.env` file to chat."
    )

def generate_and_execute_sql(user_query):
    # Configure Gemini
    api_key = Config.GEMINI_API_KEY
    if not api_key or "your_gemini_api_key" in api_key:
        return parse_query_offline(user_query)
    
    genai.configure(api_key=api_key)
    
    # 1. Ask Gemini to generate the SQL query
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=DB_SCHEMA_INFO
        )
        sql_response = model.generate_content(user_query).text.strip()
    except Exception as e:
        err_msg = str(e)
        err_lower = err_msg.lower()
        is_conn = any(x in err_lower for x in ["connection", "unreachable", "timeout", "dns", "gaierror", "host", "resolve", "network"])
        if "API_KEY_INVALID" in err_msg or "key not valid" in err_lower or is_conn:
            return parse_query_offline(user_query)
        return f"Error communicating with AI: {err_msg}"
    
    # 2. Check if it is a general chat response
    if sql_response.startswith("CHAT:"):
        return sql_response[5:].strip()
    
    # 3. Clean up the query string
    sql_query = sql_response.replace("```sql", "").replace("```", "").strip()
    
    # Simple check for injection
    cleaned_query = sql_query.lower()
    unsafe_keywords = ["insert ", "update ", "delete ", "drop ", "alter ", "create ", "replace ", "truncate "]
    if any(keyword in cleaned_query for keyword in unsafe_keywords):
        return "I am sorry, but I can only execute read-only queries on the database. The proposed operation was blocked for safety reasons."
    
    if not cleaned_query.startswith("select"):
        # If it doesn't look like a SQL query, it might be a text explanation or message
        return sql_response
        
    # 4. Execute the SQL query on SQLite
    try:
        result = db.session.execute(text(sql_query))
        if result.returns_rows:
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        else:
            rows = []
    except Exception as e:
        return f"Database query failed. Raw SQL attempted: `{sql_query}`. Error: {str(e)}"
        
    # 5. Synthesize the response using Gemini with the raw data
    summarization_prompt = f"""
You are the HostelOS Database Assistant. You have queried the live database.
User's Question: {user_query}
Executed SQL Query: {sql_query}
Raw SQL Result Data: {str(rows)}

Formulate a concise, clear, and professional markdown response to the user.
If no data was found or the result is empty, inform the user clearly (e.g. "Student not found. Please check the roll number." or "No records match your query.").
When displaying multiple rows, use markdown tables or bullet points for readability.
If the query was about a specific student's details, display them beautifully in a key-value layout. Include details like Name, Roll, Room, Block, Attendance Today, Present/Absent days, etc. as returned by the SQL.
Do not mention the raw SQL query or technical database details in your final output unless explicitly asked.
"""
    try:
        s_model = genai.GenerativeModel("gemini-2.5-flash")
        response = s_model.generate_content(summarization_prompt)
        return response.text
    except Exception as e:
        # Fallback to direct Python formatting if network fails during summarization
        formatted_rows = "\n".join([f"- {str(row)}" for row in rows])
        return f"### Database Query Results (Offline/Connection Fallback)\n\n{formatted_rows}"
