import unittest
import json
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the WAHelper class from your module.
from waveassist import WAHelper
import random
import string

class TestWAHelper(unittest.TestCase):
    def setUp(self):
        self.uid = "14fe5bcd-8a50-43a6-b431-1b72b839cc06"
        self.project_key = "tp"
        self.data_key = "test_data"
        self.helper = WAHelper(self.uid)

    def random_string(self, length=8):
        """Generate a random string."""
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def test_set_and_get_dataframe_success(self):
        """Success Case: Set DataFrame, get DataFrame, and compare values."""
        # Create a random DataFrame
        df = pd.DataFrame([
            {"col1": self.random_string(), "col2": self.random_string()},
            {"col1": self.random_string(), "col2": self.random_string()},
        ])

        # Save the DataFrame
        save_result = self.helper.set_dataframe(df, self.project_key, self.data_key)
        self.assertTrue(save_result, "Failed to save DataFrame.")

        # Retrieve the DataFrame
        retrieved_df = self.helper.get_dataframe(self.project_key, self.data_key)

        # Ensure the retrieved DataFrame matches the original
        pd.testing.assert_frame_equal(df, retrieved_df)

    def test_set_invalid_data(self):
        """Failure Case: Try to set an invalid (non-DataFrame) value."""
        invalid_data = {"col1": "invalid", "col2": "data"}  # Not a DataFrame

        with self.assertRaises(ValueError) as context:
            self.helper.set_dataframe(invalid_data, self.project_key, self.data_key,)

        self.assertIn("The argument must be a DataFrame.", str(context.exception))


if __name__ == "__main__":
    unittest.main()
