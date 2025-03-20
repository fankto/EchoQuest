import asyncio
from typing import Dict, List, Any, Optional, Union
import time

import httpx
import openai
from openai import AsyncOpenAI
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.exceptions import ExternalServiceError


class OpenAIService:
    """
    Service wrapper for OpenAI API integration

    Provides a consistent interface for all OpenAI API calls with proper
    error handling, retries, and response formatting.
    """

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.is_configured = bool(self.api_key) and not self.api_key.startswith("your-")
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        self.chat_model = settings.OPENAI_CHAT_MODEL
        self.async_client = AsyncOpenAI(api_key=self.api_key)

        logger.info(f"OpenAI service initialized with API key configured: {self.is_configured}")

    def _check_configuration(self) -> None:
        """
        Check if the API key is configured

        Raises:
            ExternalServiceError: If API key is not properly configured
        """
        if not self.is_configured:
            raise ExternalServiceError("OpenAI", "API key is not properly configured")

    @retry(
        stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.OPENAI_RETRY_DELAY, min=1, max=60),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a list of texts

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ExternalServiceError: If there's an error with the OpenAI API
        """
        self._check_configuration()

        try:
            # Split into batches to avoid hitting token limits
            batch_size = 100
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                logger.debug(
                    f"Creating embeddings for batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1}")

                response = await self.async_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )

                # Extract embeddings from response
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # Respect rate limits
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.5)

            return all_embeddings

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            error_msg = f"HTTP error creating embeddings: {str(e)}"
            logger.error(error_msg)
            raise ExternalServiceError("OpenAI", error_msg)
        except Exception as e:
            error_msg = f"Error creating embeddings: {str(e)}"
            logger.error(error_msg)
            raise ExternalServiceError("OpenAI", error_msg)

    @retry(
        stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.OPENAI_RETRY_DELAY, min=1, max=60),
        retry=if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def create_chat_completion(
            self,
            messages: List[Dict[str, str]],
            max_tokens: Optional[int] = None,
            temperature: float = 0.7,
            stream: bool = False,
            model: Optional[str] = None
    ) -> Union[str, AsyncIterator[str]]:
        """
        Create a chat completion

        Args:
            messages: List of messages in the conversation
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            stream: Whether to stream the response
            model: Optional model override

        Returns:
            If stream=False: Generated text
            If stream=True: Async iterator yielding generated text chunks

        Raises:
            ExternalServiceError: If there's an error with the OpenAI API
        """
        self._check_configuration()

        # Use the specified model or default
        model_name = model or self.chat_model

        try:
            if stream:
                return self._stream_chat_completion(
                    messages, max_tokens, temperature, model_name
                )
            else:
                response = await self.async_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            error_msg = f"HTTP error in chat completion: {str(e)}"
            logger.error(error_msg)
            raise ExternalServiceError("OpenAI", error_msg)
        except Exception as e:
            error_msg = f"Error in chat completion: {str(e)}"
            logger.error(error_msg)
            raise ExternalServiceError("OpenAI", error_msg)

    async def _stream_chat_completion(
            self,
            messages: List[Dict[str, str]],
            max_tokens: Optional[int],
            temperature: float,
            model: str
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion

        Args:
            messages: List of messages in the conversation
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            model: Model to use

        Yields:
            Generated text chunks

        Raises:
            ExternalServiceError: If there's an error with the OpenAI API
        """
        try:
            stream = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            async for chunk in stream:
                if hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            error_msg = f"HTTP error in streaming chat completion: {str(e)}"
            logger.error(error_msg)
            raise ExternalServiceError("OpenAI", error_msg)
        except Exception as e:
            error_msg = f"Error in streaming chat completion: {str(e)}"
            logger.error(error_msg)
            raise ExternalServiceError("OpenAI", error_msg)


# Create singleton instance
openai_service = OpenAIService()