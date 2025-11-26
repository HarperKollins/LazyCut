import os
import sqlite3
import datetime
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import google.generativeai as genai
from typing import List, Union
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Load Environment Variables
load_dotenv()

# Load API Key from Environment Variable (Secure)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # Fallback for local testing if not set, but ideally should be in env
    print("WARNING: GEMINI_API_KEY not found in environment variables.")

# Database File
DB_FILE = "lazycut.db"

# Daily Limit
DAILY_LIMIT = 1000

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
app = FastAPI(title="LazyCut Backend", version="1.0")

# --- Pydantic Models ---
class DirectorRequest(BaseModel):
    hardware_id: str
    transcript: str 

# --- AI LOGIC (Moved from Client) ---
def generate_director_cut_gemini(transcript_text):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: Missing API Key")
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Try to use the best available model with fallback
    # Prioritize models with better rate limits for free tier
    # Using actual model names from genai.list_models()
    model_names = [
        'gemini-2.5-flash',       # Latest stable flash model (recommended)
        'gemini-flash-latest',    # Latest flash release
        'gemini-pro-latest',      # Latest pro release
    ]
    
    model = None
    selected_model_name = None
    for model_name in model_names:
        try:
            model = genai.GenerativeModel(model_name)
            selected_model_name = model_name
            logger.info(f"Using model: {model_name}")
            break
        except Exception as e:
            logger.warning(f"Model {model_name} not available: {e}")
            continue
    
    if not model:
        # Last resort: list available models and use the first one
        try:
            available_models = genai.list_models()
            for m in available_models:
                if 'generateContent' in m.supported_generation_methods:
                    model = genai.GenerativeModel(m.name)
                    selected_model_name = m.name
                    logger.info(f"Using fallback model: {m.name}")
                    break
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No available models found: {str(e)}")
    
    prompt = f"""
    You are a Documentary Editor specializing in narrative coherence and storytelling.

    TRANSCRIPT:
    {transcript_text}

    EDITORIAL PHILOSOPHY:
    Your priority is NARRATIVE FLOW and COHERENCE. Create a story that makes sense, not just viral moments.

    GROUPING RULES:
    1. **Think in Paragraphs**: Group related sentences into logical units, not individual sentences
    2. **Golden Take Selection**: If multiple takes of the same point exist, select the BEST delivery (clearest, most confident, no stutters)
    3. **Setup-Punchline Rule**: NEVER cut the setup without the punchline. Complete thoughts only.
    4. **No Mid-Thought Cuts**: Each idea must be complete before moving to the next
    5. **Remove Redundancy**: If the speaker repeats themselves, keep only the best version

    SELECTION PROCESS:
    Step 1: Identify the main narrative arc - what's the story being told?
    Step 2: Group sentences into coherent paragraphs (related ideas together)
    Step 3: For each paragraph, select the "Golden Take" - best delivery, no false starts
    Step 4: Ensure logical flow between paragraphs - does B follow A naturally?
    Step 5: Remove all filler, "umms", false starts, and redundant takes

    NARRATIVE STRUCTURE:
    - Introduction: What's this about?
    - Development: Main points in logical order
    - Conclusion: Wrap up or call-to-action

    OUTPUT JSON:
    {{
      "selected_sequence": [0, 1, 2, 5, 6, 7, 10, 11],
      "seo_title": "Descriptive_Content_Title",
      "reasoning": "Para 1 (intro): [0-2], Para 2 (main point): [5-7], Para 3 (conclusion): [10-11]"
    }}

    CRITICAL: Maintain narrative coherence. Each clip should flow naturally into the next. No random jumps.
    """
    
    # Retry logic for rate limits
    import time
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Clean up potential markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            data = json.loads(text)
            
            # Handle new format with SEO title
            if isinstance(data, dict):
                indices = data.get("selected_sequence", [])
                seo_title = data.get("seo_title", "Viral_Edit")
                reasoning = data.get("reasoning", "")
                logger.info(f"AI Reasoning: {reasoning}")
                return {"indices": indices, "seo_title": seo_title}
            else:
                # Fallback for old format (just array)
                return {"indices": data, "seo_title": "Viral_Edit"}
        except Exception as e:
            error_str = str(e)
            
            # Check if it's a rate limit error
            if "429" in error_str or "quota" in error_str.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment and try again.")
            
            # Other errors
            logger.error(f"Gemini Error: {e}")
            raise HTTPException(status_code=500, detail=f"AI Processing Failed: {str(e)}")

# --- ENDPOINTS ---

@app.post("/process_script")
async def process_script(request: DirectorRequest):
    hw_id = request.hardware_id
    today = datetime.date.today().isoformat()
    
    # 1. Check Rate Limit
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT count FROM usage WHERE hardware_id = ? AND date = ?", (hw_id, today))
    row = cursor.fetchone()
    
    current_count = 0
    if row:
        current_count = row[0]
    
    if current_count >= DAILY_LIMIT:
        conn.close()
        logger.warning(f"Rate limit reached for {hw_id}")
        raise HTTPException(status_code=403, detail="Daily limit reached. Upgrade to Pro.")
    
    # 2. Process with AI
    try:
        # Call Gemini
        result = generate_director_cut_gemini(request.transcript)
        
        # 3. Update Usage Count
        new_count = current_count + 1
        cursor.execute('''
            INSERT INTO usage (hardware_id, date, count)
            VALUES (?, ?, ?)
            ON CONFLICT(hardware_id, date) DO UPDATE SET count = count + 1
        ''', (hw_id, today, new_count))
        conn.commit()
        conn.close()
        
        logger.info(f"Processed request for {hw_id}. Count: {new_count}/{DAILY_LIMIT}")
        return result  # Returns {"indices": [...], "seo_title": "..."}
        
    except Exception as e:
        conn.close()
        raise e

@app.get("/")
def health_check():
    return {"status": "online", "service": "LazyCut Backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
