#!/usr/bin/env python3

print("Fixing the app.py file indentation")

# Read the file line by line
with open('app.py', 'r') as f:
    lines = f.readlines()

# Make a backup of the original file
with open('app.py.backup_indent', 'w') as f:
    f.writelines(lines)

# Find the problem area and fix it
fixed_code = []
for i, line in enumerate(lines):
    # Look for the problematic section specifically
    if "elif 1 <= col <= 9:" in line:
        fixed_code.append(line)  # Keep the elif line as is
        
        # Check the next two lines
        if i+1 < len(lines) and i+2 < len(lines):
            if "# Map column indices" in lines[i+1]:
                # Fix indentation of the column indices comment
                fixed_code.append("                # Map column indices to metadata keys\n")
                
                # Fix indentation of the metadata_keys array
                md_keys_line = lines[i+2].strip()
                fixed_code.append(f"                {md_keys_line}\n")
                
                # Skip these lines since we've already processed them
                i += 2
                continue
    elif "metadata_keys = [" in line and "# Map column indices" in lines[i-1]:
        # We've already handled this
        continue
    else:
        # For all other lines, just add them as they are
        fixed_code.append(line)

# Write the fixed content back to the file
with open('app.py', 'w') as f:
    f.writelines(fixed_code)

print("Fix complete - indentation issue should be resolved") 