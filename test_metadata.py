#!/usr/bin/env python3
"""
Test script to read metadata from a single WAV file
"""

import sys
import os
import wav_metadata

def test_file(wav_path):
    """Test reading metadata from a single WAV file"""
    if not os.path.exists(wav_path):
        print(f"Error: File not found: {wav_path}")
        return
    
    if not wav_path.lower().endswith('.wav'):
        print(f"Error: Not a WAV file: {wav_path}")
        return
    
    print(f"\nTesting metadata reading for: {wav_path}")
    print("="*80)
    
    try:
        # Read metadata using our module
        metadata = wav_metadata.read_wav_metadata(wav_path, debug=True)
        
        # Print the results
        print("\nMetadata read results:")
        for key, value in metadata.items():
            print(f"  {key}: {repr(value)}")
            
        # Check if we found any data
        empty_fields = [k for k, v in metadata.items() 
                         if k not in ["Filename", "File Path"] and not v]
        if empty_fields:
            print(f"\nEmpty fields: {empty_fields}")
        else:
            print("\nAll metadata fields were populated successfully!")
    
    except Exception as e:
        print(f"Error reading metadata: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_metadata.py path/to/your/file.wav")
        sys.exit(1)
    
    wav_path = sys.argv[1]
    test_file(wav_path)

if __name__ == "__main__":
    main() 