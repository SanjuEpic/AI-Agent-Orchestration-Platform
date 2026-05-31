import os
import sys
import subprocess
import argparse
import time

# Reconfigure stdout/stderr to use UTF-8 on Windows to prevent UnicodeEncodeError with emojis
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

def check_command_exists(cmd):
    """Check if a terminal command is available on the system path."""
    try:
        subprocess.run([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        return True
    except FileNotFoundError:
        return False

def install_backend_dependencies():
    """Install required Python packages."""
    print("📦 [Setup] Checking and installing backend dependencies...")
    req_file = os.path.join(os.path.dirname(__file__), "backend", "requirements.txt")
    if not os.path.exists(req_file):
        print(f"Error: Could not find requirements file: {req_file}")
        sys.exit(1)
        
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
        print("✅ [Setup] Python dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ [Setup] Failed to install Python dependencies: {str(e)}")
        sys.exit(1)

def install_and_build_frontend(dev_mode=False):
    """Install npm dependencies and compile React frontend into static assets."""
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    if not os.path.exists(frontend_dir):
        print(f"Error: Could not find frontend directory: {frontend_dir}")
        sys.exit(1)
        
    if not check_command_exists("npm"):
        print("[WARNING] 'npm' command not found on path. Cannot compile frontend.")
        print("Please ensure Node.js is installed. Falling back to API-only server mode.")
        return False
        
    print("📦 [Setup] Installing frontend Node modules (npm install)...")
    try:
        # Run npm install
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True, shell=True)
        print("✅ [Setup] Frontend node modules installed.")
        
        if not dev_mode:
            print("🚀 [Setup] Compiling React static assets (npm run build)...")
            subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True, shell=True)
            print("✅ [Setup] Frontend compiled successfully into static assets.")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"❌ [Setup] Frontend installation or build failed: {str(e)}")
        sys.exit(1)
        
    return False

def start_servers(dev_mode=False):
    """Start uvicorn server (and optionally Vite dev server concurrently)."""
    import socket
    backend_dir = os.path.dirname(__file__)
    
    # We will launch uvicorn
    # Make sure we run from the root workspace directory
    uvicorn_cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]
    if dev_mode:
        uvicorn_cmd.append("--reload")
        
    print("🚀 Starting AI Agent Orchestration Platform backend...")
    
    try:
        # Start backend in a background subprocess in both modes
        backend_proc = subprocess.Popen(uvicorn_cmd, cwd=backend_dir)
        
        # Wait for backend to bind and respond on port 8000
        start_time = time.time()
        backend_ready = False
        while time.time() - start_time < 15.0:
            if backend_proc.poll() is not None:
                # Backend process crashed
                print("❌ [Error] Backend server crashed on startup.")
                sys.exit(1)
            try:
                with socket.create_connection(("127.0.0.1", 8000), timeout=1.0):
                    backend_ready = True
                    break
            except (socket.timeout, ConnectionRefusedError):
                time.sleep(0.5)
                
        if not backend_ready:
            print("⚠️ [Warning] Backend took too long to start. It might not be running correctly.")
        else:
            print("\n✅ AI Agent Orchestration Platform backend is ready!")
            print("👉 API Port running at: http://127.0.0.1:8000")
            if not dev_mode:
                print("👉 Web interface served directly at: http://127.0.0.1:8000")
        
        if dev_mode:
            print("👉 Starting Vite Dev Server concurrently at: http://localhost:3000")
            frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
            
            # Start Vite in foreground
            try:
                subprocess.run(["npm", "run", "dev", "--", "--port", "3000"], cwd=frontend_dir, shell=True)
            except KeyboardInterrupt:
                print("\nShutting down dev servers...")
            finally:
                backend_proc.terminate()
        else:
            # Production mode: block on backend process
            try:
                backend_proc.wait()
            except KeyboardInterrupt:
                print("\nShutting down backend server...")
                backend_proc.terminate()
    except Exception as e:
        print(f"❌ Failed to run servers: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent Orchestration Platform Orchestrator Bootloader")
    parser.add_argument("--dev", action="store_true", help="Run in developer mode with live-reloading servers")
    parser.add_argument("--skip-build", action="store_true", help="Skip npm install and build steps")
    
    args = parser.parse_args()
    
    # Load .env file configurations if available, else warn user
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_file):
        print("⚠️ [WARNING] No '.env' file found in workspace root. Please copy '.env.example' to '.env' and fill in API keys.")
        # Create an empty .env file template
        with open(env_file, "w") as f:
            f.write("# LLM API Keys\nGEMINI_API_KEY=YOUR_GEMINI_API_KEY\nOPENAI_API_KEY=YOUR_OPENAI_API_KEY\nANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY\n\n# Messaging bot tokens\nTELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN\nSLACK_BOT_TOKEN=YOUR_SLACK_BOT_TOKEN\nWHATSAPP_ACCESS_TOKEN=YOUR_WHATSAPP_ACCESS_TOKEN\n")
        print("📝 Created default '.env' file template. Please edit it with real keys to run workflows.")

    # 1. Install Python packages
    install_backend_dependencies()
    
    # 2. Build React frontend if not skipped
    build_success = False
    if not args.skip_build:
        build_success = install_and_build_frontend(dev_mode=args.dev)
        
    # 3. Start execution
    start_servers(dev_mode=args.dev)
