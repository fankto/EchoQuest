# src/question_answerer/question_answerer.py
import gc
import logging
import threading
import time
from functools import lru_cache
from typing import List, Dict

from ..model_manager.manager import model_manager
from .prompt_templates import question_answering_messages

logger = logging.getLogger(__name__)

class Settings:
    rate_limit_questions_per_minute: int = 10

settings = Settings()

class QuestionAnswerer:
    def __init__(self):
        self.last_request_time = 0
        self._lock = threading.Lock()

    def _prepare_messages(self, question: str, context: str) -> List[Dict[str, str]]:
        """Prepare messages for the model"""
        prepared_messages = []
        for message in question_answering_messages:
            if message['role'] == 'user':
                content = message['content'].format(context=context, question=question)
            else:
                content = message['content']
            prepared_messages.append({"role": message['role'], "content": content})
        return prepared_messages

    @lru_cache(maxsize=100)
    async def _cached_answer_question(self, question: str, context: str) -> str:
        """Generate an answer using cache for efficiency"""
        messages = self._prepare_messages(question, context)

        try:
            pipeline = model_manager.get_pipeline('llm_answer')
            response = await self._get_model_response(messages, pipeline)
            return response
        except Exception as e:
            logger.error(f"Error in answering question: {str(e)}")
            raise RuntimeError(f"Error in answering question: {str(e)}")

    async def _get_model_response(self, messages: List[Dict[str, str]], pipeline: any) -> str:
        """Get response from Ollama model"""
        prompt = self._format_messages(messages)
        system = messages[0]['content'] if messages[0]['role'] == 'system' else None

        response = await pipeline.generate(
            prompt=prompt,
            model=pipeline.settings.answer_model,
            system=system
        )

        return response.strip()

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for Ollama"""
        formatted = []
        for msg in messages:
            if msg['role'] != 'system':  # System message is handled separately
                formatted.append(f"{msg['role'].capitalize()}: {msg['content']}")
        return "\n\n".join(formatted)

    async def answer_question(self, question: str, context: str) -> str:
        """Main method to get an answer for a question"""
        with self._lock:
            # Apply rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < 60 / settings.rate_limit_questions_per_minute:
                sleep_time = 60 / settings.rate_limit_questions_per_minute - time_since_last_request
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

            self.last_request_time = time.time()
            try:
                return await self._cached_answer_question(question, context)
            finally:
                # Signal the model manager to unload if needed
                # This doesn't actually unload immediately but marks it for potential unloading
                model_manager.get_pipeline('llm_answer')

    def unload_model(self):
        """Clean up resources"""
        try:
            model_manager.unload_model('llm_answer')
        except Exception as e:
            logger.error(f"Error unloading model: {str(e)}")


# Create a singleton instance
question_answerer = QuestionAnswerer()