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
    vision_deployment: Optional[str] = None  # For vision-capable models like gpt-4o

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
            embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            vision_deployment=os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT", os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))
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

    async def analyze_image(
        self,
        image_base64: str,
        image_format: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> str:
        """
        Analiza una imagen usando el modelo de visión de Azure OpenAI.

        Args:
            image_base64: Imagen codificada en base64
            image_format: Formato de la imagen ('png', 'jpeg', etc.)
            prompt: Prompt para el análisis de la imagen
            temperature: Temperatura para generación (más bajo = más determinista)
            max_tokens: Máximo de tokens en respuesta

        Returns:
            Descripción/análisis de la imagen generado por el modelo

        Raises:
            ValueError: Si vision_deployment no está configurado
            Exception: Si hay error en la llamada a la API
        """
        if not self.settings.vision_deployment:
            raise ValueError("Vision deployment no configurado. Configure AZURE_OPENAI_VISION_DEPLOYMENT")

        try:
            # Construir el mensaje multimodal para visión
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]

            # Llamar a la API de chat con contenido multimodal
            response = self.client.chat.completions.create(
                model=self.settings.vision_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"Error en análisis de imagen con Azure OpenAI: {str(e)}")

    async def analyze_multiple_images(
        self,
        images: List[dict],
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 800
    ) -> str:
        """
        Analiza múltiples imágenes en un solo prompt.

        Args:
            images: Lista de diccionarios con 'base64' y 'format' de cada imagen
            prompt: Prompt para el análisis de las imágenes
            temperature: Temperatura para generación
            max_tokens: Máximo de tokens en respuesta

        Returns:
            Descripción/análisis combinado de todas las imágenes

        Raises:
            ValueError: Si vision_deployment no está configurado
            Exception: Si hay error en la llamada a la API
        """
        if not self.settings.vision_deployment:
            raise ValueError("Vision deployment no configurado. Configure AZURE_OPENAI_VISION_DEPLOYMENT")

        try:
            # Construir contenido con texto y múltiples imágenes
            content = [{"type": "text", "text": prompt}]

            for idx, img in enumerate(images):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{img['format']};base64,{img['base64']}"
                    }
                })

            messages = [{"role": "user", "content": content}]

            # Llamar a la API
            response = self.client.chat.completions.create(
                model=self.settings.vision_deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"Error en análisis de múltiples imágenes: {str(e)}")