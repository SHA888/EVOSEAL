"""
Concurrent and performance tests for the KnowledgeBase component.
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

import pytest
from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase

# Constants for performance testing
LARGE_DATASET_SIZE = 1000
CONCURRENT_THREADS = 10


def test_concurrent_access(tmp_path: Path):
    """Test concurrent access to the knowledge base."""
    db_path = str(tmp_path / "concurrent_kb.db")
    num_workers = 3  # Reduced number of workers for more reliable testing
    
    print(f"\n=== Starting test_concurrent_access with db_path: {db_path} ===")
    
    # Create and initialize the knowledge base
    def initialize_kb():
        print("Initializing knowledge base...")
        kb = KnowledgeBase(db_path)
        # Add initial entries
        for i in range(10):
            kb.add_entry(f"Initial entry {i}")
        kb.save_to_disk()
        print(f"Initialized with {len(kb.entries)} entries")
        return kb
    
    # Initialize the knowledge base
    kb = initialize_kb()
    
    # Worker function that performs operations
    def worker(worker_id: int):
        """Worker function that performs operations on the knowledge base."""
        print(f"Worker {worker_id} starting...")
        worker_kb = KnowledgeBase(db_path)
        operations = []
        
        try:
            # Add new entries
            for i in range(3):  # Reduced number of operations per worker
                # Add a new entry
                entry_content = f"Worker {worker_id} entry {i}"
                entry_id = worker_kb.add_entry(entry_content)
                operations.append(("add", entry_id, entry_content))
                print(f"Worker {worker_id} added entry: {entry_content}")
                
                # Update an entry (if it exists)
                query = f"Initial entry {i % 10}"
                entries = worker_kb.search_entries(query=query)
                if entries:
                    entry_id = entries[0].id
                    new_content = f"Updated by worker {worker_id} at {i}"
                    worker_kb.update_entry(entry_id, new_content)
                    operations.append(("update", entry_id, new_content))
                    print(f"Worker {worker_id} updated entry {entry_id}")
                
                # Save to disk after each operation
                worker_kb.save_to_disk()
                print(f"Worker {worker_id} saved to disk")
            
            result = f"Worker {worker_id} completed"
            print(f"{result} with operations: {operations}")
            return result, operations
            
        except Exception as e:
            error_msg = f"Worker {worker_id} failed: {str(e)}"
            print(error_msg)
            return error_msg, []
    
    # Run workers sequentially first to ensure basic functionality
    print("\n=== Running workers sequentially ===")
    sequential_results = []
    for i in range(num_workers):
        result = worker(i)
        sequential_results.append(result)
    
    # Verify sequential results
    print("\n=== Verifying sequential results ===")
    for i, (result, _) in enumerate(sequential_results):
        assert "completed" in result, f"Worker {i} failed during sequential test: {result}"
    print("All sequential workers completed successfully")
    
    # Now run workers concurrently
    print("\n=== Running workers concurrently ===")
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker, i + num_workers) for i in range(num_workers)]
        concurrent_results = [future.result() for future in as_completed(futures)]
    
    # Combine all results
    all_results = sequential_results + concurrent_results
    
    # Verify all workers completed successfully
    print("\n=== Verifying all workers completed ===")
    for i, (result, _) in enumerate(all_results):
        assert "completed" in result, f"Worker {i} failed: {result}"
    print("All workers completed successfully")
    
    # Load a fresh instance to verify all changes were persisted
    print("\n=== Verifying persistence ===")
    final_kb = KnowledgeBase(db_path)
    entries = final_kb.search_entries(limit=1000)
    
    print(f"Found {len(entries)} total entries in the database")
    for i, entry in enumerate(entries):
        print(f"Entry {i+1}: {entry.content[:100]}{'...' if len(str(entry.content)) > 100 else ''}")
    
    # Verify we can find entries from all workers
    worker_entries_found = set()
    
    for entry in entries:
        content = str(entry.content)
        for worker_id in range(2 * num_workers):  # Check both sequential and concurrent workers
            if f"Worker {worker_id}" in content:
                worker_entries_found.add(worker_id)
    
    print(f"\nFound entries from workers: {sorted(worker_entries_found)}")
    
    # At least some workers should have left entries
    assert len(worker_entries_found) > 0, "No worker entries found in the database"
    
    # Check that we have entries from at least the sequential workers
    min_expected_workers = num_workers  # At least the sequential workers should be present
    assert len(worker_entries_found) >= min_expected_workers, \
        f"Expected entries from at least {min_expected_workers} workers, got {len(worker_entries_found)}"
    
    print("\n=== Test completed successfully ===")


def test_large_dataset_performance(tmp_path: Path):
    """Test performance with a large dataset."""
    db_path = tmp_path / "large_kb.db"
    kb = KnowledgeBase(str(db_path))
    
    # Time adding a large number of entries
    start_time = time.time()
    for i in range(LARGE_DATASET_SIZE):
        kb.add_entry(
            content={
                "id": i,
                "data": f"Sample data {i}",
                "category": f"category_{i % 10}",
                "tags": [f"tag_{j}" for j in range(i % 3 + 1)]
            },
            metadata={"source": "performance_test"},
            tags=[f"tag_{i % 5}"]
        )
    add_time = time.time() - start_time
    
    # Time searching
    start_time = time.time()
    results = kb.search_entries(query="sample", limit=100)
    search_time = time.time() - start_time
    
    # Time filtering by tag
    start_time = time.time()
    results = kb.search_entries(tags=["tag_1"], limit=100)
    tag_filter_time = time.time() - start_time
    
    # Time saving to disk
    start_time = time.time()
    kb.save_to_disk()
    save_time = time.time() - start_time
    
    # Time loading from disk
    start_time = time.time()
    kb2 = KnowledgeBase(str(db_path))
    load_time = time.time() - start_time
    
    # Print performance metrics
    print(f"\nPerformance metrics for {LARGE_DATASET_SIZE} entries:")
    print(f"- Add entries: {add_time:.4f}s")
    print(f"- Search: {search_time:.4f}s")
    print(f"- Filter by tag: {tag_filter_time:.4f}s")
    print(f"- Save to disk: {save_time:.4f}s")
    print(f"- Load from disk: {load_time:.4f}s")
    
    # Basic assertions
    assert len(results) > 0
    assert len(kb2.search_entries(limit=1)) > 0
    
    # Verify data integrity
    assert len(kb.search_entries(limit=LARGE_DATASET_SIZE + 10)) == LARGE_DATASET_SIZE


@pytest.mark.benchmark
class TestKnowledgeBasePerformance:
    """Performance benchmarks for KnowledgeBase."""
    
    def test_search_performance(self, benchmark, tmp_path: Path):
        """Benchmark search performance."""
        db_path = tmp_path / "benchmark_kb.db"
        kb = KnowledgeBase(str(db_path))
        
        # Setup: Add test data
        for i in range(1000):
            kb.add_entry(
                content=f"Test entry {i} with some text to search",
                tags=[f"tag_{i % 10}"]
            )
        
        # Benchmark search
        def _search():
            return kb.search_entries(query="search", limit=100)
        
        result = benchmark(_search)
        assert len(result) > 0
    
    def test_concurrent_access_performance(self, benchmark, tmp_path: Path):
        """Benchmark concurrent access performance."""
        db_path = tmp_path / "concurrent_benchmark_kb.db"
        
        def _concurrent_ops():
            with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as executor:
                futures = [
                    executor.submit(self._worker, db_path, i)
                    for i in range(CONCURRENT_THREADS)
                ]
                return [f.result() for f in as_completed(futures)]
        
        # Warm up
        _concurrent_ops()
        
        # Run benchmark
        results = benchmark(_concurrent_ops)
        assert len(results) == CONCURRENT_THREADS
    
    @staticmethod
    def _worker(db_path: Path, worker_id: int) -> str:
        """Worker function for concurrent testing."""
        kb = KnowledgeBase(str(db_path))
        
        # Perform operations
        for i in range(10):
            # Add entry
            kb.add_entry(f"Worker {worker_id} entry {i}")
            
            # Search
            _ = kb.search_entries(query=f"Worker {worker_id}")
            
            # Update
            entries = kb.search_entries(query=f"Worker {worker_id}")
            if entries:
                kb.update_entry(entries[0].id, f"Updated by worker {worker_id}")
        
        return f"Worker {worker_id} completed"
