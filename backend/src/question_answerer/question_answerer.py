# src/question_answerer/question_answerer.py
import logging
import threading
import time
from functools import lru_cache
from typing import List, Dict

import torch
from pydantic_settings import BaseSettings
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, pipeline

from .prompt_templates import question_answering_messages

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    llm_model_name: str = "meta-llama/Llama-3.1-8B-Instruct"
    llm_model_dtype: str = "bfloat16"
    load_in_4bit: bool = True
    compute_dtype: str = "bfloat16"
    max_new_tokens: int = 256
    do_sample: bool = True
    temperature: float = 0.5
    num_return_sequences: int = 1
    rate_limit_questions_per_minute: int = 10

    model_config = {
        "protected_namespaces": ('settings_',)
    }


settings = Settings()


class QuestionAnswerer:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = None
        self.model = None
        self.pipeline = None
        self.last_request_time = 0
        self._lock = threading.Lock()
        self._is_loaded = False

    def _load_model(self):
        """Load model with memory optimization"""
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available. This model requires a GPU.")

        try:
            torch.cuda.empty_cache()

            # Load tokenizer first
            if not self.tokenizer:
                self.tokenizer = AutoTokenizer.from_pretrained(settings.llm_model_name)

            # Check available GPU memory
            total_memory = torch.cuda.get_device_properties(0).total_memory
            reserved_memory = torch.cuda.memory_reserved(0)
            available_memory = total_memory - reserved_memory

            # Load quantized model by default to save memory
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                settings.llm_model_name,
                quantization_config=quantization_config,
                device_map="auto",
                torch_dtype=torch.bfloat16,
                low_cpu_mem_usage=True,
            )

            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device_map="auto",
            )

            self._is_loaded = True

        except Exception as e:
            self.unload_model()
            raise RuntimeError(f"Failed to load model: {str(e)}")

    @lru_cache(maxsize=100)
    def _cached_answer_question(self, question: str, context: str) -> str:
        messages = self._prepare_messages(question, context)

        try:
            response = self._get_model_response(messages)
            return self._parse_response(response)
        except Exception as e:
            raise RuntimeError(f"Error in answering question: {str(e)}")

    def _prepare_messages(self, question: str, context: str) -> List[Dict[str, str]]:
        prepared_messages = []
        for message in question_answering_messages:
            if message['role'] == 'user':
                content = message['content'].format(context=context, question=question)
            else:
                content = message['content']
            prepared_messages.append({"role": message['role'], "content": content})
        return prepared_messages

    def _get_model_response(self, messages: List[Dict[str, str]]) -> str:
        prompt = self._format_messages(messages)
        outputs = self.pipeline(
            prompt,
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.do_sample,
            temperature=settings.temperature,
            num_return_sequences=settings.num_return_sequences,
        )
        return outputs[0]['generated_text']

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        formatted_messages = []
        for message in messages:
            formatted_messages.append(f"{message['role'].capitalize()}: {message['content']}")
        return "\n\n".join(formatted_messages) + "\n\nAssistant:"

    def _parse_response(self, response: str) -> str:
        # Extract the assistant's response from the full output
        assistant_response = response.split("Assistant:")[-1].strip()
        return assistant_response

    def answer_question(self, question: str, context: str) -> str:
        with self._lock:
            if self.model is None:
                self._load_model()

            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < 60 / settings.rate_limit_questions_per_minute:
                time.sleep(60 / settings.rate_limit_questions_per_minute - time_since_last_request)

            self.last_request_time = time.time()
            return self._cached_answer_question(question, context)

    def unload_model(self):
        """Unload model and clear memory"""
        if self._is_loaded:
            if self.model:
                del self.model
            if self.pipeline:
                del self.pipeline
            if self.tokenizer:
                del self.tokenizer

            self.model = None
            self.pipeline = None
            self.tokenizer = None
            self._is_loaded = False

            # Clear CUDA cache
            gc.collect()
            torch.cuda.empty_cache()
            if torch.cuda.is_available():
                torch.cuda.ipc_collect()


question_answerer = QuestionAnswerer()
