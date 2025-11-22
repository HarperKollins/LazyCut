import imageio_ffmpeg
import shutil
import os

def fix_ffmpeg():
    print("🕵️‍♀️ Hunting for FFmpeg inside your computer...")
    
    # Find where the hidden FFmpeg is
    source_path = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"✅ Found it here: {source_path}")
    
    # Define where we want it (right here in the LazyCut folder)
    destination_path = os.path.join(os.getcwd(), "ffmpeg.exe")
    
    # Copy and rename it
    print("🚚 Moving it to the LazyCut folder...")
    try:
        shutil.copy(source_path, destination_path)
        print(f"✅ Success! Created: {destination_path}")
        print("\n🎉 FFmpeg is now fixed.") 
        print("👉 You can now run 'python main.py' and it will work!")
    except Exception as e:
        print(f"❌ Error moving file: {e}")

if __name__ == "__main__":
    fix_ffmpeg()