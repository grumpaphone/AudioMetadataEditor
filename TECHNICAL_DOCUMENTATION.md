# Audio Metadata Editor - Technical Documentation

_Last Updated: December 2024_

## 📋 Table of Contents

1. [Application Overview](#application-overview)
2. [Architecture Overview](#architecture-overview)
3. [Core Components](#core-components)
4. [Background Agent System](#background-agent-system)
5. [User Interface Structure](#user-interface-structure)
6. [Data Flow](#data-flow)
7. [File Organization](#file-organization)
8. [Key Classes and Responsibilities](#key-classes-and-responsibilities)
9. [Threading Model](#threading-model)
10. [Command System](#command-system)

---

## 📖 Application Overview

The Audio Metadata Editor is a sophisticated PyQt6-based desktop application designed for professional audio workflows. It provides advanced metadata management for WAV audio files with enterprise-level features including background processing, undo/redo capabilities, and real-time validation.

### Primary Functions:

- **WAV File Discovery**: Recursively scan directories for WAV files
- **Metadata Extraction**: Read comprehensive metadata including iXML, BWF, and ID3 tags
- **Interactive Editing**: Table-based interface for direct metadata modification
- **Batch Operations**: Process multiple files simultaneously
- **Background Processing**: Non-blocking operations with progress reporting
- **Data Persistence**: Save metadata back to original files
- **Validation**: Real-time integrity checking and error detection

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PyQt6 Main Window                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Tool Bar      │  │   Status Bar    │  │   Menu Bar  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Main Content Area                          │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │            File Table Widget                        │ │ │
│  │  │  - File listing with metadata columns               │ │ │
│  │  │  - Sortable, filterable, editable                   │ │ │
│  │  │  - Context menus and shortcuts                      │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │            Control Panel                            │ │ │
│  │  │  - Load/Save buttons                                │ │ │
│  │  │  - Search and filter controls                       │ │ │
│  │  │  - Batch operation tools                            │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Background Agent System                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ AutoSave    │  │ FileWatcher │  │ Validation Agent    │  │
│  │ Agent       │  │ Agent       │  │                     │  │
│  │ (30s cycle) │  │ (realtime)  │  │ (periodic checks)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Metadata Processing Layer                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │            wav_metadata.py Module                       │ │
│  │  - WAV file parsing                                     │ │
│  │  - iXML extraction and parsing                          │ │
│  │  │  - BWF (Broadcast Wave Format) support               │ │
│  │  - ID3 tag processing                                   │ │
│  │  - Metadata writing and validation                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 Core Components

### 1. AudioMetadataEditor (Main Application Class)

**File:** `app.py:864-2680`
**Purpose:** Primary application window and controller

**Key Responsibilities:**

- Window management and UI layout
- Event handling and user interactions
- File loading orchestration
- Background agent coordination
- Undo/redo system management
- Settings and preferences

**Key Methods:**

- `__init__()`: Initialize UI, agents, and systems
- `load_files()`: File discovery and loading
- `on_files_loaded()`: Post-load processing
- `setup_ui()`: UI component initialization
- `setup_agent_manager()`: Background agent configuration

### 2. Background Agent System

**File:** `app.py:60-600`
**Purpose:** Non-blocking background processing

#### 2.1 BackgroundAgent (Base Class)

**Lines:** `app.py:60-150`

- Abstract base for all background agents
- QThread-based for proper Qt integration
- Configurable intervals and lifecycle management
- Signal-based communication with main thread

#### 2.2 BackgroundAgentManager

**Lines:** `app.py:151-250`

- Coordinates multiple background agents
- Handles agent startup, shutdown, and error recovery
- Provides unified configuration interface
- Manages agent dependencies and priorities

#### 2.3 AutoSaveAgent

**Lines:** `app.py:251-350`

- Automatically saves pending changes every 30 seconds
- Monitors `changes_pending` flag
- Provides user feedback via status updates
- Handles save errors gracefully

#### 2.4 FileWatcherAgent

**Lines:** `app.py:351-450`

- Monitors external changes to loaded WAV files
- Uses Qt file system watcher
- Alerts user when files are modified outside application
- Offers reload options

#### 2.5 ValidationAgent

**Lines:** `app.py:451-550`

- Periodically validates metadata integrity
- Checks for file corruption or inconsistencies
- Validates metadata format compliance
- Reports issues via status system

### 3. File Loading System

**File:** `app.py:602-800`

#### 3.1 FileLoadWorker (QThread)

**Purpose:** Background file discovery and metadata extraction
**Key Features:**

- Recursive directory scanning
- Parallel file processing using ThreadPoolExecutor
- Progress reporting with interruption support
- Error handling and recovery

**Process Flow:**

1. Scan directory recursively for `.wav` files
2. Create ThreadPoolExecutor for parallel processing
3. Process files in batches (optimized for performance)
4. Extract metadata using `wav_metadata.py`
5. Emit progress signals for UI updates
6. Handle interruption and cleanup

### 4. Command System (Undo/Redo)

**File:** `app.py:1-59`

#### 4.1 Command Classes

- **EditMetadataCommand**: Single field edits
- **RenameFileCommand**: File renaming operations
- **BatchCommand**: Multiple operations as single unit
- **SortCommand**: Table sorting operations

#### 4.2 CommandManager

- Maintains undo/redo stacks
- Executes commands with error handling
- Provides batch operation support
- Integrates with UI for state updates

---

## 🤖 Background Agent System

### Agent Lifecycle

```
Application Start
       │
       ▼
Agent Manager Created
       │
       ▼
Agents Configured
       │
       ▼
Files Loaded ────────► Agents Started
       │                    │
       ▼                    │
Application Running          │
       │                    ▼
       │              Agent Processing
       │              (Auto-save, Watch, Validate)
       │                    │
       ▼                    │
Application Close ◄──────────┘
       │
       ▼
Agents Stopped
       │
       ▼
Cleanup Complete
```

### Agent Communication

- **Signals Used:**
  - `agent_status_changed`: Status updates
  - `agent_error_occurred`: Error reporting
  - `manager_status_changed`: Manager state changes
- **Thread Safety:** All agent-to-UI communication via Qt signals
- **Error Handling:** Graceful degradation when agents fail

---

## 🖼️ User Interface Structure

### Main Window Layout

```
┌─────────────────────────────────────────────────────────┐
│ Menu Bar [File] [Edit] [View] [Tools] [Help]            │
├─────────────────────────────────────────────────────────┤
│ Tool Bar [Load] [Save] [Undo] [Redo] [🔍] [Filter]      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                File Table                           │ │
│  │ ┌─────────┬────────┬────────┬──────────┬──────────┐ │ │
│  │ │Filename │ Scene  │ Take   │ Category │Subcat... │ │ │
│  │ ├─────────┼────────┼────────┼──────────┼──────────┤ │ │
│  │ │ File1   │ Sc1    │ 01     │ Dialog   │ Clean    │ │ │
│  │ │ File2   │ Sc2    │ 02     │ Music    │ Score    │ │ │
│  │ │ ...     │ ...    │ ...    │ ...      │ ...      │ │ │
│  │ └─────────┴────────┴────────┴──────────┴──────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Status Bar: [Status] [Agent Info] [Progress] [Counts]   │
└─────────────────────────────────────────────────────────┘
```

### UI Components

#### 1. File Table (QTableWidget)

**Purpose:** Primary data display and editing interface
**Features:**

- Sortable columns with custom sort indicators
- In-place editing with validation
- Context menus for batch operations
- Keyboard shortcuts for common actions
- Selection highlighting and multi-select support

#### 2. Search and Filter System

**Purpose:** Data discovery and navigation
**Components:**

- Search field with debounced input
- Dropdown filters for categorical data
- Clear/reset functionality
- Real-time filtering with performance optimization

#### 3. Progress Reporting

**Purpose:** User feedback for long operations
**Implementation:**

- QProgressDialog for file loading
- Status bar updates for background operations
- Progress cancellation support
- Error reporting with details

---

## 🔄 Data Flow

### File Loading Flow

```
User Action (Drag/Drop or Open)
           │
           ▼
File Discovery (Recursive Scan)
           │
           ▼
Metadata Extraction (Parallel)
           │
           ▼
Data Validation
           │
           ▼
UI Population
           │
           ▼
Background Agents Start
           │
           ▼
Ready for Editing
```

### Edit Operation Flow

```
User Edit (Cell Change)
           │
           ▼
Create Command Object
           │
           ▼
Add to Undo Stack
           │
           ▼
Execute Command
           │
           ▼
Update UI
           │
           ▼
Mark Changes Pending
           │
           ▼
Auto-save Agent Triggered
```

### Save Operation Flow

```
Save Triggered (Manual/Auto)
           │
           ▼
Collect Changed Records
           │
           ▼
Backup Original Files
           │
           ▼
Write Metadata (Parallel)
           │
           ▼
Validate Written Data
           │
           ▼
Update UI Status
           │
           ▼
Clear Changes Pending
```

---

## 📁 File Organization

```
project_root/
├── app.py                      # Main application (5353 lines)
│   ├── Lines 1-59             # Command System Classes
│   ├── Lines 60-600           # Background Agent System
│   ├── Lines 601-863          # File Loading System
│   ├── Lines 864-2680         # AudioMetadataEditor Class
│   └── Lines 2681-5353        # UI Helper Methods & Event Handlers
│
├── wav_metadata.py             # Metadata processing (680 lines)
│   ├── Lines 1-100            # Imports and Constants
│   ├── Lines 101-300          # WAV File Parsing
│   ├── Lines 301-500          # iXML Processing
│   ├── Lines 501-600          # Metadata Writing
│   └── Lines 601-680          # Utility Functions
│
├── test_metadata.py            # Testing utilities (55 lines)
├── run_app.sh                  # Launch script (4 lines)
├── requirements.txt            # Dependencies (11 lines)
├── README.md                   # User documentation (66 lines)
├── TECHNICAL_DOCUMENTATION.md  # This file
│
├── .cursor/rules/              # Development rules
│   └── python-audio-metadata-editor.mdc
│
├── .git/                       # Version control
├── .venv/                      # Virtual environment
└── PR2_Allen_Sc5.14D_01.wav    # Sample data (11MB)
```

---

## 🏛️ Key Classes and Responsibilities

### Core Application Classes

| Class                    | File   | Lines    | Responsibility                            |
| ------------------------ | ------ | -------- | ----------------------------------------- |
| `AudioMetadataEditor`    | app.py | 864-2680 | Main window, UI management, orchestration |
| `BackgroundAgentManager` | app.py | 151-250  | Agent lifecycle and coordination          |
| `FileLoadWorker`         | app.py | 602-700  | Background file loading and processing    |
| `CommandManager`         | app.py | 35-59    | Undo/redo system management               |

### Command System Classes

| Class                 | File   | Lines | Responsibility                     |
| --------------------- | ------ | ----- | ---------------------------------- |
| `EditMetadataCommand` | app.py | 1-15  | Single field edit operations       |
| `RenameFileCommand`   | app.py | 16-25 | File renaming with undo support    |
| `BatchCommand`        | app.py | 26-34 | Multiple operations as atomic unit |

### Background Agent Classes

| Class              | File   | Lines   | Responsibility                      |
| ------------------ | ------ | ------- | ----------------------------------- |
| `BackgroundAgent`  | app.py | 60-110  | Base class for all agents           |
| `AutoSaveAgent`    | app.py | 251-320 | Automatic saving of pending changes |
| `FileWatcherAgent` | app.py | 351-420 | External file change monitoring     |
| `ValidationAgent`  | app.py | 451-520 | Metadata integrity validation       |

---

## 🧵 Threading Model

### Thread Architecture

```
Main UI Thread (Primary)
│
├── Background Agent Threads (3 concurrent)
│   ├── AutoSave Agent Thread
│   ├── FileWatcher Agent Thread
│   └── Validation Agent Thread
│
├── File Loading Thread (1 active)
│   └── ThreadPoolExecutor (CPU cores * 2)
│       ├── Worker Thread 1
│       ├── Worker Thread 2
│       └── Worker Thread N
│
└── Qt Signal/Slot System (Thread-safe communication)
```

### Thread Safety Measures

- **Qt Signals/Slots**: All cross-thread communication
- **Data Protection**: Shared data accessed via signals only
- **Resource Management**: Proper cleanup on thread termination
- **Error Isolation**: Thread failures don't crash main application

---

## ⚡ Command System

### Command Pattern Implementation

```
User Action
     │
     ▼
Create Command Object
     │
     ▼
CommandManager.execute()
     │
     ▼
Command.execute()
     │
     ▼
Update Data Model
     │
     ▼
Update UI
     │
     ▼
Add to Undo Stack
```

### Undo/Redo Stack Management

- **Undo Stack**: Commands executed (for undoing)
- **Redo Stack**: Commands undone (for redoing)
- **Stack Limits**: Configurable maximum stack size
- **Memory Management**: Automatic cleanup of old commands

---

## 🔧 Development Guidelines

### When Adding New Features:

1. **Update this documentation** with new components
2. **Follow existing architectural patterns**
3. **Use background threads** for long operations
4. **Implement undo/redo** for data changes
5. **Add appropriate error handling**
6. **Update cursor rules** if needed

### When Modifying Existing Code:

1. **Review this documentation** for impact analysis
2. **Update affected sections** in this file
3. **Test background agent integration**
4. **Verify thread safety** of changes
5. **Update version in header** of this document

---

## 📊 Performance Characteristics

### File Loading Performance

- **Small directories** (< 100 files): ~2-5 seconds
- **Medium directories** (100-1000 files): ~10-30 seconds
- **Large directories** (1000+ files): ~1-5 minutes
- **Scaling factor**: Linear with file count, parallel processing optimized

### Memory Usage

- **Base application**: ~50-100 MB
- **Per loaded file**: ~1-5 KB metadata storage
- **Large datasets** (10,000 files): ~150-200 MB total

### Background Agent Impact

- **CPU Usage**: Minimal (<5% during idle)
- **I/O Impact**: Low (periodic file checks)
- **User Experience**: Non-blocking, seamless operation

---

_This document should be updated whenever significant changes are made to the application architecture, functionality, or structure._
