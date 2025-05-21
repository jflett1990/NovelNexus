import unittest
import os
import shutil
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from memory.dynamic_memory import DynamicMemory

class TestDynamicMemory(unittest.TestCase):
    """Test case for the DynamicMemory class."""
    
    def setUp(self):
        """Set up the test environment."""
        self.test_dir = "test_memory_data"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Create a simple embedding function for testing
        def simple_embedding_function(text):
            # Create a deterministic embedding based on text length
            vector_size = 10
            np.random.seed(hash(text) % 2**32)
            return np.random.rand(vector_size).tolist()
        
        # Name the embedding function
        simple_embedding_function.__name__ = "test_embedding_function"
        
        self.memory = DynamicMemory(
            project_id="test_project",
            embedding_function=simple_embedding_function,
            vector_dimension=10,
            storage_dir=self.test_dir
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up the test directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_add_document(self):
        """Test adding documents to memory."""
        # Add a document
        doc_id = self.memory.add_document(
            text="This is a test document",
            agent_name="test_agent",
            metadata={"test_key": "test_value"}
        )
        
        # Verify document was added
        self.assertIsNotNone(doc_id)
        self.assertIn(doc_id, self.memory.documents)
        self.assertIn(doc_id, self.memory.embeddings)
        self.assertIn(doc_id, self.memory.metadata)
        self.assertIn("test_agent", self.memory.agent_memories)
        self.assertIn(doc_id, self.memory.agent_memories["test_agent"])
        
        # Verify metadata was stored correctly
        self.assertEqual(self.memory.metadata[doc_id]["test_key"], "test_value")
        self.assertEqual(self.memory.metadata[doc_id]["agent"], "test_agent")
        self.assertIn("timestamp", self.memory.metadata[doc_id])
        self.assertIn("embedding_model", self.memory.metadata[doc_id])
        self.assertEqual(self.memory.metadata[doc_id]["embedding_dimensions"], 10)
    
    def test_query_memory(self):
        """Test querying memory."""
        # Add documents
        self.memory.add_document("Apple is a fruit", "test_agent")
        self.memory.add_document("Banana is yellow", "test_agent")
        self.memory.add_document("Cat is an animal", "test_agent")
        
        # Query for documents
        results = self.memory.query_memory("fruit", "test_agent")
        
        # Verify results
        self.assertGreater(len(results), 0)
        self.assertIn("text", results[0])
        self.assertIn("metadata", results[0])
    
    def test_get_document(self):
        """Test retrieving a document by ID."""
        # Add a document
        doc_id = self.memory.add_document("Test document", "test_agent")
        
        # Retrieve the document
        doc = self.memory.get_document(doc_id)
        
        # Verify document
        self.assertEqual(doc["text"], "Test document")
        self.assertIn("metadata", doc)
        self.assertEqual(doc["metadata"]["agent"], "test_agent")
    
    def test_get_agent_memory(self):
        """Test retrieving all documents for an agent."""
        # Add documents
        self.memory.add_document("Document 1", "agent1")
        self.memory.add_document("Document 2", "agent1")
        self.memory.add_document("Document 3", "agent2")
        
        # Get agent memory
        agent1_docs = self.memory.get_agent_memory("agent1")
        agent2_docs = self.memory.get_agent_memory("agent2")
        
        # Verify results
        self.assertEqual(len(agent1_docs), 2)
        self.assertEqual(len(agent2_docs), 1)
        
        # Verify nonexistent agent
        self.assertEqual(len(self.memory.get_agent_memory("nonexistent")), 0)
    
    def test_delete_document(self):
        """Test deleting a document."""
        # Add a document
        doc_id = self.memory.add_document("Document to delete", "test_agent")
        
        # Verify it exists
        self.assertIn(doc_id, self.memory.documents)
        
        # Delete the document
        result = self.memory.delete_document(doc_id)
        
        # Verify deletion
        self.assertTrue(result)
        self.assertNotIn(doc_id, self.memory.documents)
        self.assertNotIn(doc_id, self.memory.embeddings)
        self.assertNotIn(doc_id, self.memory.metadata)
        self.assertNotIn(doc_id, self.memory.agent_memories["test_agent"])
        
        # Try deleting nonexistent document
        result = self.memory.delete_document("nonexistent")
        self.assertFalse(result)
    
    def test_memory_persistence(self):
        """Test that memory persists between instances."""
        # Add a document
        doc_id = self.memory.add_document("Persistent document", "test_agent")
        
        # Create a new memory instance
        def simple_embedding_function(text):
            vector_size = 10
            np.random.seed(hash(text) % 2**32)
            return np.random.rand(vector_size).tolist()
        
        # Create a new memory instance pointing to the same storage
        new_memory = DynamicMemory(
            project_id="test_project",
            embedding_function=simple_embedding_function,
            vector_dimension=10,
            storage_dir=self.test_dir
        )
        
        # Verify document was loaded
        self.assertIn(doc_id, new_memory.documents)
        self.assertEqual(new_memory.documents[doc_id], "Persistent document")
    
    def test_concurrency(self):
        """Test thread safety with concurrent operations."""
        num_threads = 5
        docs_per_thread = 10
        
        def add_documents(thread_id):
            for i in range(docs_per_thread):
                doc_text = f"Document from thread {thread_id}, doc {i}"
                self.memory.add_document(doc_text, f"agent{thread_id}")
        
        # Run concurrent document additions
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=add_documents, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all documents were added correctly
        total_expected_docs = num_threads * docs_per_thread
        doc_count = len(self.memory.documents)
        self.assertEqual(doc_count, total_expected_docs, 
                        f"Expected {total_expected_docs} documents, got {doc_count}")
        
        # Verify agent memories
        for i in range(num_threads):
            agent_docs = self.memory.get_agent_memory(f"agent{i}")
            self.assertEqual(len(agent_docs), docs_per_thread, 
                           f"Agent {i} should have {docs_per_thread} documents")
    
    def test_mixed_concurrency(self):
        """Test mixed read/write operations concurrently."""
        # Add some initial documents
        for i in range(10):
            self.memory.add_document(f"Initial document {i}", "test_agent")
        
        def read_operation():
            # Read operations
            for _ in range(10):
                self.memory.query_memory("document", "test_agent")
                time.sleep(0.01)  # Small delay
        
        def write_operation():
            # Write operations
            for i in range(5):
                self.memory.add_document(f"New document {i}", "test_agent")
                time.sleep(0.01)  # Small delay
        
        # Run read and write operations concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(5):
                futures.append(executor.submit(read_operation))
            for _ in range(5):
                futures.append(executor.submit(write_operation))
        
        # Verify all documents were added
        self.assertEqual(len(self.memory.get_agent_memory("test_agent")), 35)  # 10 initial + 5*5 new

if __name__ == "__main__":
    unittest.main() 