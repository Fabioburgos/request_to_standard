"""
RAG 2 Schema - Modelo para servicios/tickets/solicitudes
Basado en el esquema de datos proporcionado
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class RAG2Schema(BaseModel):
    """
    Schema para RAG 2:
    - Orientado a servicios/tickets/solicitudes
    - Incluye campos como descripción, tipo, servicio, categoría, subcategoría
    """
    id: str = Field(..., description="ID único generado a partir de la descripción")
    descripcion: str = Field(..., description="Descripción del servicio/solicitud")
    tipo: str = Field(..., description="Tipo de servicio")
    servicio: str = Field(..., description="Nombre del servicio")
    categoria: str = Field(..., description="Categoría del servicio")
    subcategoria: str = Field(..., description="Subcategoría del servicio")
    fuente: str = Field(..., description="Fuente de la solicitud")
    embedding: Optional[List[float]] = Field(None, description="Vector de embedding")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "desc_hash_abc123",
                "descripcion": "Solicitud de soporte técnico para configuración de red",
                "tipo": "Soporte Técnico",
                "servicio": "Infraestructura IT",
                "categoria": "Redes",
                "subcategoria": "Configuración",
                "fuente": "email",
                "embedding": None
            }
        }


class RAG2Response(BaseModel):
    """Respuesta con payload RAG 2"""
    format: str = Field(default="rag2_standard", description="Formato del payload")
    data: List[RAG2Schema] = Field(..., description="Lista de registros estandarizados")
    metadata: dict = Field(default_factory=dict, description="Metadatos del procesamiento")
    confidence_score: float = Field(..., description="Umbral de confianza", ge=0.0, le=1.0)