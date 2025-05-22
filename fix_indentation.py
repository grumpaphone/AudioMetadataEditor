#!/usr/bin/env python3

import re

print("Creating a backup of app.py")
import shutil
shutil.copy2('app.py', 'app.py.bak.indent')

# Read the file line by line
with open('app.py', 'r') as f:
    lines = f.readlines()

# Find and fix the problematic indentation
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Look for the start of the problematic section
    if "elif 1 <= col <= 9:" in line:
        fixed_lines.append(line)  # Add the elif line
        i += 1  # Move to next line
        
        # Fix the indentation for the metadata_keys block
        if i < len(lines) and "metadata_keys" in lines[i]:
            # This is where the indentation is wrong
            # Make sure it's indented properly
            fixed_line = "                # Map column indices to metadata keys\n"
            fixed_lines.append(fixed_line)
            
            # Add the metadata_keys line with correct indentation
            metadata_keys_line = lines[i].lstrip()
            fixed_lines.append("                " + metadata_keys_line)
            
            # Continue with the rest of the section
            i += 1
            while i < len(lines) and i < len(lines) and "key = metadata_keys" not in lines[i]:
                # Fix indentation for all lines until we reach the key assignment
                stripped = lines[i].lstrip()
                if stripped:  # Only add non-empty lines
                    fixed_lines.append("                " + stripped)
                i += 1
            
            # Add the key assignment line and the rest with proper indentation
            if i < len(lines):
                fixed_lines.append("                " + lines[i].lstrip())
                i += 1
                
                # Continue adding with proper indentation until we hit another major section
                while i < len(lines) and "command = MetadataEditCommand" not in lines[i]:
                    stripped = lines[i].lstrip()
                    if stripped:  # Only add non-empty lines
                        fixed_lines.append("                " + stripped)
                    i += 1
                
                # Add the command line with proper indentation
                if i < len(lines):
                    fixed_lines.append("                    " + lines[i].lstrip())
                    i += 1
                    
                    # Add the undo_redo_stack line with proper indentation
                    if i < len(lines) and "undo_redo_stack.push" in lines[i]:
                        fixed_lines.append("                    " + lines[i].lstrip())
                        i += 1
                    
        else:
            # If we didn't find the expected pattern, just add the line as is
            fixed_lines.append(line)
    else:
        # For all other lines, just add them unchanged
        fixed_lines.append(line)
        i += 1

# Write the fixed file
with open('app.py', 'w') as f:
    f.writelines(fixed_lines)

print("Fixed indentation issues in app.py")
print("Now you can run the dark_mode_toggle.py script to add dark mode functionality") 