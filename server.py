import os
import sqlite3
import datetime
import json
import logging
from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
import google.generativeai as genai
from typing import List, Optional
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

# Securely load API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in environment variables.")

# Database File
DB_FILE = "lazycut.db"

# Limits
DAILY_LIMIT = 4
ADMIN_KEYS = ["harper_master_key_2025"]

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LazyCutServer")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            hardware_id TEXT,
            date TEXT,
            count INTEGER,
            PRIMARY KEY (hardware_id, date)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FASTAPI APP ---
app = FastAPI(title="LazyCut Backend", version="2.0")

# --- Pydantic Models ---
class DirectorRequest(BaseModel):
    hardware_id: str
    transcript: str
    token: Optional[str] = None

# --- AI LOGIC ---
def generate_director_cut_gemini(transcript_text):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: Missing API Key")
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Model Selection Strategy
    model_names = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    model = None
    
    for name in model_names:
        try:
            model = genai.GenerativeModel(name)
            break
        except:
            continue
            
    if not model:
        # Fallback to whatever is available
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    model = genai.GenerativeModel(m.name)
                    break
        except:
            pass

    if not model:
        raise HTTPException(status_code=500, detail="No AI models available.")

    prompt = f"""
    You are a Documentary Editor.
    TRANSCRIPT: {transcript_text}
    
    GOAL: Create a coherent narrative.
    RULES:
    1. Group related sentences.
    2. Select the best take if repeated.
    3. Ensure logical flow.
    4. Remove filler.
    
    OUTPUT JSON ONLY:
    {{
      "cut_list": [global_ids_of_selected_sentences],
      "seo_title": "Viral_Title_Here"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean markdown
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        
        data = json.loads(text)
        return data
    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Processing Failed: {str(e)}")

# --- ENDPOINTS ---
@app.post("/process_script")
async def process_script(request: DirectorRequest):
    hw_id = request.hardware_id
    token = request.token
    today = datetime.date.today().isoformat()
    
    # 1. Authorization & Rate Limiting
    is_admin = token in ADMIN_KEYS
    
    if not is_admin:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM usage WHERE hardware_id = ? AND date = ?", (hw_id, today))
        row = cursor.fetchone()
        current_count = row[0] if row else 0
        conn.close()
        
        if current_count >= DAILY_LIMIT:
            logger.warning(f"Rate limit reached for {hw_id}")
            raise HTTPException(status_code=403, detail="Daily Limit Reached")

    # 2. AI Processing
    result = generate_director_cut_gemini(request.transcript)
    
    # 3. Update Usage (if not admin)
    if not is_admin:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usage (hardware_id, date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(hardware_id, date) DO UPDATE SET count = count + 1
        ''', (hw_id, today))
        conn.commit()
        conn.close()
        
    return result

@app.get("/")
def health_check():
    return {"status": "online", "service": "LazyCut Backend v2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
