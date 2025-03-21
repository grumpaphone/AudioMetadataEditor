# Audio Metadata Editor

A macOS application for reading, viewing, and editing metadata of WAV audio files.

## Features

- Drag and drop folders to scan for WAV files
- View metadata including Filename, Scene, Take, Category, Subcategory, and iXML fields
- Edit metadata directly in the table
- Save changes back to the original files

## Requirements

- Python 3.8+
- PyQt6
- soundfile
- wavinfo

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python app.py
```

Simply drag a folder containing WAV files into the application window to scan and display their metadata.
