import google.generativeai as genai
from flask import Blueprint, render_template, request, jsonify, session
from app.routes.auth import login_required, role_required
from app.services.rag_engine import query_rag
from app.services.db_chatbot import generate_and_execute_sql
from app.config import Config

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

@ai_bp.route('/assistant')
@login_required
def assistant():
    # Render the AI Assistant interface
    # Render with the selected mode if passed via query parameters
    selected_mode = request.args.get('mode', 'hostel_knowledge')
    return render_template('ai_assistant.html', current_mode=selected_mode)

@ai_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.json or {}
    message = data.get('message', '')
    mode = data.get('mode', 'hostel_knowledge')
    
    if not message.strip():
        return jsonify({'success': False, 'response': 'Please enter a valid query.'}), 400
        
    try:
        response_text = query_rag(message, mode)
        return jsonify({
            'success': True,
            'response': response_text
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'response': f"An error occurred while compiling AI response: {str(e)}"
        }), 500

@ai_bp.route('/admin_chat', methods=['POST'])
@login_required
@role_required(['admin', 'super_admin'])
def admin_chat():
    data = request.json or {}
    message = data.get('message', '')
    
    if not message.strip():
        return jsonify({'success': False, 'response': 'Please enter a valid query.'}), 400
        
    try:
        response_text = generate_and_execute_sql(message)
        return jsonify({
            'success': True,
            'response': response_text
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'response': f"An error occurred: {str(e)}"
        }), 500

@ai_bp.route('/explain_page', methods=['POST'])
@login_required
def explain_page():
    data = request.json or {}
    path = data.get('path', '')
    title = data.get('title', '')
    content = data.get('content', '')
    
    api_key = Config.GEMINI_API_KEY
    if not api_key or "your_gemini_api_key" in api_key:
        demo_explanation = f"""
### [Demo Mode] AI Page Explainer

It looks like a valid Gemini API Key is not configured in your `.env` file. Showing offline page explanation:

#### 1. Purpose of this page:
This is the **{title}** page (located at `{path}`). It allows users to view, manage, and interact with the relevant data records.

#### 2. Key Actions & Features:
- Interact with form elements, buttons, and directory details visible on the screen.
- Use the sidebar menu to navigate across different panels.
- Query specific records using the top universal search input.

---
> [!TIP]
> **Enable Live AI**: Replace `your_gemini_api_key_here` in your [`.env` file](file:///c:/Users/kastu/OneDrive/Desktop/hostel%20portal/.env) with a valid key from Google AI Studio.
"""
        return jsonify({
            'success': True,
            'response': demo_explanation
        })
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
You are the HostelOS AI Explainer.
Explain the current page being viewed by the user.

Page Details:
- Title: {title}
- URL Path: {path}
- Extracted Page Content:
{content}

Please provide a structured, easy-to-understand explanation containing:
1. The **Purpose** of this page.
2. How to **Use** the features or interact with the elements on this page.
3. An explanation of the **Data**, charts, cards, tables, or graphs that are visible on this page.
4. Recommendations/Next actions for the user based on this page.

Format the response using markdown (headers, bold text, bullet points). Keep the language friendly, clear, and professional.
"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return jsonify({
            'success': True,
            'response': response.text
        })
    except Exception as e:
        err_msg = str(e)
        err_lower = err_msg.lower()
        is_conn = any(x in err_lower for x in ["connection", "unreachable", "timeout", "dns", "gaierror", "host", "resolve", "network"])
        if "API_KEY_INVALID" in err_msg or "key not valid" in err_lower or is_conn:
            demo_explanation = f"""
### [Demo Mode] AI Page Explainer

Could not connect to Gemini (Internet offline or Invalid Key). Showing offline page explanation:

#### 1. Purpose of this page:
This is the **{title}** page (located at `{path}`).

#### 2. Key Actions & Features:
- Interact with form elements, buttons, and directory details visible on the screen.
- Use the sidebar menu to navigate across different panels.

---
> [!WARNING]
> **API Connection Unreachable**: Please verify your internet connection or update your [`.env` file](file:///c:/Users/kastu/OneDrive/Desktop/hostel%20portal/.env) with a valid Gemini key.
"""
            return jsonify({
                'success': True,
                'response': demo_explanation
            })
            
        return jsonify({
            'success': False,
            'response': f"Failed to generate explanation: {err_msg}"
        }), 500

