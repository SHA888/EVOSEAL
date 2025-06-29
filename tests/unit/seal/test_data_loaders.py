"""Tests for the data loaders module."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

from pydantic import BaseModel

from evoseal.integration.seal.data_loaders import (
    CSVLoader,
    DataCache,
    DataFormat,
    DataLoader,
    JSONLoader,
    YAMLLoader,
    cached,
    load_batch,
    load_data,
)


# Test models
class TestModel(BaseModel):
    """Test model for data loading."""

    id: int
    name: str
    active: bool = True


class TestDataLoaders(unittest.TestCase):
    """Test cases for data loaders."""

    def setUp(self):
        """Set up test data."""
        self.test_data = [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2", "active": False},
            {"id": 3, "name": "Item 3"},
        ]
        self.test_model = TestModel

        # Create a temporary directory for test files
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create test files
        self.json_file = self.temp_path / "test.json"
        self.yaml_file = self.temp_path / "test.yaml"
        self.csv_file = self.temp_path / "test.csv"

        # Write test data to files
        self.json_file.write_text(
            '''
        [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2", "active": false},
            {"id": 3, "name": "Item 3"}
        ]
        '''
        )

        self.yaml_file.write_text(
            '''
        - id: 1
          name: Item 1
        - id: 2
          name: Item 2
          active: false
        - id: 3
          name: Item 3
        '''
        )

        self.csv_file.write_text(
            '''id,name,active
1,Item 1,true
2,Item 2,false
3,Item 3,true
'''
        )

    def tearDown(self):
        """Clean up test files."""
        self.temp_dir.cleanup()

    def test_json_loader(self):
        """Test JSON loader."""
        loader = JSONLoader[TestModel]()
        content = self.json_file.read_text()
        result = loader.from_string(content, DataFormat.JSON, TestModel)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], TestModel)
        self.assertEqual(result[0].id, 1)
        self.assertEqual(result[1].active, False)

    def test_yaml_loader(self):
        """Test YAML loader."""
        loader = YAMLLoader[TestModel]()
        content = self.yaml_file.read_text()
        result = loader.from_string(content, DataFormat.YAML, TestModel)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], TestModel)
        self.assertEqual(result[0].id, 1)
        self.assertEqual(result[1].active, False)

    def test_csv_loader(self):
        """Test CSV loader."""
        loader = CSVLoader[TestModel]()
        content = self.csv_file.read_text()
        result = loader.from_string(content, DataFormat.CSV, TestModel)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], TestModel)
        self.assertEqual(result[0].id, 1)
        self.assertEqual(result[1].active, False)

    def test_load_data_json(self):
        """Test load_data with JSON file."""
        result = load_data(self.json_file, TestModel)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], TestModel)

    def test_load_data_yaml(self):
        """Test load_data with YAML file."""
        result = load_data(self.yaml_file, TestModel, format="yaml")
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], TestModel)

    def test_load_data_csv(self):
        """Test load_data with CSV file."""
        result = load_data(self.csv_file, TestModel, format="csv")
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], TestModel)

    def test_batch_loading(self):
        """Test batch loading of multiple files."""
        files = [self.json_file, self.yaml_file, self.csv_file]
        results = load_batch(files, TestModel, max_workers=2)
        # Each file has 3 items, but CSV has an extra header row that's skipped
        self.assertEqual(len(results), 9)  # 3 files × 3 items each

    def test_caching(self):
        """Test caching functionality."""
        # Create a test cache
        cache = DataCache()

        # Test cache miss
        self.assertIsNone(cache.get("test_key"))

        # Test cache set and get
        cache.set("test_key", "test_value")
        self.assertEqual(cache.get("test_key"), "test_value")

        # Test cache clear
        cache.clear()
        self.assertIsNone(cache.get("test_key"))

    def test_cached_decorator(self):
        """Test the @cached decorator."""
        call_count = 0

        @cached
        def get_data():
            nonlocal call_count
            call_count += 1
            return [1, 2, 3]

        # First call should increment call_count
        result1 = get_data()
        self.assertEqual(call_count, 1)
        self.assertEqual(result1, [1, 2, 3])

        # Second call should use cache
        result2 = get_data()
        self.assertEqual(call_count, 1)  # Should still be 1
        self.assertEqual(result2, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
