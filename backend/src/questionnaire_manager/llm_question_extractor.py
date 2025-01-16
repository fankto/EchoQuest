# src/questionnaire_manager/llm_question_extractor.py
import copy
import json
import logging
import re
from threading import Lock
from typing import Dict, List

from ..model_manager.manager import model_manager
from .prompt_templates import extraction_messages

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
        """Clean and parse JSON from model response"""
        try:
            # First try direct JSON parsing
            data = json.loads(json_string)

            # Extract just the items from extracted_items
            if isinstance(data, dict) and "extracted_items" in data:
                items = [item["item"] for item in data["extracted_items"] if isinstance(item, dict) and "item" in item]
                return {"items": items}

            return {"items": []}

        except json.JSONDecodeError:
            # If direct parsing fails, try to extract JSON using regex
            try:
                # Find JSON object pattern
                json_pattern = r'\{[\s\S]*\}'
                match = re.search(json_pattern, json_string)
                if match:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict) and "extracted_items" in data:
                        items = [item["item"] for item in data["extracted_items"] if isinstance(item, dict) and "item" in item]
                        return {"items": items}
            except:
                pass

            logger.error("Failed to parse JSON response")
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


async def extract_and_verify_questions(content: str) -> Dict[str, list]:
    """Main function to extract questions"""
    try:
        extractor = LLMQuestionExtractor()
        return await extractor.extract_questions(content)
    finally:
        # Ensure model is unloaded after extraction
        model_manager.unload_model('llm_extract')