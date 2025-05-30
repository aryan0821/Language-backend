# memory/vector_store.py

"""
memory/vector_store.py

Chroma DB–based vector store with async support and metadata filtering.
"""
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings
from chromadb import HttpClient

class VectorStore:
    """
    Chroma DB vector store with async support, matching Chroma docs and seeding script.
    """
    def __init__(self):
        self.host = os.getenv("CHROMA_HOST", "localhost")
        # Ensure port is int
        self.port = int(os.getenv("CHROMA_PORT", "8000"))
        self.collection_name = os.getenv("CHROMA_COLLECTION", "architect-docs")
        self._client: Optional[HttpClient] = None
        self._collection = None

    async def initialize(self):
        """Initialize client and collection using get_or_create_collection."""
        tries = 0
        max_tries = 5
        retry_delay = 3  # seconds
        
        while tries < max_tries:
            try:
                logging.info(f"Attempting to connect to ChromaDB at {self.host}:{self.port} (attempt {tries+1}/{max_tries})")
                self._client = HttpClient(
                    host=self.host,
                    port=self.port,
                    settings=Settings(
                        chroma_client_auth_provider="token",
                        chroma_client_auth_credentials=os.getenv("CHROMA_TOKEN", "")
                    )
                )
                # Use get_or_create_collection to avoid duplicate collections
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logging.info(f"Successfully connected to Chroma server at {self.host}:{self.port}")
                break
            except Exception as e:
                tries += 1
                if tries < max_tries:
                    logging.warning(f"ChromaDB connection attempt {tries}/{max_tries} failed: {e}")
                    await asyncio.sleep(retry_delay)
                else:
                    logging.error(f"All {max_tries} attempts to connect to ChromaDB failed: {e}")
                    # Initialize with empty collection to prevent app crash
                    self._collection = None
                    # Don't raise exception, let the app continue with limited functionality
                    logging.warning("Application will start without ChromaDB functionality")

    async def add_doc_chunk(self,
                            chunk_id: str,
                            document: str,
                            component: str,
                            doc_type: str,
                            metadata: Dict[str, Any] = None):
        """
        Add a single markdown/doc chunk for a given component.
        """
        try:
            meta = {
                "type": "doc",
                "component": component,
                "doc_type": doc_type,
                **(metadata or {})
            }
            self._collection.add(
                ids=[chunk_id],
                documents=[document],
                metadatas=[meta]
            )
        except Exception as e:
            logging.error(f"Doc chunk add failed: {e}")
            raise

    async def query_docs(self, query: str, n_results: int = 5, content_type: Optional[str] = None):
        """
        Query the vector store for documentation chunks similar to the query string.
        
        Args:
            query: The search query text
            n_results: Maximum number of results to return
            content_type: Optional filter for "documentation" or "template" content types
        """
        try:
            # Build where clause if content_type is specified
            where_filter = None
            if content_type:
                where_filter = {"content_type": content_type}
            
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            return self._format_results(results)
        except Exception as e:
            logging.error(f"Doc chunk query failed: {e}")
            return []
            
    async def query_templates(self, component_name: Optional[str] = None, n_results: int = 5):
        """
        Query specifically for component templates.
        
        Args:
            component_name: Optional specific component to retrieve templates for
            n_results: Maximum number of results to return
        """
        try:
            # Build where clause
            where_filter = {"content_type": "template"}
            if component_name:
                where_filter["component"] = component_name
                
            results = self._collection.query(
                query_texts=["component template"],
                n_results=n_results,
                where=where_filter
            )
            return self._format_results(results)
        except Exception as e:
            logging.error(f"Template query failed: {e}")
            return []

    def _format_results(self, results):
        # Chroma returns lists of lists for each field
        return [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            }
            for i in range(len(results["ids"][0]))
        ]
    
    

# Singleton instance
vector_store = VectorStore()
