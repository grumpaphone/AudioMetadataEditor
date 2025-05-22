#!/usr/bin/env python3
import os

print("Creating a backup of app.py...")
os.system("cp app.py app.py.bak2")

# Let's use a line-by-line approach for safer editing
with open('app.py', 'r') as f:
    lines = f.readlines()

# Flag to track when we're inside the problematic section
in_problem_section = False
fixed_lines = []

for i, line in enumerate(lines):
    # Look for the start of the problematic section (around line 1528)
    if "elif 1 <= col <= 9:  # Metadata columns" in line:
        in_problem_section = True
        fixed_lines.append(line)  # Keep the elif line as is
        # The next few lines need their indentation fixed
        continue
    
    # Look for the end of the problematic section
    if in_problem_section and "undo_redo_stack.push(command)" in line:
        in_problem_section = False
        # Ensure proper indentation for this line (should be aligned with the 'if new_value != old_value:' line)
        fixed_lines.append(line.replace("                    ", "                "))
        continue
    
    # Fix indentation for lines in the problematic section
    if in_problem_section:
        # Check if this line is a comment or code that needs to be fixed
        if "# Map column indices to metadata keys" in line:
            fixed_lines.append(line.replace("            # ", "                # "))
        elif "metadata_keys = " in line:
            fixed_lines.append(line.replace("            ", "                "))
        elif '"Subcategory"' in line:
            fixed_lines.append(line.replace("                           ", "                           "))
        elif "# Get the metadata key and old value" in line:
            fixed_lines.append(line.replace("                # ", "                # "))
        elif "key = metadata_keys" in line:
            fixed_lines.append(line.replace("            ", "                "))
        elif "old_value = metadata.get" in line:
            fixed_lines.append(line.replace("                ", "                "))
        elif "# Only update if the value has changed" in line:
            fixed_lines.append(line.replace("                # ", "                # "))
        elif "if new_value != old_value:" in line:
            fixed_lines.append(line.replace("                ", "                "))
        elif "# Create and push the command to the stack" in line:
            fixed_lines.append(line.replace("                    # ", "                    # "))
        else:
            # Keep other lines as they are
            fixed_lines.append(line)
    else:
        # Outside the problematic section, handle other specific issues
        if "self.mapping_preview.clear()" in line and "def update_mapping_preview" in lines[max(0, i-5):i]:
            # Fix indentation issue around line 4825
            fixed_lines.append(line.replace("self.mapping_preview", "    self.mapping_preview"))
        elif "self.field_mappings = {}" in line and "if not hasattr" in lines[max(0, i-2):i]:
            # Fix indentation around line 4836
            fixed_lines.append(line.replace("self.field_mappings", "    self.field_mappings"))
        elif "for csv_field, wav_field in self.field_mappings.items():" in line and "if self.field_mappings:" in lines[max(0, i-2):i]:
            # Fix indentation around line 4853
            fixed_lines.append(line.replace("for csv_field", "    for csv_field"))
        elif "mappings_count = len(self.field_mappings)" in line and "parentWidget" in line:
            # Fix indentation in line 4863
            fixed_lines.append(line.replace("mappings_count", "        mappings_count"))
        elif "preview_title = f\"Mapping Preview ({mappings_count} mappings)\"" in line:
            # Fix indentation in line 4864
            fixed_lines.append(line.replace("preview_title", "        preview_title"))
        elif "self.mapping_preview.parentWidget().setTitle(preview_title)" in line:
            # Fix indentation in line 4865
            fixed_lines.append(line.replace("self.mapping_preview", "        self.mapping_preview"))
        else:
            # Keep other lines as they are
            fixed_lines.append(line)

# Write the fixed content back to a new file
with open('app.py.fixed2', 'w') as f:
    f.writelines(fixed_lines)

print("Fixed syntax issues and wrote to app.py.fixed2")
print("To apply the fix, run: mv app.py.fixed2 app.py")
