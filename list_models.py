import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY not found in .env file")
    exit(1)

print(f"✅ API Key found: {api_key[:20]}...")
print("\n" + "="*60)
print("AVAILABLE GEMINI MODELS")
print("="*60 + "\n")

genai.configure(api_key=api_key)

try:
    models = genai.list_models()
    
    generation_models = []
    
    for model in models:
        # Check if model supports generateContent
        if 'generateContent' in model.supported_generation_methods:
            generation_models.append(model)
            print(f"✅ {model.name}")
            print(f"   Display Name: {model.display_name}")
            print(f"   Description: {model.description[:100]}..." if len(model.description) > 100 else f"   Description: {model.description}")
            print(f"   Supported Methods: {', '.join(model.supported_generation_methods)}")
            print()
    
    print("="*60)
    print(f"\nTotal models supporting generateContent: {len(generation_models)}")
    
    if generation_models:
        print("\n🎯 RECOMMENDED MODEL:")
        # Prefer flash models for speed and rate limits
        recommended = None
        for m in generation_models:
            if 'flash' in m.name.lower():
                recommended = m
                break
        
        if not recommended:
            recommended = generation_models[0]
        
        print(f"   {recommended.name}")
        print(f"   Reason: {'Fast and good rate limits' if 'flash' in recommended.name.lower() else 'First available model'}")
        
except Exception as e:
    print(f"❌ Error listing models: {e}")
