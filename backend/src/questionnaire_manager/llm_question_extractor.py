# src/questionnaire_manager/llm_question_extractor.py
import copy
import json
import logging
import re
from threading import Lock
from typing import Dict, Union, List

from ..model_manager.manager import model_manager
from .prompt_templates import extraction_messages, verification_messages

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
        def fix_json(s):
            # Fix unquoted keys
            s = re.sub(r'(\w+)(?=\s*:)', r'"\1"', s)
            # Remove trailing commas
            s = re.sub(r',\s*}', '}', s)
            s = re.sub(r',\s*]', ']', s)
            return s

        # Find all potential JSON objects
        json_objects = re.findall(r'\{.*?\}', json_string, re.DOTALL)

        for obj in json_objects:
            try:
                return json.loads(obj)
            except json.JSONDecodeError:
                fixed_obj = fix_json(obj)
                try:
                    return json.loads(fixed_obj)
                except json.JSONDecodeError:
                    continue

        logger.warning("No valid JSON found in the response")
        return {"items": []}

    def _get_model_response(self, messages: List[Dict[str, str]]) -> str:
        """Get response from the model using the centralized pipeline"""
        try:
            pipeline = model_manager.get_pipeline('llm')
            outputs = pipeline(
                messages
            )  # Pipeline parameters are now set during pipeline creation in ModelManager

            response = outputs[0]['generated_text'][-1]['content']
            logger.info(f"Model response: {response}")
            return response.strip()
        except Exception as e:
            logger.error(f"Error in getting model response: {str(e)}")
            raise

    def _clean_extracted_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace"""
        return re.sub(r'\s+', ' ', text).strip()

    def _clean_extracted_json(self, extracted_json: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Clean all extracted items in the JSON"""
        cleaned_json = {}
        for key, value_list in extracted_json.items():
            cleaned_json[key] = [self._clean_extracted_text(item) for item in value_list]
        return cleaned_json

    def extract_questions(self, content: str) -> Dict[str, List[str]]:
        """Extract questions from content using the LLM"""
        logger.info(f"Extracting questions from content: {content[:100]}...")
        messages = copy.deepcopy(extraction_messages)
        messages[1]["content"] = messages[1]["content"].format(content=content)

        response = self._get_model_response(messages)
        logger.info(f"Raw LLM extraction response:\n{response}")

        extracted_json = self._clean_json(response)
        logger.info(f"Extracted JSON after cleaning:\n{extracted_json}")

        cleaned_json = self._clean_extracted_json(extracted_json)
        logger.info(f"Final cleaned extracted JSON:\n{cleaned_json}")

        return cleaned_json

    def verify_extraction(
            self,
            content: str,
            extracted_json: Dict[str, List[str]]
    ) -> Dict[str, Union[str, Dict[str, List[str]]]]:
        """Verify and potentially correct extracted questions"""
        logger.info(f"Verifying extraction. Content: {content[:100]}...")
        messages = copy.deepcopy(verification_messages)

        if "items" in extracted_json:
            extracted_items = json.dumps(extracted_json["items"])
            messages[1]["content"] = messages[1]["content"].format(
                content=content,
                extracted_items=extracted_items
            )
        else:
            logger.error(f"'items' key missing in extracted JSON: {extracted_json}")
            raise KeyError("'items' key missing in extracted JSON")

        response = self._get_model_response(messages)
        logger.info(f"LLM verification response:\n{response}")

        if "yes" in response.strip().lower():
            logger.info("Verification passed. Returning original JSON.")
            return {"result": "yes", "json": extracted_json}

        corrected_json = self._clean_json(response)
        if corrected_json["items"]:
            cleaned_corrected_json = self._clean_extracted_json(corrected_json)
            logger.info(f"Verification failed. Corrected and cleaned JSON:\n{cleaned_corrected_json}")
            return {"result": "no", "json": cleaned_corrected_json}
        else:
            logger.error("No valid JSON found in the verification response")
            return {"result": "no", "json": extracted_json}


def extract_and_verify_questions(content: str) -> Dict[str, list]:
    """Convenience function to perform extraction and verification"""
    extractor = LLMQuestionExtractor()
    extracted_json = extractor.extract_questions(content)
    verification_result = extractor.verify_extraction(content, extracted_json)
    return verification_result["json"]