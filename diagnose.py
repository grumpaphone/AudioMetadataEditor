#!/usr/bin/env python3
"""
Diagnostic tool for WAV metadata reading
"""
import os
import sys
import traceback
from wavinfo import WavInfoReader
import xml.etree.ElementTree as ET


def analyze_wav_file(file_path):
    """Analyze a WAV file and print detailed info about its metadata structure"""
    print(f"\n{'='*80}\nAnalyzing WAV file: {file_path}\n{'='*80}")
    
    try:
        # Basic file info
        print(f"File size: {os.path.getsize(file_path)} bytes")
        print(f"File exists: {os.path.exists(file_path)}")
        
        # Try to load with wavinfo
        print("\nAttempting to load with WavInfoReader...")
        wav_info = WavInfoReader(file_path)
        
        # Print ALL available attributes and their raw values
        print("\nRAW WavInfoReader contents:")
        for attr in dir(wav_info):
            if not attr.startswith('__'):
                try:
                    value = getattr(wav_info, attr)
                    print(f"  - {attr}: {repr(value)} (type: {type(value)})")
                except Exception as e:
                    print(f"  - {attr}: ERROR accessing - {e}")
        
        # Check for BWF/BEXT chunk
        print("\nBWF/BEXT chunk information:")
        if hasattr(wav_info, 'bext'):
            print("  BEXT chunk found")
            bext = wav_info.bext
            print("  BEXT attributes:")
            for attr in dir(bext):
                if not attr.startswith('__'):
                    try:
                        value = getattr(bext, attr)
                        print(f"    - {attr}: {value}")
                    except Exception as e:
                        print(f"    - {attr}: ERROR accessing - {e}")
        else:
            print("  No BEXT chunk found")
        
        # Check for iXML chunk
        print("\niXML chunk information:")
        if hasattr(wav_info, 'ixml'):
            print("  iXML chunk found")
            ixml = wav_info.ixml
            print(f"  iXML type: {type(ixml)}")
            
            try:
                if hasattr(ixml, 'to_dict'):
                    print("  iXML has to_dict method")
                    ixml_dict = ixml.to_dict()
                    print(f"  iXML dict type: {type(ixml_dict)}")
                    if ixml_dict and isinstance(ixml_dict, dict):
                        print("  iXML dict keys:")
                        for key, value in ixml_dict.items():
                            print(f"    - {key}: {value}")
                    else:
                        print(f"  iXML dict is invalid: {ixml_dict}")
                else:
                    print("  iXML does NOT have to_dict method")
                    if isinstance(ixml, str):
                        print(f"  iXML is a string, length: {len(ixml)}")
                    elif isinstance(ixml, bytes):
                        print(f"  iXML is bytes, length: {len(ixml)}")
                    else:
                        print(f"  iXML is type: {type(ixml)}")
            except Exception as e:
                print(f"  Error examining iXML: {e}")
                traceback.print_exc()
        else:
            print("  No iXML chunk found")
        
        print("\nAttempting to extract metadata...")
        metadata = extract_metadata(wav_info, file_path)
        print("Extracted metadata:")
        for key, value in metadata.items():
            print(f"  - {key}: {value}")
        
    except Exception as e:
        print(f"Error analyzing file: {e}")
        traceback.print_exc()


def extract_metadata(wav_info, file_path):
    """Extract metadata from WAV file (debug version)"""
    # Initialize metadata dictionary with empty values
    metadata = {
        "Filename": os.path.basename(file_path),
        "Scene": "",
        "Take": "",
        "Category": "",
        "Subcategory": "",
        "ixmlNote": "",
        "ixmlCircled": "",
        "File Path": file_path
    }
    
    # Extract BWAV metadata if available
    try:
        print("Extracting BEXT metadata...")
        if hasattr(wav_info, 'bext'):
            # Map BWAV fields to our metadata structure
            bext = wav_info.bext
            if hasattr(bext, 'scene'):
                metadata["Scene"] = bext.scene
                print(f"  Got Scene: {bext.scene}")
            if hasattr(bext, 'take'):
                metadata["Take"] = bext.take
                print(f"  Got Take: {bext.take}")
    except Exception as e:
        print(f"Error extracting BEXT metadata: {e}")
    
    # Extract iXML metadata if available
    try:
        print("Extracting iXML metadata...")
        if hasattr(wav_info, 'ixml'):
            ixml_str = wav_info.ixml
            print(f"  iXML type: {type(ixml_str)}")
            
            if ixml_str:
                # Try using to_dict if available
                if hasattr(ixml_str, 'to_dict'):
                    print("  Using to_dict method")
                    try:
                        ixml_dict = ixml_str.to_dict()
                        print(f"  Dict result: {type(ixml_dict)}")
                        
                        if ixml_dict and isinstance(ixml_dict, dict):
                            for key in ['CATEGORY', 'SUBCATEGORY', 'NOTE', 'CIRCLED']:
                                if key in ixml_dict:
                                    if key == 'CATEGORY':
                                        metadata["Category"] = str(ixml_dict[key])
                                        print(f"  Got Category: {ixml_dict[key]}")
                                    elif key == 'SUBCATEGORY':
                                        metadata["Subcategory"] = str(ixml_dict[key])
                                        print(f"  Got Subcategory: {ixml_dict[key]}")
                                    elif key == 'NOTE':
                                        metadata["ixmlNote"] = str(ixml_dict[key])
                                        print(f"  Got Note: {ixml_dict[key]}")
                                    elif key == 'CIRCLED':
                                        metadata["ixmlCircled"] = str(ixml_dict[key])
                                        print(f"  Got Circled: {ixml_dict[key]}")
                    except Exception as e:
                        print(f"  Error using to_dict: {e}")
                
                # Try using ElementTree if to_dict failed or isn't available
                else:
                    print("  Using ElementTree parsing")
                    try:
                        # If it's a string, encode it
                        if isinstance(ixml_str, str):
                            ixml_str = ixml_str.encode('utf-8')
                            print("  Encoded string to bytes")
                        
                        if ixml_str:
                            root = ET.fromstring(ixml_str)
                            print(f"  Parsed XML root: {root.tag}")
                            
                            for path, metadata_key in [
                                (".//CATEGORY", "Category"),
                                (".//SUBCATEGORY", "Subcategory"),
                                (".//NOTE", "ixmlNote"),
                                (".//CIRCLED", "ixmlCircled")
                            ]:
                                element = root.find(path)
                                if element is not None and element.text:
                                    metadata[metadata_key] = element.text
                                    print(f"  Got {metadata_key}: {element.text}")
                    except Exception as e:
                        print(f"  Error parsing XML: {e}")
    except Exception as e:
        print(f"Error extracting iXML metadata: {e}")
    
    return metadata


def main():
    """Main function to run the diagnostic tool"""
    if len(sys.argv) < 2:
        print("Usage: python diagnose.py <wav_file_or_directory>")
        sys.exit(1)
    
    path = sys.argv[1]
    
    if os.path.isfile(path) and path.lower().endswith('.wav'):
        analyze_wav_file(path)
    elif os.path.isdir(path):
        # Find first 3 wav files in the directory
        wav_files = []
        for root, _, files in os.walk(path):
            for file in files:
                if file.lower().endswith('.wav'):
                    wav_files.append(os.path.join(root, file))
                    if len(wav_files) >= 3:
                        break
            if len(wav_files) >= 3:
                break
        
        if not wav_files:
            print(f"No WAV files found in {path}")
            sys.exit(1)
        
        print(f"Found {len(wav_files)} WAV files, analyzing...")
        for wav_file in wav_files:
            analyze_wav_file(wav_file)
    else:
        print(f"Invalid path: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main() 