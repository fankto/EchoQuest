from typing import Any, Dict, List, Optional
import uuid
import asyncio
import random

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Filter, PointStruct
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.utils.exceptions import ExternalAPIError
from app.utils.redis import get_redis_client


class QdrantService:
    """Service for working with Qdrant vector database"""

    def __init__(self):
        # Initialize Qdrant client
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION_NAME

        # Initialize OpenAI settings
        self.openai_api_key = settings.OPENAI_API_KEY
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        self.embedding_dimension = 1536  # Dimension for text-embedding-3-small

        # Check API key validity
        self.has_valid_api_key = self._check_api_key()
        if not self.has_valid_api_key:
            logger.warning("OpenAI API key is not properly configured. RAG functionality will be limited.")

    def _check_api_key(self) -> bool:
        """Check if the OpenAI API key is valid"""
        return bool(self.openai_api_key) and not (
                isinstance(self.openai_api_key, str) and
                (self.openai_api_key.startswith("your-") or not self.openai_api_key.strip())
        )

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
                        size=self.embedding_dimension,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                logger.info(f"Collection {self.collection_name} created successfully")
        except Exception as e:
            logger.error(f"Error initializing Qdrant collections: {e}")
            raise

    @retry(
        stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.OPENAI_RETRY_DELAY, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a list of texts

        Args:
            texts: List of text strings to create embeddings for

        Returns:
            List of embedding vectors
        """
        try:
            # Check if we should use cache
            redis = await get_redis_client()
            cached_embeddings = []
            texts_to_embed = []
            text_indices = []

            # Try to get cached embeddings first
            if redis:
                for i, text in enumerate(texts):
                    # Create cache key based on hash of text
                    cache_key = f"embedding:{hash(text)}"
                    cached = await redis.get(cache_key)

                    if cached:
                        # Convert from string to list of floats
                        embedding = [float(x) for x in cached.decode('utf-8').split(',')]
                        cached_embeddings.append((i, embedding))
                    else:
                        # Mark for embedding
                        texts_to_embed.append(text)
                        text_indices.append(i)
            else:
                # No cache available, embed all texts
                texts_to_embed = texts
                text_indices = list(range(len(texts)))

            # If all embeddings were cached, return them
            if not texts_to_embed:
                # Sort by original index
                sorted_embeddings = sorted(cached_embeddings, key=lambda x: x[0])
                return [emb for _, emb in sorted_embeddings]

            # Handle missing API key
            if not self.has_valid_api_key:
                # Generate mock embeddings for texts that need embedding
                new_embeddings = [(i, self._generate_mock_embedding()) for i in text_indices]

                # Combine cached and new embeddings
                all_embeddings = cached_embeddings + new_embeddings

                # Sort by original index
                sorted_embeddings = sorted(all_embeddings, key=lambda x: x[0])

                return [emb for _, emb in sorted_embeddings]

            # Create embeddings for texts that weren't cached
            client = AsyncOpenAI(api_key=self.openai_api_key)
            response = await client.embeddings.create(
                model=self.embedding_model,
                input=texts_to_embed
            )

            new_embeddings = [(text_indices[i], item.embedding) for i, item in enumerate(response.data)]

            # Cache new embeddings
            if redis:
                for i, text in enumerate(texts_to_embed):
                    embedding = response.data[i].embedding
                    cache_key = f"embedding:{hash(text)}"
                    # Store as comma-separated string to save space
                    embedding_str = ','.join([str(x) for x in embedding])
                    await redis.set(cache_key, embedding_str, ex=86400 * 7)  # Cache for 7 days

            # Combine cached and new embeddings
            all_embeddings = cached_embeddings + new_embeddings

            # Sort by original index
            sorted_embeddings = sorted(all_embeddings, key=lambda x: x[0])

            return [emb for _, emb in sorted_embeddings]

        except httpx.HTTPError as e:
            logger.error(f"HTTP error creating embeddings: {e}")
            raise ExternalAPIError(f"Error communicating with OpenAI: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating embeddings: {e}")
            # Fallback to mock embeddings
            return [self._generate_mock_embedding() for _ in texts]

    def _generate_mock_embedding(self) -> List[float]:
        """
        Generate a mock embedding vector for testing without OpenAI API

        Returns:
            Mock embedding vector
        """
        # Create a vector with the correct dimension and small random values
        return [random.uniform(-0.01, 0.01) for _ in range(self.embedding_dimension)]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
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

            # If no chunks provided, just exit
            if not chunks:
                logger.warning(f"No chunks provided for indexing interview {interview_id}")
                return

            # Prepare texts for embedding
            texts = [chunk["text"] for chunk in chunks]

            # Create embeddings
            embeddings = await self.create_embeddings(texts)

            # Create point objects for batch insertion
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Generate a valid UUID for each point
                point_id = str(uuid.uuid4())

                # Prepare payload with metadata
                payload = {
                    "interview_id": interview_id,
                    "text": chunk["text"],
                    "chunk_index": i,
                }

                # Add optional fields if they exist
                for field in ["start_time", "end_time", "speaker"]:
                    if field in chunk and chunk[field] is not None:
                        payload[field] = chunk[field]

                # Create point struct
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload,
                    )
                )

            # Upload points to Qdrant in batches of 100
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )

            logger.info(f"Indexed {len(points)} chunks for interview {interview_id}")
        except Exception as e:
            logger.error(f"Error indexing transcript chunks: {e}")
            raise

    async def delete_interview_chunks(self, interview_id: str) -> None:
        """
        Delete all chunks for a specific interview

        Args:
            interview_id: ID of the interview to delete chunks for
        """
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
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
            # Check for cached results
            redis = await get_redis_client()
            if redis:
                cache_key = f"search:{interview_id}:{hash(query)}:{limit}"
                cached_results = await redis.get(cache_key)
                if cached_results:
                    import json
                    return json.loads(cached_results)

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
                result_item = {
                    "text": res.payload["text"],
                    "score": res.score,
                    "chunk_index": res.payload.get("chunk_index"),
                }

                # Add optional fields if they exist in the payload
                for field in ["start_time", "end_time", "speaker"]:
                    if field in res.payload:
                        result_item[field] = res.payload[field]

                formatted_results.append(result_item)

            # Cache results
            if redis:
                import json
                await redis.set(
                    cache_key,
                    json.dumps(formatted_results),
                    ex=3600  # Cache for 1 hour
                )

            return formatted_results
        except Exception as e:
            logger.error(f"Error searching transcript: {e}")
            raise


# Create singleton instance
qdrant_service = QdrantService()