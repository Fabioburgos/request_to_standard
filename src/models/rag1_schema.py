"""
RAG 1 Schema - Modelo para artículos/documentos estructurados
Basado en el esquema de base de datos proporcionado
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class RAG1Schema(BaseModel):
    """
    Schema para RAG 1:
    - Orientado a artículos/documentos con estructura formal
    - Incluye campos como artículo_id, tipo, número, título, texto
    """
    id: str = Field(..., description="ID único del registro")
    articulo_id: str = Field(..., description="ID del artículo")
    tipo: str = Field(..., description="Tipo de documento/artículo")
    numero: int = Field(..., description="Número del artículo", ge=0, le=32767)  # SMALLINT
    titulo: str = Field(..., description="Título del artículo")
    texto: str = Field(..., description="Texto/contenido del artículo")
    image_caption: Optional[str] = Field(None, description="Descripción de imagen asociada")
    keywords: Optional[str] = Field(None, description="Palabras clave separadas por coma")
    embedding: Optional[List[float]] = Field(None, description="Vector de embedding")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "art_001_2024",
                "articulo_id": "ART001",
                "tipo": "Ley",
                "numero": 42,
                "titulo": "Ley de Protección de Datos",
                "texto": "Artículo 42. Toda persona tiene derecho a la protección de sus datos personales...",
                "image_caption": None,
                "keywords": "datos personales, protección, privacidad",
                "embedding": None
            }
        }


class RAG1Response(BaseModel):
    """Respuesta con payload RAG 1"""
    format: str = Field(default="rag1_standard", description="Formato del payload")
    data: List[RAG1Schema] = Field(..., description="Lista de registros estandarizados")
    metadata: dict = Field(default_factory=dict, description="Metadatos del procesamiento")
    confidence_score: float = Field(..., description="Umbral de confianza", ge=0.0, le=1.0)