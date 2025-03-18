from typing import Dict, List
import json
import asyncio
import uuid

import openai
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InsufficientCreditsError
from app.crud.crud_interview import interview_crud
from app.crud.crud_transaction import transaction_crud
from app.models.models import ChatMessage, Interview, TransactionType, User
from app.schemas.chat import ChatMessageCreate
from app.services.qdrant_service import QdrantService
from app.services.token_service import token_service


class ChatService:
    """Service for handling chat interactions with interview transcripts"""
    
    def __init__(self):
        self.qdrant_service = QdrantService()
        # Initialize OpenAI API key
        openai.api_key = settings.OPENAI_API_KEY
        if not openai.api_key or isinstance(openai.api_key, str) and (openai.api_key.startswith("your-") or not openai.api_key.strip()):
            logger.warning("OpenAI API key is not properly configured. Chat functionality will be limited.")
    
    async def create_chat_message(
        self,
        db: AsyncSession,
        interview: Interview,
        user: User,
        message_text: str,
        chat_session_id: uuid.UUID = None,
    ) -> ChatMessage:
        """
        Create a new chat message from user and store in the database
        
        Args:
            db: Database session
            interview: Interview object
            user: User sending the message
            message_text: Message content
            chat_session_id: Optional chat session ID
            
        Returns:
            Created ChatMessage object
        """
        # Count tokens in the message
        tokens = token_service.count_tokens(message_text)
        
        # Check if user has enough tokens
        if interview.remaining_chat_tokens < tokens:
            raise InsufficientCreditsError("Not enough chat tokens remaining")
        
        # Create message
        message_data = ChatMessageCreate(
            interview_id=interview.id,
            user_id=user.id,
            role="user",
            content=message_text,
            tokens_used=tokens,
            chat_session_id=chat_session_id,
        )
        
        message = ChatMessage(
            interview_id=message_data.interview_id,
            user_id=message_data.user_id,
            role=message_data.role,
            content=message_data.content,
            tokens_used=message_data.tokens_used,
            chat_session_id=message_data.chat_session_id,
        )
        
        # Update interview token count
        interview.remaining_chat_tokens -= tokens
        
        # Add to database
        db.add(message)
        await db.flush()
        
        # Create transaction record
        await transaction_crud.create_transaction(
            db=db,
            user_id=user.id,
            organization_id=interview.organization_id,
            interview_id=interview.id,
            transaction_type=TransactionType.CHAT_TOKEN_USAGE,
            amount=tokens,
        )
        
        return message
    
    async def generate_assistant_response(
        self,
        db: AsyncSession,
        interview: Interview,
        user: User,
        context_messages: List[ChatMessage],
        chat_session_id: uuid.UUID = None,
    ) -> ChatMessage:
        """
        Generate assistant response using OpenAI API
        
        Args:
            db: Database session
            interview: Interview object
            user: User
            context_messages: Previous messages for context
            chat_session_id: Optional chat session ID
            
        Returns:
            Assistant response ChatMessage object
        """
        try:
            # Check if OpenAI API key is configured
            if not openai.api_key or isinstance(openai.api_key, str) and (openai.api_key.startswith("your-") or not openai.api_key.strip()):
                # Create a mock response if OpenAI is not configured
                content = "I'm sorry, but the OpenAI API is not properly configured. Please set up a valid OpenAI API key to use the chat functionality."
                message = ChatMessage(
                    interview_id=interview.id,
                    user_id=user.id,
                    role="assistant",
                    content=content,
                    tokens_used=0,  # No tokens used for mock response
                    chat_session_id=chat_session_id,
                )
                db.add(message)
                await db.flush()
                return message
            
            # Get transcript chunks based on recent messages
            transcript_context = await self._get_transcript_context(interview, context_messages)
            
            # Format conversation for OpenAI
            messages = await self._prepare_messages(context_messages, transcript_context)
            
            # Estimate token usage for messages
            input_tokens = token_service.count_message_tokens(messages)
            
            # Estimate max tokens for response (leaving some buffer)
            max_tokens = min(4000, interview.remaining_chat_tokens - input_tokens)
            
            if max_tokens < 100:
                raise InsufficientCreditsError("Not enough chat tokens remaining for response")
            
            # Initialize OpenAI client
            client = openai.OpenAI(api_key=openai.api_key)
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model=settings.OPENAI_CHAT_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            
            # Get response content
            content = response.choices[0].message.content
            
            # Count output tokens
            output_tokens = token_service.count_tokens(content)
            total_tokens = input_tokens + output_tokens
            
            # Create assistant message
            message = ChatMessage(
                interview_id=interview.id,
                user_id=user.id,  # Using the same user ID for tracking purposes
                role="assistant",
                content=content,
                tokens_used=total_tokens,
                chat_session_id=chat_session_id,
            )
            
            # Update interview token count
            interview.remaining_chat_tokens -= total_tokens
            
            # Add to database
            db.add(message)
            await db.flush()
            
            # Create transaction record
            await transaction_crud.create_transaction(
                db=db,
                user_id=user.id,
                organization_id=interview.organization_id,
                interview_id=interview.id,
                transaction_type=TransactionType.CHAT_TOKEN_USAGE,
                amount=total_tokens,
            )
            
            return message
        except Exception as e:
            logger.error(f"Error generating assistant response: {e}")
            raise
    
    async def _get_transcript_context(
        self, interview: Interview, recent_messages: List[ChatMessage]
    ) -> str:
        """
        Retrieve relevant transcript chunks based on recent messages
        
        Args:
            interview: Interview object
            recent_messages: Recent chat messages
            
        Returns:
            Formatted transcript context
        """
        # Extract the last user message
        last_user_message = next(
            (msg for msg in reversed(recent_messages) if msg.role == "user"), None
        )
        
        if not last_user_message:
            return "No transcript available."
        
        # For short transcripts, return the full transcript
        if interview.transcription and len(interview.transcription) < 6000:
            return interview.transcription
        
        # For longer transcripts, use RAG to find relevant chunks
        transcript_chunks = await self.qdrant_service.search_transcript(
            interview_id=str(interview.id),
            query=last_user_message.content,
            limit=5,
        )
        
        # Format the transcript chunks
        context = "Relevant parts of the interview transcript:\n\n"
        
        for i, chunk in enumerate(transcript_chunks):
            speaker = chunk.get("speaker", "Speaker")
            text = chunk.get("text", "")
            start_time = chunk.get("start_time")
            end_time = chunk.get("end_time")
            
            time_info = ""
            if start_time and end_time:
                time_info = f"[{self._format_time(start_time)} - {self._format_time(end_time)}]"
            
            context += f"{speaker} {time_info}: {text}\n\n"
        
        return context
    
    async def _prepare_messages(
        self, context_messages: List[ChatMessage], transcript_context: str
    ) -> List[Dict]:
        """
        Prepare messages for OpenAI API
        
        Args:
            context_messages: Previous chat messages
            transcript_context: Transcript content
            
        Returns:
            List of formatted messages for OpenAI
        """
        # System message with instructions
        system_message = {
            "role": "system",
            "content": f"""You are an AI assistant helping analyze an interview transcript. 
Answer questions based only on the provided transcript excerpts.
If the information isn't in the transcript, say so clearly.
When referring to specific parts of the transcript, mention the speaker and timestamp.
Be concise but thorough in your answers.

TRANSCRIPT CONTEXT:
{transcript_context}"""
        }
        
        # Format chat history
        chat_messages = []
        for msg in context_messages:
            chat_messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        # Combine all messages
        return [system_message] + chat_messages
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    async def stream_assistant_response(
        self,
        db: AsyncSession,
        interview: Interview,
        user: User,
        context_messages: List[ChatMessage],
        chat_session_id: uuid.UUID = None,
    ):
        """
        Generate streaming assistant response using OpenAI API
        
        Args:
            db: Database session
            interview: Interview object
            user: User
            context_messages: Previous messages for context
            chat_session_id: Optional chat session ID
            
        Yields:
            Streaming response chunks
        """
        try:
            # Check if OpenAI API key is configured
            if not openai.api_key or isinstance(openai.api_key, str) and (openai.api_key.startswith("your-") or not openai.api_key.strip()):
                # Create a mock response if OpenAI is not configured
                content = "I'm sorry, but the OpenAI API is not properly configured. Please set up a valid OpenAI API key to use the chat functionality."
                
                # Send initial data with user message
                user_message = next((msg for msg in reversed(context_messages) if msg.role == "user"), None)
                if user_message:
                    yield f"data: {json.dumps({'type': 'user_message', 'content': user_message.content})}\n\n"
                
                # Stream mock response one character at a time
                for char in content:
                    yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"
                    await asyncio.sleep(0.01)
                
                # Create and save the message
                message = ChatMessage(
                    interview_id=interview.id,
                    user_id=user.id,
                    role="assistant",
                    content=content,
                    tokens_used=0,  # No tokens used for mock response
                    chat_session_id=chat_session_id,
                )
                db.add(message)
                await db.flush()
                await db.commit()
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'done', 'remaining_tokens': interview.remaining_chat_tokens, 'chat_session_id': str(chat_session_id) if chat_session_id else None})}\n\n"
                return
            
            # Get transcript chunks based on recent messages
            transcript_context = await self._get_transcript_context(interview, context_messages)
            
            # Format conversation for OpenAI
            messages = await self._prepare_messages(context_messages, transcript_context)
            
            # Estimate token usage for messages
            input_tokens = token_service.count_message_tokens(messages)
            
            # Estimate max tokens for response (leaving some buffer)
            max_tokens = min(4000, interview.remaining_chat_tokens - input_tokens)
            
            if max_tokens < 100:
                raise InsufficientCreditsError("Not enough chat tokens remaining for response")
            
            # Send initial data with user message
            user_message = next((msg for msg in reversed(context_messages) if msg.role == "user"), None)
            if user_message:
                yield f"data: {json.dumps({'type': 'user_message', 'content': user_message.content})}\n\n"
            
            # Initialize client with API key
            client = openai.OpenAI(api_key=openai.api_key)
            
            # Stream response from OpenAI
            full_content = ""
            
            # Call OpenAI API with stream=True
            stream = client.chat.completions.create(
                model=settings.OPENAI_CHAT_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=True,
            )
            
            for chunk in stream:
                # Check if the chunk has content
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
                    content_chunk = chunk.choices[0].delta.content
                    full_content += content_chunk
                    
                    # Send each token to the client
                    yield f"data: {json.dumps({'type': 'token', 'content': content_chunk})}\n\n"
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0)
            
            # Count output tokens
            output_tokens = token_service.count_tokens(full_content)
            total_tokens = input_tokens + output_tokens
            
            # Create assistant message
            message = ChatMessage(
                interview_id=interview.id,
                user_id=user.id,
                role="assistant",
                content=full_content,
                tokens_used=total_tokens,
                chat_session_id=chat_session_id,
            )
            
            # Update interview token count
            interview.remaining_chat_tokens -= total_tokens
            
            # Add to database
            db.add(message)
            await db.flush()
            
            # Create transaction record
            await transaction_crud.create_transaction(
                db=db,
                user_id=user.id,
                organization_id=interview.organization_id,
                interview_id=interview.id,
                transaction_type=TransactionType.CHAT_TOKEN_USAGE,
                amount=total_tokens,
            )
            
            await db.commit()
            
            # Send completion signal with remaining tokens
            yield f"data: {json.dumps({'type': 'done', 'remaining_tokens': interview.remaining_chat_tokens, 'chat_session_id': str(chat_session_id) if chat_session_id else None})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming assistant response: {e}")
            # Send error message
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            await db.rollback()
            raise


# Create singleton instance
chat_service = ChatService()