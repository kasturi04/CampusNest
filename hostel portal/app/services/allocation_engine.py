from app.database import db
from app.models import Room, StudentProfile, User

def suggest_room(year, preferred_type=None):
    """
    Suggests the best available room based on the student's year of study and room type preference.
    
    Year rules:
    - Year 1 -> Floor 1 (First Floor)
    - Year 2 -> Floor 2 (Second Floor)
    - Year 3 & 4 (Final Year) -> Floor 3 (Third Floor)
    
    Returns:
    - dict: {
        'success': bool,
        'room_number': str,
        'room_id': int,
        'room_type': str,
        'floor': int,
        'reason': str
      }
    """
    # 1. Determine target floor
    if year == 1:
        target_floors = [1]
        floor_desc = "First Floor (reserved for 1st Year new admissions)"
    elif year == 2:
        target_floors = [2]
        floor_desc = "Second Floor (reserved for 2nd Year students)"
    elif year in [3, 4]:
        target_floors = [3]
        floor_desc = "Third Floor (reserved for 3rd & Final Year students)"
    else:
        # Fallback for unexpected year values
        target_floors = [1, 2, 3]
        floor_desc = "Available student floors"

    # 2. Query rooms on target floor(s)
    # We want rooms that are 'Available' or not full
    rooms = Room.query.filter(
        Room.floor.in_(target_floors),
        Room.status != 'Maintenance'
    ).all()
    
    if not rooms:
        return {
            'success': False,
            'reason': f"No rooms are currently configured on the target floor: {floor_desc}."
        }
        
    # 3. Filter rooms by type preference if specified, and calculate vacancy
    valid_allocations = []
    
    for room in rooms:
        # Get count of approved residents in this room
        occupied_count = db.session.query(db.func.count(StudentProfile.user_id))\
            .join(User)\
            .filter(StudentProfile.room_id == room.id, User.status == 'approved')\
            .scalar()
            
        vacancy_count = room.capacity - occupied_count
        
        if vacancy_count > 0:
            valid_allocations.append({
                'room': room,
                'vacancy_count': vacancy_count,
                'occupied_count': occupied_count
            })
            
    if not valid_allocations:
        return {
            'success': False,
            'reason': f"All rooms on the designated floor ({floor_desc}) are fully occupied or under maintenance."
        }
        
    # 4. Attempt to match room type preference
    preferred_allocations = []
    if preferred_type:
        preferred_allocations = [a for a in valid_allocations if a['room'].room_type.lower() == preferred_type.lower()]
        
    # If we found matches with preferred type, use them. Otherwise, fallback to other types on same floor.
    is_fallback_type = False
    if preferred_allocations:
        candidates = preferred_allocations
    else:
        candidates = valid_allocations
        if preferred_type:
            is_fallback_type = True
            
    # Sort candidates by vacancy count descending (suggest room with most vacancy first)
    # And then room number ascending for stable sort
    candidates.sort(key=lambda x: (-x['vacancy_count'], x['room'].room_number))
    
    best_candidate = candidates[0]
    selected_room = best_candidate['room']
    
    # Formulate explanatory reason
    reason = f"Allocated Room {selected_room.room_number} on Floor {selected_room.floor}."
    
    if is_fallback_type and preferred_type:
        reason += f" Note: Your preferred room type '{preferred_type}' was not available on your year's designated floor, so a '{selected_room.room_type}' room was allocated as a fallback."
    else:
        reason += f" This aligns with your year rules ({floor_desc}) and your preferred room type ('{selected_room.room_type}')."
        
    return {
        'success': True,
        'room_number': selected_room.room_number,
        'room_id': selected_room.id,
        'room_type': selected_room.room_type,
        'floor': selected_room.floor,
        'reason': reason
    }
