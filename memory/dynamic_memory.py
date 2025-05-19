import os
import logging
import json
import pickle
from typing import Dict, List, Any, Optional, Union, Tuple
import hashlib
from datetime import datetime
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class DynamicMemory:
    """
    Dynamic memory management system for storing and retrieving information 
    using vector embeddings for semantic search.
    """
    def __init__(
        self,
        project_id: str,
        embedding_function: callable,
        vector_dimension: int = 384,  # Dimension for snowflake-arctic-embed:335m
        storage_dir: Optional[str] = None
    ):
        """
        Initialize dynamic memory system.
        
        Args:
            project_id: Unique identifier for the project
            embedding_function: Function to convert text to embeddings
            vector_dimension: Dimension of embedding vectors
            storage_dir: Directory to store memory data (default: './memory_data')
        """
        self.project_id = project_id
        self.embedding_function = embedding_function
        self.vector_dimension = vector_dimension
        self.storage_dir = storage_dir or "./memory_data"
        
        # Ensure storage directory exists
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize memory structures
        self.documents = {}  # id -> document
        self.embeddings = {}  # id -> embedding vector
        self.metadata = {}   # id -> metadata
        
        # Memory segments by agent
        self.agent_memories = {}  # agent_name -> list of doc_ids
        
        # Create project directory
        self.project_dir = os.path.join(self.storage_dir, self.project_id)
        Path(self.project_dir).mkdir(parents=True, exist_ok=True)
        
        # Load existing memory if available
        self._load_memory()
    
    def _load_memory(self) -> None:
        """Load memory data from disk if it exists."""
        memory_file = os.path.join(self.project_dir, "memory.pkl")
        
        if os.path.exists(memory_file):
            try:
                with open(memory_file, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data.get('documents', {})
                    self.embeddings = data.get('embeddings', {})
                    self.metadata = data.get('metadata', {})
                    self.agent_memories = data.get('agent_memories', {})
                logger.info(f"Loaded memory for project {self.project_id} with {len(self.documents)} documents")
            except Exception as e:
                logger.error(f"Error loading memory: {e}")
    
    def _save_memory(self) -> None:
        """Save memory data to disk."""
        memory_file = os.path.join(self.project_dir, "memory.pkl")
        
        try:
            data = {
                'documents': self.documents,
                'embeddings': self.embeddings,
                'metadata': self.metadata,
                'agent_memories': self.agent_memories
            }
            
            with open(memory_file, 'wb') as f:
                pickle.dump(data, f)
                
            # Also save a JSON summary for inspection
            summary = {
                'document_count': len(self.documents),
                'agent_memories': {agent: len(docs) for agent, docs in self.agent_memories.items()},
                'last_updated': datetime.now().isoformat()
            }
            
            with open(os.path.join(self.project_dir, "memory_summary.json"), 'w') as f:
                json.dump(summary, f, indent=2)
                
            logger.debug(f"Saved memory for project {self.project_id}")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    
    def add_document(
        self,
        text: str,
        agent_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """
        Add a document to memory.
        
        Args:
            text: The document text
            agent_name: Name of the agent adding the document
            metadata: Optional metadata dictionary
            doc_id: Optional document ID (generated if not provided)
            
        Returns:
            Document ID
        """
        # Generate document ID if not provided
        if not doc_id:
            doc_id = hashlib.md5((text + str(datetime.now().timestamp())).encode()).hexdigest()
        
        # Create metadata if not provided
        if metadata is None:
            metadata = {}
        
        # Add timestamp to metadata
        metadata['timestamp'] = datetime.now().isoformat()
        metadata['agent'] = agent_name
        
        # Generate embedding for document
        try:
            embedding = self.embedding_function(text)
            
            # Store document, embedding, and metadata
            self.documents[doc_id] = text
            self.embeddings[doc_id] = embedding
            self.metadata[doc_id] = metadata
            
            # Add to agent memory
            if agent_name not in self.agent_memories:
                self.agent_memories[agent_name] = []
            
            self.agent_memories[agent_name].append(doc_id)
            
            # Save memory to disk
            self._save_memory()
            
            return doc_id
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            raise Exception(f"Error adding document: {e}")
    
    def query_memory(
        self,
        query: str,
        agent_name: Optional[str] = None,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Query memory for relevant documents.
        
        Args:
            query: The query text
            agent_name: Optional agent name to filter results
            top_k: Number of results to return
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of dictionaries with document text, metadata, and similarity score
        """
        # Generate embedding for query
        query_embedding = self.embedding_function(query)
        
        results = []
        
        # Filter doc_ids by agent_name if provided
        if agent_name and agent_name in self.agent_memories:
            doc_ids = self.agent_memories[agent_name]
        else:
            doc_ids = list(self.documents.keys())
        
        # Calculate similarity for each document
        similarities = []
        
        for doc_id in doc_ids:
            if doc_id in self.embeddings:
                doc_embedding = self.embeddings[doc_id]
                similarity = self._calculate_similarity(query_embedding, doc_embedding)
                similarities.append((doc_id, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by threshold and limit to top_k
        for doc_id, similarity in similarities[:top_k]:
            if similarity >= threshold:
                results.append({
                    'doc_id': doc_id,
                    'text': self.documents[doc_id],
                    'metadata': self.metadata[doc_id],
                    'similarity': similarity
                })
        
        return results
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Dictionary with document text and metadata, or None if not found
        """
        if doc_id in self.documents:
            return {
                'doc_id': doc_id,
                'text': self.documents[doc_id],
                'metadata': self.metadata[doc_id]
            }
        return None
    
    def get_agent_memory(self, agent_name: str) -> List[Dict[str, Any]]:
        """
        Get all documents for an agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            List of dictionaries with document text and metadata
        """
        results = []
        
        if agent_name in self.agent_memories:
            for doc_id in self.agent_memories[agent_name]:
                if doc_id in self.documents:
                    results.append({
                        'doc_id': doc_id,
                        'text': self.documents[doc_id],
                        'metadata': self.metadata[doc_id]
                    })
        
        return results
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from memory.
        
        Args:
            doc_id: Document ID
            
        Returns:
            True if document was deleted, False otherwise
        """
        if doc_id in self.documents:
            # Remove document from all structures
            del self.documents[doc_id]
            
            if doc_id in self.embeddings:
                del self.embeddings[doc_id]
            
            if doc_id in self.metadata:
                del self.metadata[doc_id]
            
            # Remove from agent memories
            for agent_name in self.agent_memories:
                if doc_id in self.agent_memories[agent_name]:
                    self.agent_memories[agent_name].remove(doc_id)
            
            # Save memory to disk
            self._save_memory()
            
            return True
        
        return False
    
    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (0-1)
        """
        # Convert to numpy arrays
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
        
        if norm_product == 0:
            return 0.0
        
        similarity = dot_product / norm_product
        
        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, similarity))
    
    def summarize_memory(self) -> Dict[str, Any]:
        """
        Summarize memory statistics.
        
        Returns:
            Dictionary with memory statistics
        """
        return {
            'document_count': len(self.documents),
            'agent_memories': {agent: len(docs) for agent, docs in self.agent_memories.items()},
            'memory_size_bytes': self._estimate_memory_size(),
            'last_updated': max([self.metadata[doc_id].get('timestamp', '1970-01-01') 
                                for doc_id in self.metadata], default='1970-01-01')
        }
    
    def _estimate_memory_size(self) -> int:
        """
        Estimate the memory size in bytes.
        
        Returns:
            Size in bytes
        """
        try:
            data = {
                'documents': self.documents,
                'embeddings': self.embeddings,
                'metadata': self.metadata,
                'agent_memories': self.agent_memories
            }
            
            return len(pickle.dumps(data))
        except Exception:
            return 0
    
    def clear_memory(self) -> None:
        """Clear all memory."""
        self.documents = {}
        self.embeddings = {}
        self.metadata = {}
        self.agent_memories = {}
        
        # Save empty memory to disk
        self._save_memory()
