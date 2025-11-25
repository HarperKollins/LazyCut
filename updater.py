import os
import sys
import requests
import logging
import subprocess
import time
from packaging import version
from config import VERSION, GITHUB_REPO, TEMP_DIR, IS_WINDOWS

logger = logging.getLogger('LazyCut.Updater')

def check_for_updates():
    """
    Checks GitHub for a newer release.
    Returns (bool, str, str): (update_available, latest_version, download_url)
    """
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        latest_tag = data.get("tag_name", "v0.0.0").lstrip("v")
        
        if version.parse(latest_tag) > version.parse(VERSION):
            logger.info(f"🚀 New version available: {latest_tag} (Current: {VERSION})")
            
            # Find the correct asset
            download_url = None
            asset_name_filter = ".exe" if IS_WINDOWS else ".AppImage" # Example filter
            
            for asset in data.get("assets", []):
                if asset_name_filter in asset["name"]:
                    download_url = asset["browser_download_url"]
                    break
            
            return True, latest_tag, download_url
        else:
            logger.info("✅ App is up to date.")
            return False, latest_tag, None
            
    except Exception as e:
        logger.error(f"❌ Update check failed: {e}")
        return False, None, None

def download_and_install_update(download_url, new_version):
    """
    Downloads the update and triggers the installer/executable.
    """
    try:
        logger.info(f"⬇️ Downloading update from {download_url}...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        filename = os.path.basename(download_url)
        save_path = os.path.join(TEMP_DIR, filename)
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info("✅ Download complete. Starting update...")
        
        if IS_WINDOWS:
            # In a real scenario, this would likely be an installer or a self-replacing exe.
            # For this script, we'll simulate by launching the new exe and exiting.
            subprocess.Popen([save_path, "--silent"])
            sys.exit(0)
        else:
            # Linux: Make executable and run
            os.chmod(save_path, 0o755)
            subprocess.Popen([save_path])
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"❌ Update failed: {e}")
        return False

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    avail, ver, url = check_for_updates()
    if avail:
        print(f"Update found: {ver} -> {url}")
    else:
        print("No update found.")
