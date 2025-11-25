import requests
import os
import sys
import subprocess
from packaging import version
import tkinter.messagebox as messagebox

# --- CONFIG ---
CURRENT_VERSION = "2.0.0"  # UPDATE THIS when you release new versions!
REPO_OWNER = "HarperKollins"
REPO_NAME = "LazyCut"
GITHUB_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

def check_for_updates():
    print(f"🔍 Checking for updates... (Current: {CURRENT_VERSION})")
    
    try:
        # 1. Get latest info from GitHub
        response = requests.get(GITHUB_URL)
        if response.status_code != 200:
            print("⚠️ Could not connect to GitHub.")
            return

        data = response.json()
        latest_tag = data['tag_name'].replace('v', '') # Remove 'v' if you use 'v2.1'
        
        # 2. Compare Versions
        if version.parse(latest_tag) > version.parse(CURRENT_VERSION):
            print(f"🚨 New Version Found: {latest_tag}")
            
            # Ask User
            do_update = messagebox.askyesno(
                "Update Available", 
                f"LazyCut v{latest_tag} is out!\n\nDo you want to update now?"
            )
            
            if do_update:
                download_and_install(data['assets'])
        else:
            print("✅ App is up to date.")

    except Exception as e:
        print(f"❌ Update check failed: {e}")

def download_and_install(assets):
    # Find the .exe asset
    download_url = None
    for asset in assets:
        if asset['name'].endswith(".exe"):
            download_url = asset['browser_download_url']
            break
            
    if not download_url:
        messagebox.showerror("Error", "Could not find the installer file.")
        return

    print("⬇️ Downloading update...")
    
    # Download to Temp folder
    installer_path = os.path.join(os.getenv('TEMP'), "LazyCut_Update.exe")
    
    try:
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(installer_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print("✅ Download Complete. Installing...")
        
        # 3. RUN INSTALLER SILENTLY & CLOSE APP
        # /SILENT = Installs without asking questions
        # /CLOSEAPPLICATIONS = Tries to close the running LazyCut
        subprocess.Popen([installer_path, "/SILENT", "/CLOSEAPPLICATIONS"])
        
        # Kill current app immediately
        sys.exit(0)
        
    except Exception as e:
        messagebox.showerror("Update Failed", str(e))

# Test it (Only runs if you click play on this file directly)
if __name__ == "__main__":
    check_for_updates()
