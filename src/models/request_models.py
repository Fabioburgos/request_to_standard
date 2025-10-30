"""
Modelos de entrada (Request) para la API
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class StandardizationRequest(BaseModel):
    """Request para estandarización de datos"""
    sample_size: int = Field(
        100,
        description="Número de filas para muestreo en análisis",
        ge=10,
        le=1000
    )
    generate_embeddings: bool = Field(
        False,
        description="Generar embeddings para los datos estandarizados"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sample_size": 100,
                "generate_embeddings": False
            }
        }


class FileInfo(BaseModel):
    """Información del archivo procesado"""
    filename: str
    size_bytes: int
    rows_count: int
    columns_count: int
    file_type: str  # csv o xlsx
