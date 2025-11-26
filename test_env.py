import os
from dotenv import load_dotenv

# Test if .env loads correctly
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    print(f"✅ API Key found: {api_key[:20]}...")
else:
    print("❌ API Key NOT found")
    
print(f"Current directory: {os.getcwd()}")
print(f".env file exists: {os.path.exists('.env')}")
