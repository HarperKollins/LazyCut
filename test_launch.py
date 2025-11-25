import sys
import os

print("Testing imports...")
try:
    import customtkinter
    print("✅ customtkinter loaded")
    import moviepy.editor
    print("✅ moviepy loaded")
    import whisper
    print("✅ whisper loaded")
    import google.generativeai
    print("✅ google.generativeai loaded")
    from core import LazyCutCore
    print("✅ core module loaded")
    from config import IS_WINDOWS
    print(f"✅ config loaded (Windows: {IS_WINDOWS})")
    
    # Try initializing core (lightweight check)
    core = LazyCutCore()
    print("✅ Core initialized")
    
    print("ALL CHECKS PASSED")
    sys.exit(0)
except Exception as e:
    print(f"❌ IMPORT ERROR: {e}")
    sys.exit(1)
