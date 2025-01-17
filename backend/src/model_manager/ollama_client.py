# src/model_manager/ollama_client.py
import logging
from typing import Optional

import httpx
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class OllamaSettings(BaseSettings):
    host: str = "http://localhost:11434"
    extract_model: str = "llama3.2:1b"
    answer_model: str = "llama3.2"
    timeout: int = 120

    model_config = {
        "env_prefix": "OLLAMA_",
        "case_sensitive": False,
        "validate_assignment": True
    }


class OllamaClient:
    def __init__(self, settings: Optional[OllamaSettings] = None):
        self.settings = settings or OllamaSettings()
        self.client = httpx.Client(timeout=self.settings.timeout)
        self._models_loaded = set()

    def _get_url(self, endpoint: str) -> str:
        return f"{self.settings.host}/api/{endpoint}"

    async def generate(self, prompt: str, model: str, system: Optional[str] = None) -> str:
        """Generate a response using the specified model"""
        try:
            if model not in self._models_loaded:
                await self.load_model(model)

            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": 0  # Model will automatically unload after request
            }
            if system:
                data["system"] = system

            response = self.client.post(self._get_url("generate"), json=data)
            response.raise_for_status()
            return response.json()["response"]

        except Exception as e:
            logger.error(f"Error generating response with Ollama: {str(e)}")
            raise

    async def load_model(self, model: str):
        """Load a model into Ollama"""
        try:
            response = self.client.post(self._get_url("pull"), json={"name": model})
            response.raise_for_status()
            self._models_loaded.add(model)
            logger.info(f"Successfully loaded model: {model}")
        except Exception as e:
            logger.error(f"Error loading model {model}: {str(e)}")
            raise

    def __del__(self):
        """Cleanup when the client is destroyed"""
        if hasattr(self, 'client'):
            self.client.close()


# Create a singleton instance
ollama_client = OllamaClient()
