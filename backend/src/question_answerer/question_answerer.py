# src/question_answerer/question_answerer.py
import os
import threading
import time
from functools import lru_cache
from typing import List, Dict


import torch
from pydantic_settings import BaseSettings
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, pipeline

from .prompt_templates import question_answering_messages


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
        self.tokenizer = AutoTokenizer.from_pretrained(settings.llm_model_name)
        self.model = None
        self.pipeline = None
        self.last_request_time = 0
        self._lock = threading.Lock()

    def _load_model(self):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available. This model requires a GPU.")

        try:
            torch.cuda.empty_cache()

            # Check available GPU memory
            total_memory = torch.cuda.get_device_properties(0).total_memory
            reserved_memory = torch.cuda.memory_reserved(0)
            available_memory = total_memory - reserved_memory

            # Estimate model size (this is a rough estimate, adjust as needed)
            model_size = 8 * 2 * (1024 ** 3)  # 8 GB for 8B parameter model

            if available_memory > model_size:
                # Try to load the full-precision model
                try:
                    self.model = AutoModelForCausalLM.from_pretrained(
                        settings.llm_model_name,
                        device_map="auto",
                        torch_dtype=getattr(torch, settings.llm_model_dtype),
                        low_cpu_mem_usage=True,
                    )
                    print("Loaded full-precision model successfully.")
                except Exception as e:
                    print(f"Failed to load full-precision model: {str(e)}. Falling back to quantized model.")
                    self._load_quantized_model()
            else:
                print("Insufficient GPU memory for full-precision model. Loading quantized model.")
                self._load_quantized_model()

            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device_map="auto",
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")

    def _load_quantized_model(self):
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=settings.load_in_4bit,
            bnb_4bit_compute_dtype=getattr(torch, settings.compute_dtype),
            llm_int8_enable_fp32_cpu_offload=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            settings.llm_model_name,
            quantization_config=quantization_config,
            device_map="auto",
            torch_dtype=getattr(torch, settings.llm_model_dtype),
            low_cpu_mem_usage=True,
        )

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
        with self._lock:
            if self.model:
                del self.model
                self.model = None
            if self.pipeline:
                del self.pipeline
                self.pipeline = None
            torch.cuda.empty_cache()


question_answerer = QuestionAnswerer()