import subprocess
import sys
import os
import requests

# --- CONFIGURATION ---
# IMPORTANT: Ensure this URL points to the updated file on your GitHub
GITHUB_RAW_URL = "https://raw.githubusercontent.com/dopesniper101/RDU-BOT/main/RDU%20CODE.py"

# --- STEP 1: INSTALL CORE DEPENDENCIES ---
print("--- Checking and Installing Core Dependencies ---")
try:
    # Aggressively install/upgrade py-cord with voice dependencies
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "py-cord[voice]"])
    
    # Try a quick import check for the core library (not the sinks module)
    try:
        import discord
        print("✅ Core dependencies installed successfully.")
    except ImportError:
        # If core import fails, we definitely need a restart
        print("⚠️ Core dependencies installed, but environment needs refresh.")
        print("Please run this cell AGAIN immediately to fully apply the changes.")
        sys.exit(0)
        
except Exception as e:
    print(f"❌ FATAL ERROR during core dependency installation: {e}")
    sys.exit(1)

# --- STEP 2: FETCH CODE FROM GITHUB ---
print("\n--- Fetching Code from GitHub ---")
try:
    response = requests.get(GITHUB_RAW_URL, timeout=10)
    response.raise_for_status()
    bot_code = response.text
    print(f"✅ Code fetched successfully from: {GITHUB_RAW_URL}")
except requests.exceptions.RequestException as e:
    print(f"❌ FATAL ERROR fetching code from GitHub. Check URL and connection: {e}")
    sys.exit(1)

# --- STEP 3: EXECUTE THE BOT CODE ---
print("\n--- Attempting to Start Discord Bot ---")
# The explicit PyNaCl install within the fetched code should now resolve the final error.
try:
    # Run the fetched code directly in the current environment
    exec(bot_code)
except SystemExit:
    # This is fine if the fetched code exited gracefully (e.g., token check fail).
    pass
except Exception as e:
    print(f"❌ An unexpected error occurred during code execution: {e.__class__.__name__}: {e}")
