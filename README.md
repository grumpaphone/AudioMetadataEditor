# Audio Metadata Editor

![Python](https://img.shields.io/badge/python-3.11.3-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.4.0+-green.svg)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A sophisticated macOS application for reading, viewing, and editing metadata of WAV audio files with advanced background processing capabilities.

## 📸 Screenshots

_Application interface with loaded WAV files and metadata editing capabilities_

## 🎵 Features

- **Drag & Drop Interface**: Drag folders to scan for WAV files
- **Advanced Metadata Editing**: View and edit Filename, Scene, Take, Category, Subcategory, and iXML fields
- **Background Agent System**: Auto-save, file monitoring, and validation agents
- **Undo/Redo System**: Full command pattern implementation
- **Parallel Processing**: Multi-threaded file loading and processing
- **Real-time Validation**: Background integrity checking
- **Progress Reporting**: Visual feedback for long operations

## 🔧 Requirements

- **Python 3.11.3** (CRITICAL - use `python3` command)
- PyQt6 (6.4.0+)
- soundfile
- wavinfo
- numpy
- cachetools

## 📦 Installation

```bash
# Install dependencies
pip3 install -r requirements.txt
```

## 🚀 Usage

```bash
# Run the application
python3 app.py

# Or use the shell script (ensures correct Python version)
./run_app.sh
```

Simply drag a folder containing WAV files into the application window to scan and display their metadata.

## 🧪 Testing

```bash
# Test metadata reading with sample file
python3 test_metadata.py PR2_Allen_Sc5.14D_01.wav
```

## ⚡ Background Agents

- **AutoSave Agent**: Automatically saves changes every 30 seconds
- **FileWatcher Agent**: Monitors external file changes
- **Validation Agent**: Validates metadata integrity

## 🏗️ Architecture

- **Main App**: PyQt6-based GUI with sophisticated threading
- **Metadata Core**: Custom WAV metadata processing
- **Command System**: Undo/redo with command pattern
- **Agent System**: Background processing with Qt signals

---

**Note**: Always use `python3` (not `python`) to ensure correct version usage.
