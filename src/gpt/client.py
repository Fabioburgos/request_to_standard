"""
Cliente Azure OpenAI
Centraliza la comunicación con Azure OpenAI
"""
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from typing import Optional, List
from pydantic_settings import BaseSettings

load_dotenv()


class AzureOpenAISettings(BaseSettings):
    """Configuración de Azure OpenAI desde variables de entorno"""
    api_key: str
    api_version: str
    endpoint: str
    deployment_name: str
    embedding_deployment: Optional[str] = None

    class Config:
        env_prefix = "AZURE_OPENAI_O1MINI_"
        case_sensitive = False


class AzureOpenAIClient:
    """Cliente para Azure OpenAI"""

    def __init__(self):
        self.settings = AzureOpenAISettings(
            api_key=os.getenv("AZURE_OPENAI_O1MINI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_O1MINI_API_VERSION"),
            endpoint=os.getenv("AZURE_OPENAI_O1MINI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        )

        self.client = AzureOpenAI(
            api_key=self.settings.api_key,
            api_version=self.settings.api_version,
            azure_endpoint=self.settings.endpoint
        )

    async def chat_completion(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Ejecuta chat completion

        Args:
            messages: Lista de mensajes en formato OpenAI
            temperature: Temperatura para generación
            max_tokens: Máximo de tokens en respuesta

        Returns:
            Respuesta del modelo
        """
        try:
            response = self.client.chat.completions.create(
                model=self.settings.deployment_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"Error en Azure OpenAI chat completion: {str(e)}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Genera embedding para un texto

        Args:
            text: Texto a vectorizar

        Returns:
            Vector de embedding
        """
        if not self.settings.embedding_deployment:
            raise ValueError("Embedding deployment no configurado")

        try:
            response = self.client.embeddings.create(
                model=self.settings.embedding_deployment,
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            raise Exception(f"Error generando embedding: {str(e)}")