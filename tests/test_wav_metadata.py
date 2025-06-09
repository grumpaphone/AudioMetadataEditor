import unittest
import os
import sys

# Add the parent directory to sys.path to allow importing wav_metadata
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import wav_metadata

class TestWavMetadata(unittest.TestCase):
    """Test suite for wav_metadata.py functions."""

    def test_read_metadata_non_existent_file(self):
        """Test reading metadata from a non-existent file."""
        non_existent_path = "tests/fixtures/non_existent_file.wav"
        # Ensure the file truly doesn't exist for a clean test
        if os.path.exists(non_existent_path):
            os.remove(non_existent_path)

        result = wav_metadata.read_wav_metadata(non_existent_path, debug=False)
        self.assertIsNotNone(result.get("Error"), "Error key should be present for non-existent file.")
        self.assertIn("File not found", result["Error"], "Error message should indicate file not found.")

    def test_read_metadata_empty_file(self):
        """Test reading metadata from an empty file."""
        empty_file_path = "tests/fixtures/empty.wav"
        # Ensure the empty file exists (created in a previous step)
        self.assertTrue(os.path.exists(empty_file_path), "Empty fixture file should exist.")

        result = wav_metadata.read_wav_metadata(empty_file_path, debug=False)
        self.assertIsNotNone(result.get("Error"), "Error key should be present for an empty file.")
        self.assertIn("File too small", result["Error"], "Error message should indicate file is too small.")

    # Optional: Test with a minimal valid WAV.
    # This would require creating a fixture file with a valid WAV header and minimal data,
    # or using mocking, which might be complex with the current tool limitations.
    # For now, we'll skip this more complex test.

if __name__ == '__main__':
    unittest.main()
