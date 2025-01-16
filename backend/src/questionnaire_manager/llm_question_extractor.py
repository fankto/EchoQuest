# src/questionnaire_manager/llm_question_extractor.py
import copy
import json
import logging
import re
from threading import Lock
from typing import Dict, List

from .prompt_templates import extraction_messages
from ..model_manager.manager import model_manager

logger = logging.getLogger(__name__)


class LLMQuestionExtractor:
    _instance = None
    _lock = Lock()

    def __new__(cls, force_new=False):
        if force_new or cls._instance is None:
            with cls._lock:
                instance = super(LLMQuestionExtractor, cls).__new__(cls)
                if not force_new:
                    cls._instance = instance
        return cls._instance if not force_new else instance

    def _clean_json(self, json_string: str) -> dict:
        """Extract questions directly from the response using regex"""
        try:
            # Find all "item": "..." patterns
            import re
            pattern = r'"item":\s*"([^"]+)"'
            matches = re.finditer(pattern, json_string)

            # Extract the questions
            questions = [match.group(1) for match in matches]

            # Filter out section headers (items that are only 2-3 words and Title Case)
            questions = [q for q in questions if not (
                    len(q.split()) <= 3 and q.title() == q
            )]

            return {"items": questions}

        except Exception as e:
            logger.error(f"Error extracting questions: {str(e)}")
            return {"items": []}

    async def _get_model_response(self, messages: List[Dict[str, str]]) -> str:
        """Get response from Ollama model"""
        try:
            pipeline = model_manager.get_pipeline('llm_extract')
            prompt = self._format_messages(messages)
            system = messages[0]['content'] if messages[0]['role'] == 'system' else None

            response = await pipeline.generate(
                prompt=prompt,
                model=pipeline.settings.extract_model,
                system=system
            )

            logger.info(f"Model response: {response}")
            return response.strip()
        except Exception as e:
            logger.error(f"Error in getting model response: {str(e)}")
            raise

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for Ollama"""
        formatted = []
        for msg in messages:
            if msg['role'] != 'system':  # System message is handled separately
                formatted.append(f"{msg['role'].capitalize()}: {msg['content']}")
        return "\n\n".join(formatted)

    async def extract_questions(self, content: str) -> Dict[str, List[str]]:
        """Extract questions from content using the LLM"""
        try:
            logger.info(f"Extracting questions from content: {content[:100]}...")
            messages = copy.deepcopy(extraction_messages)
            messages[1]["content"] = messages[1]["content"].format(content=content)

            response = await self._get_model_response(messages)
            extracted_json = self._clean_json(response)

            logger.info(f"Extracted questions: {extracted_json}")
            return extracted_json
        except Exception as e:
            logger.error(f"Error in extracting questions: {str(e)}")
            raise
        finally:
            # Ensure cleanup happens even if there's an error
            try:
                model_manager.unload_model('llm_extract')
            except Exception as e:
                logger.error(f"Error unloading model: {str(e)}")


async def question_extraction(content: str) -> Dict[str, list]:
    """Main function to extract questions"""
    try:
        extractor = LLMQuestionExtractor()
        return await extractor.extract_questions(content)
    finally:
        try:
            # Use synchronous unload
            model_manager.unload_model('llm_extract')
        except Exception as e:
            logger.error(f"Error unloading model: {str(e)}")
