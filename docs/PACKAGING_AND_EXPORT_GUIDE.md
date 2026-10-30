# orang3D Standalone Packaging & Export Guide

**Complete Step-by-Step Manual for Cloning, Building, and Distributing orang3D on Windows and Linux**

---

## Table of Contents

1. [Executive Summary & Distribution Architecture](#1-executive-summary--distribution-architecture)
2. [Distribution Bundle Structure](#2-distribution-bundle-structure)
3. [Building on Linux (Ubuntu, Debian, Fedora, Arch, openSUSE)](#3-building-on-linux-ubuntu-debian-fedora-arch-opensuse)
   - [3.1 Step 1: Clone the Repository](#31-step-1-clone-the-repository)
   - [3.2 Step 2: Install System Graphics & Windowing Libraries](#32-step-2-install-system-graphics--windowing-libraries)
   - [3.3 Step 3: Create Virtual Environment & Install Dependencies](#33-step-3-create-virtual-environment--install-dependencies)
   - [3.4 Step 4: Run the Automated Build Engine](#34-step-4-run-the-automated-build-engine)
   - [3.5 Step 5: Test & Launch the Executable](#35-step-5-test--launch-the-executable)
   - [3.6 Step 6: Install Desktop Application Launcher (.desktop)](#36-step-6-install-desktop-application-launcher-desktop)
4. [Building on Windows (Windows 10 / 11 64-bit)](#4-building-on-windows-windows-10--11-64-bit)
   - [4.1 Step 1: Install Prerequisites (Python & Visual C++ Runtime)](#41-step-1-install-prerequisites-python--visual-c-runtime)
   - [4.2 Step 2: Clone the Repository](#42-step-2-clone-the-repository)
   - [4.3 Step 3: Create Virtual Environment & Install Dependencies](#43-step-3-create-virtual-environment--install-dependencies)
   - [4.4 Step 4: Run the Automated Windows Build Script](#44-step-4-run-the-automated-windows-build-script)
   - [4.5 Step 5: Test & Launch orang3d.exe](#45-step-5-test--launch-orang3dexe)
   - [4.6 Step 6: Create Windows Setup Wizard (Inno Setup)](#46-step-6-create-windows-setup-wizard-inno-setup)
5. [Automated Multi-Platform CI/CD (GitHub Actions)](#5-automated-multi-platform-cicd-github-actions)
6. [Troubleshooting & Frequently Asked Questions](#6-troubleshooting--frequently-asked-questions)

---

## 1. Executive Summary & Distribution Architecture

**orang3D** is engineered as a zero-dependency, cross-platform desktop application. Once compiled into a standalone distribution package, end users do **not** need Python, virtual environments, or C++ compilers installed on their machines.

The repository provides three tiers of distribution:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    orang3D Distribution Tiers                                    |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|  Tier 1: Pre-Compiled GitHub Actions Release Artifacts (Zero Configuration)                      |
|  • Linux x86_64:  orang3d-linux-x86_64.tar.gz (Extract and double-click `./orang3d`)             |
|  • Windows x64:   orang3d-windows-x64.zip (Extract and double-click `orang3d.exe`)               |
|                                                                                                  |
|  Tier 2: Local Standalone Binary Packaging (PyInstaller + PySide6 + PyVista)                     |
|  • Linux Shell:   ./scripts/build_linux.sh                                                       |
|  • Windows Batch: scripts\build_windows.bat                                                      |
|  • Universal CLI: python scripts/build_executable.py [--clean] [--archive] [--onefile]           |
|                                                                                                  |
|  Tier 3: Standard Python Wheels (PyPI / pip)                                                     |
|  • Build Wheel:   python -m build                                                                |
|  • Install Wheel: pip install dist/orang3d-0.1.0-py3-none-any.whl                                |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Distribution Bundle Structure

When exported in **directory bundle (`onedir`)** format (the industry standard for large scientific Qt/VTK suites), the output folder in `dist/orang3d/` contains:

### Linux Bundle (`dist/orang3d/`)
```text
dist/orang3d/
├── orang3d                      # Standalone executable ELF binary
├── orang3d.desktop              # FreeDesktop system launcher
├── README.md                    # Quick user manual
├── resources/
│   └── icons/
│       ├── orang3d.png          # High-resolution 256x256 application icon
│       └── orang3d.ico          # Multi-resolution icon
├── libQt6*.so*                  # Bundled PySide6 Qt 6 shared libraries
├── libvtk*.so*                  # Bundled VTK 9 scientific rendering libraries
└── _internal/                   # Bundled Python runtime, NumPy, SciPy, Matplotlib
```

### Windows Bundle (`dist\orang3d\`)
```text
dist\orang3d\
├── orang3d.exe                  # Standalone Windows executable (with embedded icon)
├── README.md                    # Quick user manual
├── resources\
│   └── icons\
│       ├── orang3d.ico          # Windows taskbar & titlebar icon
│       └── orang3d.png          # PNG asset
├── Qt6*.dll                     # Bundled PySide6 Qt 6 dynamic link libraries
├── vtk*.dll                     # Bundled VTK 9 visualization libraries
└── _internal\                   # Bundled Python DLL, NumPy, SciPy, Matplotlib
```

---

## 3. Building on Linux (Ubuntu, Debian, Fedora, Arch, openSUSE)

### 3.1 Step 1: Clone the Repository

Open a terminal and clone the repository:

```bash
git clone https://github.com/dibs/orang3d.git
cd orang3d
```

### 3.2 Step 2: Install System Graphics & Windowing Libraries

Linux distributions require OpenGL and X11/Wayland runtime libraries to render the PyVista 3D viewport and PySide6 Qt window:

```bash
# Debian / Ubuntu / Linux Mint / Pop!_OS
sudo apt-get update
sudo apt-get install -y libgl1-mesa-glx libegl1-mesa libxrandr2 libxss1 libxcursor1 libxcomposite1 libasound2t64 libxi6 libxtst6

# Fedora / RedHat / RHEL / CentOS Stream
sudo dnf install -y mesa-libGL mesa-libEGL libXrandr libXScrnSaver libXcursor libXcomposite alsa-lib libXi libXtst

# Arch Linux / Manjaro / EndeavourOS
sudo pacman -S mesa libglvnd libxrandr libxss libxcursor libxcomposite alsa-lib libxi libxtst

# openSUSE (Tumbleweed / Leap)
sudo zypper install -y Mesa-libGL1 Mesa-libEGL1 libXrandr2 libXcomposite1 libXcursor1
```

### 3.3 Step 3: Create Virtual Environment & Install Dependencies

Set up a clean Python 3.10+ (tested up to Python 3.12) virtual environment:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip & packaging utilities
pip install --upgrade pip setuptools wheel

# Install dependencies and packaging tools
pip install -r requirements.txt pyinstaller build pillow
pip install -e .
```

### 3.4 Step 4: Run the Automated Build Engine

Execute the build script:

```bash
# Grant execution permissions (first time only)
chmod +x scripts/build_linux.sh scripts/build_executable.py

# Run one-click build script
./scripts/build_linux.sh
```

Alternatively, you can customize the build using the universal Python packaging engine:

```bash
# Build standard directory bundle (Recommended)
python scripts/build_executable.py --clean --archive

# OR build a single-file portable binary
python scripts/build_executable.py --onefile --clean --archive
```

### 3.5 Step 5: Test & Launch the Executable

Upon build completion, the output will be in `dist/`:

```bash
# Test-run the executable
./dist/orang3d/orang3d

# If running on a headless server or VM without a GPU:
LIBGL_ALWAYS_SOFTWARE=1 ./dist/orang3d/orang3d
```

The compressed distribution archive is saved to:
`dist/orang3d-linux-x86_64.tar.gz` (~306 MB)

### 3.6 Step 6: Install Desktop Application Launcher (.desktop)

To integrate orang3D with your system application menu (GNOME Dash, KDE Kickoff, XFCE):

```bash
# 1. Extract to local programs folder
mkdir -p ~/.local/opt
tar -xzf dist/orang3d-linux-x86_64.tar.gz -C ~/.local/opt/

# 2. Install application icon
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
cp ~/.local/opt/orang3d/resources/icons/orang3d.png ~/.local/share/icons/hicolor/256x256/apps/orang3d.png

# 3. Register FreeDesktop desktop shortcut
cat << EOF > ~/.local/share/applications/orang3d.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=orang3D
GenericName=Retaining Wall Seismic & SSI Analyzer
Comment=Real-Time 3D Seismic, Hydrodynamic, and Geotechnical Soil-Structure Interaction Simulation
Exec=$HOME/.local/opt/orang3d/orang3d %F
Icon=orang3d
Terminal=false
Categories=Science;Engineering;Physics;Geology;Qt;
StartupNotify=true
StartupWMClass=orang3D
EOF

# 4. Refresh application database
update-desktop-database ~/.local/share/applications/
```

---

## 4. Building on Windows (Windows 10 / 11 64-bit)

### 4.1 Step 1: Install Prerequisites (Python & Visual C++ Runtime)

1. **Python 3.10, 3.11, or 3.12 (64-bit):**
   - Download from [python.org/downloads](https://www.python.org/downloads/).
   - **CRITICAL:** Check the box **"Add python.exe to PATH"** at the bottom of the installer window!
   - Alternatively, install via Windows Package Manager:
     ```powershell
     winget install Python.Python.3.12
     ```
2. **Microsoft Visual C++ 2015–2022 Redistributable (x64):**
   - Typically already installed on Windows machines. If missing, install via:
     ```powershell
     winget install Microsoft.VCRedist.2015+.x64
     ```

### 4.2 Step 2: Clone the Repository

Open **Command Prompt (`cmd.exe`)** or **PowerShell**:

```cmd
git clone https://github.com/dibs/orang3d.git
cd orang3d
```

### 4.3 Step 3: Create Virtual Environment & Install Dependencies

```cmd
:: 1. Create virtual environment
python -m venv .venv

:: 2. Activate virtual environment
:: In Command Prompt:
.venv\Scripts\activate.bat
:: OR in PowerShell:
:: .venv\Scripts\Activate.ps1

:: 3. Upgrade pip
python -m pip install --upgrade pip setuptools wheel

:: 4. Install dependencies and build tools
pip install -r requirements.txt pyinstaller build pillow
pip install -e .
```

> [!TIP]
> **PowerShell Execution Policy Error:**
> If PowerShell displays `File Activate.ps1 cannot be loaded because running scripts is disabled`, run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```
> and run `.venv\Scripts\Activate.ps1` again.

### 4.4 Step 4: Run the Automated Windows Build Script

Run the automated batch script:

```cmd
scripts\build_windows.bat
```

Or invoke the Python packaging engine directly:

```cmd
:: Standard onedir bundle (Fast startup, recommended)
python scripts\build_executable.py --clean --archive

:: Single-file portable .exe
python scripts\build_executable.py --onefile --clean --archive
```

### 4.5 Step 5: Test & Launch orang3d.exe

Upon completion, navigate to `dist\orang3d\` and launch the application:

```cmd
:: Run from Command Prompt:
dist\orang3d\orang3d.exe
```
Or simply double-click `dist\orang3d\orang3d.exe` in Windows File Explorer!

The distributable compressed archive is ready at:
`dist\orang3d-windows-x64.zip`

### 4.6 Step 6: Create Windows Setup Wizard (Inno Setup)

To turn `dist\orang3d\` into a professional Windows Setup Installer (`orang3d-setup.exe`):

1. Download and install [Inno Setup 6](https://jrsoftware.org/isinfo.php).
2. Create an installer script named `installer.iss`:
   ```iss
   [Setup]
   AppName=orang3D
   AppVersion=0.1.0
   DefaultDirName={autopf}\orang3D
   DefaultGroupName=orang3D
   OutputDir=dist\installer
   OutputBaseFilename=orang3d-windows-x64-setup
   Compression=lzma2/ultra64
   SolidCompression=yes
   SetupIconFile=resources\icons\orang3d.ico

   [Files]
   Source: "dist\orang3d\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

   [Icons]
   Name: "{group}\orang3D"; Filename: "{app}\orang3d.exe"; IconFilename: "{app}\resources\icons\orang3d.ico"
   Name: "{autodesktop}\orang3D"; Filename: "{app}\orang3d.exe"; IconFilename: "{app}\resources\icons\orang3d.ico"
   ```
3. Right-click `installer.iss` $\to$ **Compile** (or run `iscc installer.iss` in terminal).
4. The setup wizard is generated in `dist\installer\orang3d-windows-x64-setup.exe`.

---

## 5. Automated Multi-Platform CI/CD (GitHub Actions)

If you host your repository on GitHub, pre-compiled standalone binaries are generated automatically on every push via [`.github/workflows/ci.yml`](file:///home/avisheks/Documents/dibs/orang3d/.github/workflows/ci.yml).

### How to Download Pre-Built Binaries from GitHub:
1. Navigate to your repository on GitHub.
2. Click the **Actions** tab at the top.
3. Select the latest run of **"CI / CD & Multi-Platform Build Matrix"**.
4. Scroll down to the **Artifacts** section at the bottom of the page.
5. Download:
   - `orang3d-linux-x86_64` (for Linux)
   - `orang3d-windows-x64` (for Windows)
6. Extract the archive and double-click the executable.

---

## 6. Troubleshooting & Frequently Asked Questions

### Q1: "Python is not recognized as an internal or external command" on Windows
- **Cause:** Python was installed without checking "Add python.exe to PATH".
- **Fix:** Re-run the Python installer, select **Modify**, and check **"Add Python to environment variables"**, or manually add `C:\Users\<User>\AppData\Local\Programs\Python\Python312` and its `Scripts\` subdirectory to your system PATH.

### Q2: Linux error `libxcb-cursor.so.0: cannot open shared object file`
- **Cause:** Qt 6.5+ requires the XCB cursor library on Linux.
- **Fix:** Install the missing package:
  ```bash
  sudo apt-get install -y libxcb-cursor0  # Ubuntu/Debian
  sudo dnf install -y xcb-util-cursor     # Fedora
  sudo pacman -S xcb-util-cursor          # Arch
  ```

### Q3: 3D Viewport is blank, black, or crashes on Linux virtual machines
- **Cause:** Virtualization hypervisors often lack hardware 3D OpenGL acceleration.
- **Fix:** Force software Mesa LLVMpipe rendering:
  ```bash
  LIBGL_ALWAYS_SOFTWARE=1 ./dist/orang3d/orang3d
  ```

### Q4: Windows Defender SmartScreen blocks orang3d.exe
- **Cause:** Freshly compiled executables without a commercial EV code-signing certificate trigger a heuristic warning.
- **Fix:** Click **"More info"** $\to$ **"Run anyway"**.

### Q5: Should I use directory bundle (`onedir`) or single-file (`--onefile`)?
- **Recommendation:** Always use **directory bundle (`onedir`)** (the default).
- **Why?** Large scientific applications (Qt + VTK + NumPy + SciPy + Matplotlib) exceed 300 MB. In `--onefile` mode, the operating system must extract 300 MB into temporary directories on *every single execution*, causing a 10–20 second delay. In `onedir` mode, the application boots instantly in less than 1 second!
