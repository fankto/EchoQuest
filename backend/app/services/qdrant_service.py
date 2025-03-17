from typing import Any, Dict, List, Optional
import uuid

import openai
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Filter, PointStruct
import asyncio
import random

from app.core.config import settings


class QdrantService:
    """Service for working with Qdrant vector database"""
    
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        openai.api_key = settings.OPENAI_API_KEY
        self.has_valid_api_key = bool(openai.api_key) and not (isinstance(openai.api_key, str) and 
                                 (openai.api_key.startswith("your-") or not openai.api_key.strip()))
        if not self.has_valid_api_key:
            logger.warning("OpenAI API key is not properly configured. RAG functionality will be limited.")
    
    async def init_collections(self):
        """Initialize Qdrant collections"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                # Create collection for interview transcripts
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=1536,  # OpenAI embedding dimensions
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                logger.info(f"Collection {self.collection_name} created successfully")
        except Exception as e:
            logger.error(f"Error initializing Qdrant collections: {e}")
            raise
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a list of texts"""
        try:
            if not self.has_valid_api_key:
                # Generate mock embeddings if no valid API key
                logger.warning("Using mock embeddings as OpenAI API key is not configured properly")
                return [self._generate_mock_embedding() for _ in texts]
                
            # Using v0.28.1 API style instead of the newer embeddings.create()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: openai.Embedding.create(
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    input=texts,
                )
            )
            return [item['embedding'] for item in response['data']]
        except Exception as e:
            logger.error(f"Error creating embeddings: {e}")
            # Fallback to mock embeddings
            return [self._generate_mock_embedding() for _ in texts]
    
    def _generate_mock_embedding(self) -> List[float]:
        """Generate a mock embedding vector for testing without OpenAI API"""
        # Create a 1536-dimensional vector with small random values
        return [random.uniform(-0.01, 0.01) for _ in range(1536)]
    
    async def index_transcript_chunks(
        self, interview_id: str, chunks: List[Dict[str, Any]]
    ) -> None:
        """
        Index transcript chunks in Qdrant
        
        Args:
            interview_id: ID of the interview
            chunks: List of transcript chunks with text, metadata, etc.
        """
        try:
            # First, delete any existing chunks for this interview
            await self.delete_interview_chunks(interview_id)
            
            # Prepare texts for embedding
            texts = [chunk["text"] for chunk in chunks]
            
            # Create embeddings
            embeddings = await self.create_embeddings(texts)
            
            # Create point objects
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Generate a valid UUID for each point instead of string ID
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "interview_id": interview_id,
                            "text": chunk["text"],
                            "start_time": chunk.get("start_time"),
                            "end_time": chunk.get("end_time"),
                            "speaker": chunk.get("speaker"),
                            "chunk_index": i,
                        },
                    )
                )
            
            # Upload points to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            
            logger.info(f"Indexed {len(points)} chunks for interview {interview_id}")
        except Exception as e:
            logger.error(f"Error indexing transcript chunks: {e}")
            raise
    
    async def delete_interview_chunks(self, interview_id: str) -> None:
        """Delete all chunks for a specific interview"""
        try:
            filter_obj = Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="interview_id",
                        match=qdrant_models.MatchValue(value=interview_id),
                    )
                ]
            )
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qdrant_models.FilterSelector(filter=filter_obj),
            )
            logger.info(f"Deleted chunks for interview {interview_id}")
        except UnexpectedResponse:
            # Collection may not exist yet
            logger.warning(f"Could not delete chunks for interview {interview_id}, collection may not exist")
        except Exception as e:
            logger.error(f"Error deleting interview chunks: {e}")
            raise
    
    async def search_transcript(
        self, interview_id: str, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search transcript chunks by semantic similarity
        
        Args:
            interview_id: ID of the interview to search in
            query: Search query
            limit: Maximum number of results to return
            
        Returns:
            List of matching transcript chunks with scores
        """
        try:
            # Create embedding for the query
            query_embedding = await self.create_embeddings([query])
            
            # Create filter for the specific interview
            filter_obj = Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="interview_id",
                        match=qdrant_models.MatchValue(value=interview_id),
                    )
                ]
            )
            
            # Search in Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding[0],
                query_filter=filter_obj,
                limit=limit,
            )
            
            # Format results
            formatted_results = []
            for res in results:
                formatted_results.append({
                    "text": res.payload["text"],
                    "start_time": res.payload.get("start_time"),
                    "end_time": res.payload.get("end_time"),
                    "speaker": res.payload.get("speaker"),
                    "chunk_index": res.payload.get("chunk_index"),
                    "score": res.score,
                })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching transcript: {e}")
            raise