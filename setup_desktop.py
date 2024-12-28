import os
import platform
import subprocess
import sys

def check_python_version():
    if sys.version_info < (3, 8):
        print("Python 3.8 or higher is required")
        sys.exit(1)

def install_requirements():
    print("Installing Python dependencies...")
    # Set environment variable to prevent Bluetooth imports during installation
    os.environ['PENROSE_LOCAL_MODE'] = '1'
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_desktop.txt"])

def install_opengl():
    system = platform.system()
    if system == "Windows":
        print("On Windows, you may need to manually install OpenGL drivers.")
        print("Please ensure your graphics drivers are up to date.")
    elif system == "Linux":
        if os.path.exists("/etc/debian_version"):
            print("Installing OpenGL dependencies for Debian/Ubuntu...")
            subprocess.check_call(["sudo", "apt-get", "install", "-y", "python3-opengl"])
        else:
            print("Please install OpenGL development packages for your Linux distribution")
    elif system == "Darwin":
        print("macOS includes OpenGL by default. No additional installation needed.")

def main():
    print("Setting up Penrose Generator for desktop environment...")
    
    check_python_version()
    install_opengl()
    install_requirements()
    
    print("\nSetup completed successfully!")
    print("\nYou can now run the generator in local mode with:")
    print("python penrose_generator.py --local")

if __name__ == "__main__":
    main() 