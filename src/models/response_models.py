"""
Modelos de respuesta (Response) para la API
"""
from .request_models import FileInfo
from pydantic import BaseModel, Field
from typing import Dict, Any, Literal, Optional


class StandardizationResponse(BaseModel):
    """Respuesta principal de estandarización"""
    success: bool = Field(..., description="Indica si el procesamiento fue exitoso")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    selected_rag: Literal["rag1", "rag2"] = Field(..., description="RAG seleccionado")
    file_info: FileInfo = Field(..., description="Información del archivo procesado")
    result: Dict[str, Any] = Field(..., description="Datos estandarizados")
    processing_time_seconds: float = Field(..., description="Tiempo de procesamiento")

    class Config:
        # Permitir tipos arbitrarios para flexibilidad con datos limpios
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Datos estandarizados exitosamente a formato RAG 1",
                "selected_rag": "rag1",
                "file_info": {
                    "filename": "datos.csv",
                    "size_bytes": 15420,
                    "rows_count": 100,
                    "columns_count": 8,
                    "file_type": "csv"
                },
                "result": {
                    "format": "rag1_standard",
                    "data": [],
                    "metadata": {},
                    "confidence_score": 0.92
                },
                "processing_time_seconds": 2.45
            }
        }


class ErrorResponse(BaseModel):
    """Respuesta de error"""
    success: bool = Field(default=False)
    error: str = Field(..., description="Descripción del error")
    detail: Optional[str] = Field(None, description="Detalle adicional del error")


class HealthResponse(BaseModel):
    """Respuesta del endpoint de health check"""
    status: str = Field(default="healthy")
    version: str = Field(default="0.1.0")
    environment: str
