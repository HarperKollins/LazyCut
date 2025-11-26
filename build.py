import os
import shutil
import subprocess
import sys
import glob

def clean_build_artifacts():
    print("Starting Ruthless Cleanup...")
    folders = ['dist', 'build']
    for folder in folders:
        if os.path.exists(folder):
            print(f"   - Removing {folder}...")
            shutil.rmtree(folder, ignore_errors=True)
    
    if os.path.exists("LazyCut.spec"):
        print("   - Removing LazyCut.spec...")
        os.remove("LazyCut.spec")
    print("Cleanup Complete.")

def run_pyinstaller():
    print("Starting Build Process...")
    
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    
    # Build Command
    # Note: Using app.py as the entry point as it is the GUI.
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--icon=icon.ico",
        "--add-data", f"{ctk_path};customtkinter",
        "--collect-all", "imageio",
        "--collect-all", "moviepy",
        "--copy-metadata", "imageio",
        "--copy-metadata", "moviepy",
        "app.py", # Using app.py as the GUI entry point
        "--name", "LazyCut"
    ]
    
    print(f"   - Running: {' '.join(command)}")
    result = subprocess.run(command, capture_output=False)
    
    if result.returncode != 0:
        print("Build Failed!")
        sys.exit(1)
    print("Build Complete.")

def copy_binaries():
    print("Deploying Binaries...")
    
    dist_dir = os.path.join("dist", "LazyCut")
    if not os.path.exists(dist_dir):
        print(f"Error: Dist directory {dist_dir} not found!")
        sys.exit(1)

    # Files to copy
    files_to_copy = []
    
    # 1. Explicit Binaries
    if os.path.exists("ffmpeg.exe"): files_to_copy.append("ffmpeg.exe")
    if os.path.exists("magick.exe"): files_to_copy.append("magick.exe")
    
    # 2. DLLs and XMLs
    files_to_copy.extend(glob.glob("*.dll"))
    files_to_copy.extend(glob.glob("*.xml"))
    
    count = 0
    for f in files_to_copy:
        try:
            dest = os.path.join(dist_dir, f)
            print(f"   - Copying {f} -> {dest}")
            shutil.copy2(f, dest)
            count += 1
        except Exception as e:
            print(f"   Failed to copy {f}: {e}")
            
    print(f"Copied {count} files.")

def main():
    print("========================================")
    print("   LazyCut Build Automation Script")
    print("========================================")
    
    clean_build_artifacts()
    run_pyinstaller()
    copy_binaries()
    
    exe_path = os.path.abspath(os.path.join("dist", "LazyCut", "LazyCut.exe"))
    print("\n========================================")
    print("SUCCESS! Build Ready.")
    print(f"Executable: {exe_path}")
    print("========================================")

if __name__ == "__main__":
    main()
