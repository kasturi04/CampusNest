import os
import fitz  # PyMuPDF
import google.generativeai as genai
from flask import current_app
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import Config

# Path to local FAISS index store
INDEX_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'instance', 'faiss_index')

def get_embeddings():
    """Initializes the Sentence Transformer embeddings model."""
    # Using a standard lightweight sentence transformer model
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def build_vector_store():
    """
    Reads all PDF files in the documents folder, chunks their text,
    embeds them, and saves the vector store locally using FAISS.
    """
    docs_dir = Config.DOCUMENTS_FOLDER
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir, exist_ok=True)
        
    pdf_files = [f for f in os.listdir(docs_dir) if f.endswith('.pdf')]
    if not pdf_files:
        print("No PDF files found in documents directory to index.")
        return False
        
    all_chunks = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    
    for filename in pdf_files:
        filepath = os.path.join(docs_dir, filename)
        try:
            doc = fitz.open(filepath)
            doc_text = ""
            for page in doc:
                doc_text += page.get_text()
                
            if doc_text.strip():
                # Split text into chunks
                chunks = text_splitter.create_documents(
                    texts=[doc_text],
                    metadatas=[{"source": filename}]
                )
                all_chunks.extend(chunks)
                print(f"Parsed {filename}: {len(chunks)} chunks generated.")
        except Exception as e:
            print(f"Error parsing file {filename}: {str(e)}")
            
    if not all_chunks:
        print("No text extracted from document PDFs.")
        return False
        
    print(f"Indexing {len(all_chunks)} chunks to FAISS...")
    embeddings = get_embeddings()
    vector_store = FAISS.from_documents(all_chunks, embeddings)
    
    # Ensure instance directory exists
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    vector_store.save_local(INDEX_PATH)
    print("FAISS Index created and saved successfully.")
    return True

def query_rag(user_query, assistant_mode="hostel_knowledge"):
    """
    Performs RAG search. Searches the FAISS index for relevant chunks,
    builds a contextual system prompt, and calls Gemini API.
    
    Assistant Modes:
    - hostel_knowledge: General queries about rules & guidelines
    - admission: Help with admissions processes and requirements
    - complaint_guidance: Suggestions/tips on resolving hostel complaints
    - room_recommendation: Explain allocation engine selections
    - notices: Clarification on active announcements/notices
    """
    # 1. Check if FAISS Index exists, if not build it
    if not os.path.exists(INDEX_PATH):
        success = build_vector_store()
        if not success:
            return "HostelOS RAG Error: No knowledge base documents have been indexed yet. Please upload PDF documentation."
            
    # 2. Load Vector Index and query matching chunks
    try:
        embeddings = get_embeddings()
        vector_store = FAISS.load_local(INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        matched_docs = vector_store.similarity_search(user_query, k=3)
        context = "\n\n".join([f"[Source: {doc.metadata.get('source')}]: {doc.page_content}" for doc in matched_docs])
    except Exception as e:
        context = "No specific rules found in local index."
        print(f"RAG Retrieval warning: {str(e)}")
        
    # 3. Configure Gemini API
    api_key = Config.GEMINI_API_KEY
    if not api_key or "your_gemini_api_key" in api_key:
        # Fallback if API key is not present
        return (
            f"[DEMO MODE - GEMINI_API_KEY is missing or invalid]\n\n"
            f"Here is the local information retrieved from our database/documents relating to your query:\n\n"
            f"{context}\n\n"
            f"Please configure a valid Gemini API Key in the `.env` file to enable full conversational intelligence."
        )
        
    genai.configure(api_key=api_key)
    
    # 4. Formulate System Prompts based on assistant mode
    prompts = {
        "hostel_knowledge": (
            "You are the HostelOS Rules & Guidelines Assistant. Answer the student's question based strictly on the provided context. "
            "If the information is not present in the context, politely mention that you do not have that specific rule in your handbook.\n\n"
            f"CONTEXT:\n{context}"
        ),
        "admission": (
            "You are the HostelOS Admissions Guide. Help students and parents with queries about eligibility, fee payments, and documentation requirements. "
            "Refer to the local rules context for specifics.\n\n"
            f"CONTEXT:\n{context}"
        ),
        "complaint_guidance": (
            "You are the HostelOS Maintenance & Complaint Assistant. Explain which staff handles which category, suggest troubleshooting tips "
            "(e.g., checking if switches are turned on, reporting plumbing immediately), and guide the student on filling ticket forms.\n\n"
            f"CONTEXT:\n{context}"
        ),
        "room_recommendation": (
            "You are the HostelOS Smart Allocation Explainer. Explain to the student why they were allocated a specific floor or room "
            "based on their Year rules (1st Year: Floor 1, 2nd Year: Floor 2, 3rd/4th Year: Floor 3) and room capacities.\n\n"
            f"CONTEXT:\n{context}"
        ),
        "notices": (
            "You are the HostelOS Announcement Assistant. Provide details and clarify announcements, events, and notices posted by the Warden.\n\n"
            f"CONTEXT:\n{context}"
        )
    }
    
    system_prompt = prompts.get(assistant_mode, prompts["hostel_knowledge"])
    
    # 5. Invoke Gemini API
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt
        )
        response = model.generate_content(user_query)
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "API_KEY_INVALID" in err_msg or "key not valid" in err_msg.lower():
            return (
                f"[GEMINI API KEY ERROR]\n\n"
                f"The configured Gemini API key is invalid. Please replace 'your_gemini_api_key_here' in your `.env` file with a valid Google Gemini API key.\n\n"
                f"Local retrieved context:\n{context}"
            )
        return f"Gemini API Error: {err_msg}. Retrieved Context:\n\n{context}"
