#!/usr/bin/env python3
"""
Diagnostic Tool for WAV Metadata

This script analyzes WAV files and provides diagnostics about metadata structure and content.
"""

import os
import sys
import glob
import argparse
import time
import json
from concurrent.futures import ThreadPoolExecutor
# from functools import partial # Unused import
import multiprocessing
import traceback
from wavinfo import WavInfoReader


def analyze_wav_file(wav_path, debug=False):
    """Analyze a single WAV file and return its structure."""
    try:
        start_time = time.time()
        result = {
            "file_path": wav_path,
            "file_size": os.path.getsize(wav_path),
            "chunks": {},
            "errors": [],
            "metadata": {},
            "analysis_time_ms": 0
        }
        
        # Read the WAV file using wavinfo
        try:
            wav_info = WavInfoReader(wav_path)
            
            # Get available chunks
            for attr_name in dir(wav_info):
                if attr_name.startswith('__'):
                    continue
                
                try:
                    attr = getattr(wav_info, attr_name)
                    if attr_name in ('bext', 'ixml'):
                        result["chunks"][attr_name] = {
                            "present": attr is not None,
                            "type": str(type(attr)),
                            "attributes": [a for a in dir(attr) if not a.startswith('__')] if attr else []
                        }
                except Exception as e:
                    result["errors"].append(f"Error reading {attr_name} chunk: {str(e)}")
            
            # Extract basic metadata
            if hasattr(wav_info, 'bext') and wav_info.bext:
                bext = wav_info.bext
                result["metadata"]["bext"] = {}
                for attr_name in dir(bext):
                    if not attr_name.startswith('__'):
                        try:
                            attr_value = getattr(bext, attr_name)
                            if isinstance(attr_value, (str, int, float, bool)) or attr_value is None:
                                result["metadata"]["bext"][attr_name] = attr_value
                        except Exception as e:
                            result["errors"].append(f"Error reading bext.{attr_name}: {str(e)}")
            
            if hasattr(wav_info, 'ixml') and wav_info.ixml:
                result["metadata"]["ixml"] = {"raw_type": str(type(wav_info.ixml))}
                
                # Try to extract some basic info about iXML
                ixml = wav_info.ixml
                if hasattr(ixml, 'to_dict') and callable(ixml.to_dict):
                    try:
                        result["metadata"]["ixml"]["has_to_dict"] = True
                        # Don't actually call to_dict() as it can be slow or error-prone
                    except Exception as e:
                        result["metadata"]["ixml"]["to_dict_error"] = str(e)
                else:
                    result["metadata"]["ixml"]["has_to_dict"] = False
                
                # Check if iXML has direct properties
                for attr_name in ['CIRCLED', 'NOTE', 'TAKE', 'SCENE', 'CATEGORY', 'SUBCATEGORY']:
                    if hasattr(ixml, attr_name):
                        try:
                            result["metadata"]["ixml"][attr_name] = getattr(ixml, attr_name)
                        except Exception as e:
                            result["errors"].append(f"Error reading ixml.{attr_name}: {str(e)}")
        except Exception as e:
            result["errors"].append(f"Error reading WAV file: {str(e)}")
            if debug:
                traceback.print_exc()
        
        # Calculate analysis time
        result["analysis_time_ms"] = int((time.time() - start_time) * 1000)
        return result
        
    except Exception as e:
        # Completely unexpected error
        return {
            "file_path": wav_path,
            "errors": [f"Fatal error during analysis: {str(e)}"],
            "analysis_time_ms": int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
        }


def analyze_files(file_paths, output=None, debug=False, max_workers=None, print_progress=True):
    """Analyze multiple WAV files in parallel."""
    results = []
    total_files = len(file_paths)
    
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 1)  # Leave one CPU free
    
    start_time = time.time()
    
    # Define a callback function for progress reporting
    def update_progress(i, result):
        if print_progress and (i % 10 == 0 or i == total_files - 1):
            errors = len(result.get("errors", []))
            filename = os.path.basename(result["file_path"])
            status = "✓" if errors == 0 else f"✗ ({errors} errors)"
            percent = int((i + 1) / total_files * 100)
            elapsed = time.time() - start_time
            remaining = (elapsed / (i + 1)) * (total_files - i - 1) if i > 0 else 0
            
            sys.stdout.write(f"\r[{percent:3d}%] {i+1}/{total_files} | {filename} {status} | "
                             f"Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s")
            sys.stdout.flush()
    
    # Process files in batches to control memory usage
    batch_size = 100
    for start_idx in range(0, total_files, batch_size):
        end_idx = min(start_idx + batch_size, total_files)
        batch = file_paths[start_idx:end_idx]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Use a dict to preserve order
            futures = {executor.submit(analyze_wav_file, path, debug): i 
                      for i, path in enumerate(batch, start=start_idx)}
            
            for future in futures:
                i = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    update_progress(i, result)
                except Exception as e:
                    results.append({
                        "file_path": file_paths[i],
                        "errors": [f"Exception during analysis: {str(e)}"]
                    })
                    if debug:
                        traceback.print_exc()
                    update_progress(i, {"file_path": file_paths[i], "errors": [str(e)]})
    
    if print_progress:
        print()  # New line after progress
    
    # Write results to output file if specified
    if output:
        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
        except IOError as e:
            print(f"Error writing output file {output}: {e}", file=sys.stderr)
    
    # Print summary
    total_time = time.time() - start_time
    error_count = sum(1 for r in results if r.get("errors"))
    
    # Use regular string for f-string-without-interpolation warning
    print("\nAnalysis complete:")
    print(f"- Processed {len(results)} files in {total_time:.2f} seconds")
    print(f"- Files with errors: {error_count}")
    if total_files > 0:
        print(f"- Average time per file: {(total_time / total_files) * 1000:.1f} ms")
    else:
        print("- Average time per file: N/A (no files processed)")
    
    if output:
        print(f"- Detailed results saved to: {output}")
    
    return results


def main():
    """Main function for the diagnostic tool."""
    parser = argparse.ArgumentParser(description="Diagnostic tool for WAV metadata")
    parser.add_argument("path", help="Path to WAV file or directory containing WAV files")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursively search for WAV files in directories")
    parser.add_argument("--output", "-o", help="Output JSON file for detailed results")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    parser.add_argument("--workers", "-w", type=int, help="Number of worker threads (default: CPU count - 1)")
    
    args = parser.parse_args()
    
    # Check if path exists
    if not os.path.exists(args.path):
        print(f"Error: Path does not exist: {args.path}")
        return 1
    
    # Collect files to analyze
    if os.path.isfile(args.path):
        # Single file
        if not args.path.lower().endswith('.wav'):
            print(f"Error: Not a WAV file: {args.path}")
            return 1
        
        files = [args.path]
    else:
        # Directory - find WAV files
        pattern = "**/*.wav" if args.recursive else "*.wav"
        files = glob.glob(os.path.join(args.path, pattern), recursive=args.recursive)
        
        if not files:
            print(f"Error: No WAV files found in {args.path}")
            return 1
    
    print(f"Found {len(files)} WAV files to analyze")
    analyze_files(files, args.output, args.debug, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
