#!/usr/bin/env python3
"""
Audio Metadata Editor launcher script
"""
import sys
import traceback

def main():
    try:
        from app import main
        sys.exit(main())
    except ImportError as e:
        print(f"Error importing app module: {e}")
        print("Make sure all dependencies are installed using: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 