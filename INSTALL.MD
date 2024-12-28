# Penrose Generator Installation Guide

## Desktop Installation (Windows/Linux/macOS)

### Windows-Specific Notes
- Ensure you have up-to-date graphics drivers installed
- OpenGL should be included with your graphics drivers
- If you encounter OpenGL errors, update your graphics drivers

### Linux-Specific Notes
- On Debian/Ubuntu systems, the setup script will install required OpenGL packages
- For other distributions, you may need to install OpenGL development packages manually
- Example for Fedora: `sudo dnf install python3-opengl`

### macOS-Specific Notes
- OpenGL is included by default
- You may need to install Command Line Tools if not already installed:

## Windows Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/penrose-generator.git
   cd penrose-generator
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements_desktop.txt
   ```

3. Run the generator:
   ```bash
   python penrose_generator.py --local
   ```


## Raspberry Pi Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/penrose-generator.git
   cd penrose-generator
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements_raspi.txt
   ```

3. Run the generator:
   ```bash
   python penrose_generator.py --local
   ```
