# src/questionnaire_manager/llm_question_extractor.py
import copy
import json
import logging
import os
import re
from contextlib import contextmanager
from threading import Lock
from typing import Dict, Union, List

import torch
import yaml
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, pipeline

from .prompt_templates import extraction_messages, verification_messages

logging.basicConfig(level=logging.DEBUG, force=True)
logger = logging.getLogger(__name__)


class LLMQuestionExtractor:
    _instance = None
    _lock = Lock()

    def __new__(cls, force_new=False):
        if force_new or cls._instance is None:
            with cls._lock:
                instance = super(LLMQuestionExtractor, cls).__new__(cls)
                instance.initialize()
                if not force_new:
                    cls._instance = instance
        return cls._instance if not force_new else instance

    def initialize(self):
        self.config = self._load_config()
        self.tokenizer = AutoTokenizer.from_pretrained(self.config['model_name'])
        self.model = None
        self.pipeline = None
        self._load_model()

    def _load_config(self):
        config_locations = [
            os.path.join(os.path.dirname(__file__), 'config.yaml'),  # Check script's directory
        ]

        for location in config_locations:
            if location and os.path.exists(location):
                try:
                    with open(location, 'r') as file:
                        logger.info(f"Loading configuration from {location}")
                        return yaml.safe_load(file)
                except Exception as e:
                    logger.warning(f"Failed to load configuration from {location}: {str(e)}")

        logger.error("No valid configuration file found.")
        raise FileNotFoundError("No valid configuration file found.")

    def _clean_json(self, json_string: str) -> dict:
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
        try:
            outputs = self.pipeline(
                messages,
                max_new_tokens=self.config['generation']['max_new_tokens'],
                do_sample=self.config['generation']['do_sample'],
                temperature=self.config['generation']['temperature'],
                num_return_sequences=self.config['generation']['num_return_sequences'],
            )

            response = outputs[0]['generated_text'][-1]['content']
            logger.info(f"Model response: {response}")
            return response.strip()
        except Exception as e:
            logger.error(f"Error in getting model response: {str(e)}")
            raise

    def _clean_extracted_text(self, text: str) -> str:
        # Remove newlines, tabs, and extra spaces
        cleaned = re.sub(r'\s+', ' ', text).strip()
        return cleaned

    def _clean_extracted_json(self, extracted_json: Dict[str, List[str]]) -> Dict[str, List[str]]:
        cleaned_json = {}
        for key, value_list in extracted_json.items():
            cleaned_json[key] = [self._clean_extracted_text(item) for item in value_list]
        return cleaned_json

    def extract_questions(self, content: str) -> Dict[str, List[str]]:
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

    def verify_extraction(self, content: str, extracted_json: Dict[str, List[str]]) -> Dict[
        str, Union[str, Dict[str, List[str]]]]:
        logger.info(f"Verifying extraction. Content: {content[:100]}...")
        logger.info(f"Extracted JSON: {extracted_json}")
        messages = copy.deepcopy(verification_messages)
        if "content" not in messages[1]:
            logger.error(f"'content' key missing in messages[1]: {messages[1]}")
            raise KeyError("'content' key missing in messages[1]")

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

    def unload_model(self):
        logger.info(f"VRAM usage before unloading: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
        if self.model:
            del self.model
        if self.pipeline:
            del self.pipeline
        if hasattr(self, 'tokenizer'):
            del self.tokenizer
        self.model = None
        self.pipeline = None
        self.tokenizer = None

        import gc
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

        if torch.cuda.is_available():
            with torch.cuda.device('cuda'):
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

        logger.info(f"VRAM usage after unloading: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")

    @classmethod
    def reset_instance(cls):
        logger.info(f"VRAM usage before reset: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
        if cls._instance:
            cls._instance.unload_model()
        cls._instance = None
        torch.cuda.empty_cache()
        logger.info(f"VRAM usage after reset: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")

    def _load_model(self):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available. This model requires a GPU.")

        logger.info("Checking available GPU memory...")
        total_memory = torch.cuda.get_device_properties(0).total_memory
        reserved_memory = torch.cuda.memory_reserved(0)
        available_memory = total_memory - reserved_memory

        # Estimate model size (adjust this based on your specific model)
        estimated_model_size = 8 * 2 * (1024 ** 3)  # 8 GB for an 8B parameter model

        if available_memory > estimated_model_size:
            logger.info("Sufficient GPU memory available. Attempting to load full-precision model...")
            try:
                torch.cuda.empty_cache()  # Clear GPU memory before loading

                self.model = AutoModelForCausalLM.from_pretrained(
                    self.config['model_name'],
                    device_map="auto",
                    torch_dtype=getattr(torch, self.config['model_dtype']),
                    low_cpu_mem_usage=True,
                )
                logger.info("Full-precision model loaded successfully.")
            except Exception as full_precision_error:
                logger.warning(f"Failed to load full-precision model: {str(full_precision_error)}. Falling back to quantized model.")
                self._load_quantized_model()
        else:
            logger.info("Insufficient GPU memory for full-precision model. Loading quantized model.")
            self._load_quantized_model()

        # Create the pipeline using the loaded model
        self.pipeline = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device_map="auto",
        )
        logger.info("Text generation pipeline created successfully.")

    def _load_quantized_model(self):
        try:
            torch.cuda.empty_cache()  # Clear GPU memory again
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=self.config['quantization']['load_in_4bit'],
                bnb_4bit_compute_dtype=getattr(torch, self.config['quantization']['compute_dtype']),
                llm_int8_enable_fp32_cpu_offload=True  # Enable CPU offloading
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config['model_name'],
                quantization_config=quantization_config,
                device_map="auto",
                torch_dtype=getattr(torch, self.config['model_dtype']),
                low_cpu_mem_usage=True,
            )
            logger.info("Quantized model loaded successfully.")
        except Exception as quantized_error:
            logger.error(f"Failed to load quantized model: {str(quantized_error)}")
            raise RuntimeError(f"Failed to load quantized model. Error: {str(quantized_error)}")

def clear_gpu_memory():
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()
    if torch.cuda.is_available():
        with torch.cuda.device('cuda'):
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

@contextmanager
def load_model_context(extractor: LLMQuestionExtractor = None):
    if extractor is None:
        extractor = LLMQuestionExtractor()
    try:
        yield extractor
    finally:
        extractor.unload_model()
        LLMQuestionExtractor.reset_instance()
        clear_gpu_memory()

def extract_and_verify_questions(content: str) -> Dict[str, list]:
    with load_model_context() as extractor:
        extracted_json = extractor.extract_questions(content)
        verification_result = extractor.verify_extraction(content, extracted_json)
        return verification_result["json"]
