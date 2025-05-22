#!/usr/bin/env python3

import re

# Read the app.py file
with open('app.py', 'r') as f:
    content = f.read()

# First, fix the show_field_menu method to use set_search_field instead of select_search_field
content = content.replace(
    "action.triggered.connect(lambda checked, f=field: self.select_search_field(f))",
    "action.triggered.connect(lambda checked, f=field: self.set_search_field(f))"
)

# Next, fix the search field dropdown UI layout
# Find the search field section and replace it with our fixed version
pattern = r'(\s+# Integrated search field with dropdown\n\s+search_frame = QFrame\(\)[\s\S]*?search_frame_layout\.addWidget\(field_indicator\)\n\s+search_frame_layout\.addWidget\(dropdown_button\))'

replacement = '''        # Integrated search field with dropdown
        search_frame = QFrame()
        search_frame.setObjectName("search_frame")
        search_frame.setStyleSheet("""
            #search_frame {
                background-color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(224, 216, 201, 0.8);
                border-radius: 6px;
            }
        """)
        
        search_frame_layout = QHBoxLayout(search_frame)
        search_frame_layout.setContentsMargins(5, 0, 5, 0)
        search_frame_layout.setSpacing(0)
        
        # First add the search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(180)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                padding: 4px;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.filter_table)
        
        # Create a container for the field indicator and dropdown button
        dropdown_container = QWidget()
        dropdown_container.setFixedWidth(60)
        dropdown_layout = QHBoxLayout(dropdown_container)
        dropdown_layout.setContentsMargins(0, 0, 0, 0)
        dropdown_layout.setSpacing(0)
        
        # Field indicator and dropdown button
        field_indicator = QLabel("All")
        field_indicator.setObjectName("field_indicator")
        field_indicator.setStyleSheet("""
            #field_indicator {
                color: #666;
                padding-right: 0px;
            }
        """)
        
        dropdown_button = QPushButton("▾")
        dropdown_button.setObjectName("dropdown_button")
        dropdown_button.setFixedWidth(20)
        dropdown_button.setStyleSheet("""
            #dropdown_button {
                border: none;
                background: transparent;
                color: #666;
                padding: 0 5px 0 0;
                text-align: center;
                font-size: 10px;
            }
            #dropdown_button:hover {
                color: #333;
            }
        """)
        dropdown_button.clicked.connect(self.show_field_menu)
        
        # Add components to the dropdown container
        dropdown_layout.addWidget(field_indicator)
        dropdown_layout.addWidget(dropdown_button)
        
        # Add both components to the search frame layout in the correct order
        search_frame_layout.addWidget(self.search_input)
        search_frame_layout.addWidget(dropdown_container)'''

# Apply the replacement for the search field
modified_content = re.sub(pattern, replacement, content)

# Fix the available field options in the show_field_menu method
search_field_pattern = r'(\s+def show_field_menu\(self\):\n\s+"""Show a menu to select which field to search in"""\n\s+menu = QMenu\(self\)\n\s+)for field in \["All Fields", "Filename", "Scene", "Take", "Description", "Notes"\]:'

search_field_replacement = r'\1for field in ["All Fields", "Filename", "Scene", "Take", "Category", "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]:'

# Apply the replacement for the search fields
modified_content = re.sub(search_field_pattern, search_field_replacement, modified_content)

# Fix the indentation in the update_metadata method
indentation_pattern = r'(\s+elif 1 <= col <= 9:  # Metadata columns\n\s+)# Map column indices to metadata keys\n\s+metadata_keys = \["Show", "Scene", "Take", "Category", \n(\s+)"Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"\]\n\s+\n(\s+)# Get the metadata key and old value\n\s+key = metadata_keys\[col - 1\]  # -1 to account for filename column\n(\s+)old_value = metadata\.get\(key, ""\)\n\s+\n(\s+)# Only update if the value has changed\n\s+if new_value != old_value:\n\s+# Create and push the command to the stack\n\s+command = MetadataEditCommand\(self, actual_row, key, old_value, new_value\)\n\s+self\.undo_redo_stack\.push\(command\)'

indentation_replacement = r'\1# Map column indices to metadata keys\n                metadata_keys = ["Show", "Scene", "Take", "Category", \n                               "Subcategory", "Slate", "ixmlNote", "ixmlWildtrack", "ixmlCircled"]\n                \n                # Get the metadata key and old value\n                key = metadata_keys[col - 1]  # -1 to account for filename column\n                old_value = metadata.get(key, "")\n                \n                # Only update if the value has changed\n                if new_value != old_value:\n                    # Create and push the command to the stack\n                    command = MetadataEditCommand(self, actual_row, key, old_value, new_value)\n                    self.undo_redo_stack.push(command)'

# Apply the replacement for the indentation issues
modified_content = re.sub(indentation_pattern, indentation_replacement, modified_content)

# Fix indentation issues in update_mapping_preview method
mapping_preview_pattern = r'(\s+# Handle QListWidget \(used in entry_match_page\)\n\s+elif isinstance\(self\.mapping_preview, QListWidget\):\n\s+)self\.mapping_preview\.clear\(\)'
mapping_preview_replacement = r'\1    self.mapping_preview.clear()'
modified_content = re.sub(mapping_preview_pattern, mapping_preview_replacement, modified_content)

field_mappings_pattern = r'(\s+# Ensure field_mappings is a dictionary\n\s+if not hasattr\(self, \'field_mappings\'\):\n\s+)self\.field_mappings = \{\}'
field_mappings_replacement = r'\1    self.field_mappings = {}'
modified_content = re.sub(field_mappings_pattern, field_mappings_replacement, modified_content)

display_mappings_pattern = r'(\s+# Display current mappings in the preview\n\s+if self\.field_mappings:\n\s+)for csv_field, wav_field in self\.field_mappings\.items\(\):'
display_mappings_replacement = r'\1    for csv_field, wav_field in self.field_mappings.items():'
modified_content = re.sub(display_mappings_pattern, display_mappings_replacement, modified_content)

mappings_count_pattern = r'(\s+# Update title with count\n\s+if hasattr\(self\.mapping_preview, \'parentWidget\'\) and self\.mapping_preview\.parentWidget\(\):\n\s+)mappings_count = len\(self\.field_mappings\)'
mappings_count_replacement = r'\1        mappings_count = len(self.field_mappings)'
modified_content = re.sub(mappings_count_pattern, mappings_count_replacement, modified_content)

# Fix indentation issue around line 4834
field_mapping_controls_pattern = r'(\s+# Update field_mappings from current UI state\n\s+if hasattr\(self, \'field_mapping_controls\'\):\n\s+)self\.field_mappings\.clear\(\)  # Reset mappings\n\s+for csv_field, dropdown, checkbox in self\.field_mapping_controls:'
field_mapping_controls_replacement = r'\1                self.field_mappings.clear()  # Reset mappings\n                for csv_field, dropdown, checkbox in self.field_mapping_controls:'
modified_content = re.sub(field_mapping_controls_pattern, field_mapping_controls_replacement, modified_content)

# Fix additional indentation issues that might be related to the above
if_checkbox_pattern = r'(\s+for csv_field, dropdown, checkbox in self\.field_mapping_controls:\n\s+)if checkbox\.isChecked\(\) and dropdown\.currentText\(\):'
if_checkbox_replacement = r'\1                    if checkbox.isChecked() and dropdown.currentText():'
modified_content = re.sub(if_checkbox_pattern, if_checkbox_replacement, modified_content)

wav_field_pattern = r'(\s+if checkbox\.isChecked\(\) and dropdown\.currentText\(\):\n\s+)wav_field = dropdown\.currentText\(\)\n\s+self\.field_mappings\[csv_field\] = wav_field'
wav_field_replacement = r'\1                        wav_field = dropdown.currentText()\n                        self.field_mappings[csv_field] = wav_field'
modified_content = re.sub(wav_field_pattern, wav_field_replacement, modified_content)

# Write the modified content back to the file
with open('app.py', 'w') as f:
    f.write(modified_content)

print("Fixed search dropdown positioning, field list and all indentation issues in app.py") 