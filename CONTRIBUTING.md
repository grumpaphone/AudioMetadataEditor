# Contributing to Audio Metadata Editor

Thank you for your interest in contributing to the Audio Metadata Editor! This document provides guidelines for contributing to the project.

## 📋 Prerequisites

Before contributing, please ensure you have:

- **Python 3.11.3** installed
- Read the [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for architecture understanding
- Familiarity with PyQt6 and Qt's signal/slot system
- Understanding of multi-threaded programming concepts

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

   ```bash
   git clone https://github.com/yourusername/audio-metadata-editor.git
   cd audio-metadata-editor
   ```

3. **Set up the development environment**:

   ```bash
   # Create virtual environment
   python3 -m venv .venv
   source .venv/bin/activate

   # Install dependencies
   pip3 install -r requirements.txt
   ```

4. **Test the application**:
   ```bash
   python3 app.py
   # Or use the shell script
   ./run_app.sh
   ```

## 🏗️ Development Guidelines

### Code Standards

- **Always use Python 3.11.3** with `python3` command
- **Follow PyQt6 patterns** - never use PyQt5
- **Use f-strings** for string formatting
- **Implement proper error handling** with specific exceptions
- **Use Qt signals/slots** for thread communication
- **Follow the command pattern** for undoable operations

### Architecture Requirements

- **Background operations** must use QThread
- **Long operations** should show progress feedback
- **Data changes** should be undoable via command pattern
- **Agent system** should be used for background processing
- **Thread safety** is mandatory for all cross-thread operations

### Before Making Changes

1. **Read [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)** thoroughly
2. **Check [.cursor/rules/](cursor/rules/)** for development rules
3. **Understand affected components** and their interactions
4. **Plan your changes** to follow existing patterns

## 📝 Making Changes

### Development Process

1. **Create a feature branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the guidelines above

3. **Test thoroughly**:

   ```bash
   # Test basic functionality
   python3 app.py

   # Test metadata processing
   python3 test_metadata.py PR2_Allen_Sc5.14D_01.wav
   ```

4. **Update documentation**:
   - Update [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) for architectural changes
   - Update line number references if you've moved code significantly
   - Add new classes/methods to the appropriate documentation sections

### Commit Guidelines

- **Use clear, descriptive commit messages**
- **Reference issues** when applicable (`Fixes #123`)
- **Keep commits focused** - one feature/fix per commit
- **Include documentation updates** in the same commit as code changes

Example commit messages:

```
feat: Add new validation agent for metadata integrity checks

fix: Resolve threading issue in file loading worker

docs: Update architecture documentation for new agent system

refactor: Simplify background agent manager initialization
```

## 🧪 Testing

### Manual Testing

- **Load various WAV files** with different metadata formats
- **Test background agents** (auto-save, file watching, validation)
- **Verify undo/redo** functionality works correctly
- **Test with large file sets** (1000+ files)
- **Ensure UI responsiveness** during long operations

### Performance Testing

- Monitor memory usage with large datasets
- Verify background agents don't consume excessive CPU
- Test application startup and shutdown times
- Validate file loading performance with different directory sizes

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Python version**: Output of `python3 --version`
2. **Operating system**: macOS version
3. **Steps to reproduce** the issue
4. **Expected vs actual behavior**
5. **Sample files** if metadata-related (if possible)
6. **Console output** or error messages

## 💡 Feature Requests

For new features, please:

1. **Check existing issues** to avoid duplicates
2. **Describe the use case** and problem being solved
3. **Consider architecture impact** - how it fits with existing systems
4. **Suggest implementation approach** if you have ideas

## 📚 Resources

- [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) - Complete architecture reference
- [.cursor/rules/](cursor/rules/) - Development rules and standards
- [PyQt6 Documentation](https://doc.qt.io/qtforpython-6/) - Framework reference
- [Qt Threading](https://doc.qt.io/qt-6/thread-basics.html) - Threading best practices

## 🤝 Pull Request Process

1. **Ensure all tests pass** and application runs correctly
2. **Update documentation** for any architectural changes
3. **Follow commit message guidelines**
4. **Request review** from maintainers
5. **Address feedback** promptly and professionally

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to the Audio Metadata Editor! 🎵
