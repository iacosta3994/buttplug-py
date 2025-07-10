# MuchFun - Setup Guide

A comprehensive guide to set up and run the MuchFun Audio-Reactive Device Controller.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Windows 10/11, macOS 10.14+, or Linux
- **Python**: Version 3.9 or higher
- **RAM**: At least 4GB (8GB recommended)
- **Microphone**: Any working microphone for audio control
- **Compatible Device**: Any device supported by Buttplug/Intiface

---

## 🐍 Step 1: Install Python

### Windows
1. Download Python from [python.org](https://www.python.org/downloads/)
2. **Important**: Check "Add Python to PATH" during installation
3. Choose "Install Now" or customize installation
4. Verify installation by opening Command Prompt and typing:
   ```cmd
   python --version
   ```

### macOS
1. **Option A**: Download from [python.org](https://www.python.org/downloads/)
2. **Option B**: Use Homebrew (recommended):
   ```bash
   brew install python
   ```
3. Verify installation:
   ```bash
   python3 --version
   ```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv python3-dev
```

### Linux (Fedora/CentOS)
```bash
sudo dnf install python3 python3-pip python3-venv python3-devel
```

---

## 📁 Step 2: Create Project Directory

1. Create a folder for the project:
   ```bash
   mkdir muchfun-app
   cd muchfun-app
   ```

2. Download or create the `muchfun.py` file in this directory

---

## 🔧 Step 3: Set Up Virtual Environment

### Create Virtual Environment
```bash
# Windows
python -m venv muchfun-env

# macOS/Linux  
python3 -m venv muchfun-env
```

### Activate Virtual Environment

**Windows (Command Prompt):**
```cmd
muchfun-env\Scripts\activate
```

**Windows (PowerShell):**
```powershell
muchfun-env\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source muchfun-env/bin/activate
```

You should see `(muchfun-env)` in your terminal prompt when activated.

---

## 📦 Step 4: Install Dependencies

### Install Core Requirements
```bash
pip install --upgrade pip
pip install buttplug-py numpy
```

### Install PyAudio (Audio Processing)

**Windows:**
```cmd
pip install pyaudio
```

**macOS:**
```bash
# Install portaudio first
brew install portaudio
pip install pyaudio
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install portaudio19-dev python3-pyaudio
pip install pyaudio
```

**Linux (Fedora/CentOS):**
```bash
sudo dnf install portaudio-devel
pip install pyaudio
```

### Verify Installation
Test that all packages are installed correctly:
```python
python -c "import tkinter, pyaudio, numpy, buttplug; print('All packages installed successfully!')"
```

---

## 🎮 Step 5: Install Intiface Central

MuchFun requires a Buttplug server to control devices.

### Download Intiface Central
1. Go to [Intiface Central Releases](https://github.com/intiface/intiface-central/releases)
2. Download the latest version for your operating system:
   - **Windows**: `intiface-central-installer.exe`
   - **macOS**: `intiface-central.dmg`
   - **Linux**: `intiface-central.AppImage`

### Install and Setup
1. Install Intiface Central following the installer instructions
2. Launch Intiface Central
3. Go to **Settings** and ensure:
   - **Server Port**: `12345` (default)
   - **Allow Remote Connections**: Enabled if needed
4. Click **Start Server** - you should see "Server Status: Running"

### Connect Your Device
1. Turn on your compatible device
2. In Intiface Central, click **Start Scanning**
3. Your device should appear in the device list
4. Click **Stop Scanning** once found

---

## 🚀 Step 6: Run MuchFun

### Start the Application
```bash
# Make sure virtual environment is activated
# You should see (muchfun-env) in your prompt

# Run the application
python muchfun.py
```

### First Time Setup
1. **Start Intiface Central** first and ensure server is running
2. **Launch MuchFun** - the GUI should open
3. Click **Connect** button in the Connection section
4. If successful, you'll see "✅ Connected" and your device name

---

## 🎛️ Step 7: Using MuchFun

### Control Modes
1. **Manual Control**: Use the intensity slider for direct control
2. **Audio Control**: Enable microphone to control via sound
3. **Pattern Control**: Use automated patterns with optional randomness

### Quick Start
1. **Test Manual Control**: Move the intensity slider and verify device responds
2. **Test Audio Control**: Enable microphone, adjust sensitivity, make noise
3. **Test Patterns**: Enable pattern control, try different pattern types

### Emergency Stop
- The **🛑 EMERGENCY STOP** button immediately stops all activity
- Use this for safety if needed

---

## 🔧 Troubleshooting

### Common Issues

#### "No module named 'pyaudio'"
```bash
# Reinstall PyAudio with system dependencies
# See Step 4 for platform-specific instructions
```

#### "Connection failed" in MuchFun
1. **Check Intiface Central**: Ensure server is running on port 12345
2. **Firewall**: Allow Python/MuchFun through firewall
3. **Device**: Ensure device is connected and detected in Intiface

#### "No audio input detected"
1. **Microphone permissions**: Allow Python to access microphone
2. **Default device**: Set your microphone as default input device
3. **Test microphone**: Verify microphone works in other applications

#### PyAudio installation fails on Linux
```bash
# Install additional dependencies
sudo apt install python3-dev libasound2-dev
# Then retry: pip install pyaudio
```

#### tkinter not found (Linux)
```bash
sudo apt install python3-tk
```

### Performance Issues

#### High CPU usage
- Reduce pattern speed in Pattern Control
- Disable verbose logging
- Close unnecessary applications

#### Audio lag or choppy response
- Adjust sensitivity in Audio Input section
- Try different smoothing settings
- Check system audio settings

---

## 📁 Project Structure

Your project directory should look like:
```
muchfun-app/
├── muchfun.py              # Main application file
├── muchfun-env/            # Virtual environment
│   ├── Scripts/ (Windows) or bin/ (macOS/Linux)
│   └── ...
└── logs/                   # Created automatically
    ├── muchfun_20241210_143022.log
    └── ...
```

---

## 🔄 Daily Usage

### Starting Everything
1. **Activate virtual environment**:
   ```bash
   # Windows
   muchfun-env\Scripts\activate
   
   # macOS/Linux
   source muchfun-env/bin/activate
   ```

2. **Start Intiface Central** and start the server

3. **Run MuchFun**:
   ```bash
   python muchfun.py
   ```

4. **Connect** in the app and start controlling!

### Stopping Everything
1. Use **Emergency Stop** or close MuchFun
2. Stop server in Intiface Central
3. Deactivate virtual environment: `deactivate`

---

## 📞 Support

### Logs
- MuchFun creates detailed logs in the `logs/` directory
- Enable "Verbose Logging" for detailed debugging information
- Include relevant log sections when seeking help

### Common Resources
- [Buttplug Documentation](https://buttplug-spec.docs.buttplug.io/)
- [Intiface Central Issues](https://github.com/intiface/intiface-central/issues)
- [Python Official Documentation](https://docs.python.org/)

### Device Compatibility
- Check [Buttplug Device Support](https://iostindex.com/?filter0Availability=Available&filter1Connection=Bluetooth%2CUSB%2CSerial&filter2ButtplugSupport=4) for your device
- Most major brands are supported (Lovense, We-Vibe, etc.)

---

## 🎉 You're Ready!

Your MuchFun setup is complete! Enjoy experimenting with:
- 🎵 **Audio-reactive control** with customizable smoothing
- 🔄 **Automated patterns** with randomness
- 🎛️ **Manual control** for precise adjustment
- 🛑 **Emergency stop** for safety

Have fun and stay safe! 🎮✨