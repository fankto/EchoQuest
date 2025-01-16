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
    max_new_tokens: int = 8192
    do_sample: bool = True
    temperature: float = 0.5
    num_return_sequences: int = 1
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
    def _cached_answer_question(self, question: str, context: str) -> str:
        """Generate an answer using cache for efficiency"""
        messages = self._prepare_messages(question, context)

        try:
            pipeline = model_manager.get_pipeline('llm')
            response = self._get_model_response(messages, pipeline)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Error in answering question: {str(e)}")
            raise RuntimeError(f"Error in answering question: {str(e)}")

    def _get_model_response(self, messages: List[Dict[str, str]], pipeline: any) -> str:
        """Get response from the model"""
        prompt = self._format_messages(messages)
        outputs = pipeline(
            prompt,
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.do_sample,
            temperature=settings.temperature,
            num_return_sequences=settings.num_return_sequences,
        )
        return outputs[0]['generated_text']

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a prompt string"""
        formatted_messages = []
        for message in messages:
            formatted_messages.append(f"{message['role'].capitalize()}: {message['content']}")
        return "\n\n".join(formatted_messages) + "\n\nAssistant:"

    def _parse_response(self, response: str) -> str:
        """Extract the assistant's response from the full output"""
        assistant_response = response.split("Assistant:")[-1].strip()
        return assistant_response

    def answer_question(self, question: str, context: str) -> str:
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
            return self._cached_answer_question(question, context)


# Create a singleton instance
question_answerer = QuestionAnswerer()