"""
FastAPI Application - Request to Standard PoC
Ejecución local con Swagger UI

Ejecutar con:
    uvicorn main:app --reload
"""
import os
from dotenv import load_dotenv
from typing import Literal
from src.core.cleaning import DataCleaning
from src.core.ingestion import DataIngestion
from src.models.rag1_schema import RAG1Schema
from src.models.rag2_schema import RAG2Schema
from fastapi.middleware.cors import CORSMiddleware
from src.core.normalization import DataNormalization
from src.core.pipeline import StandardizationPipeline
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from src.models.response_models import StandardizationResponse, ErrorResponse, HealthResponse

# Cargar variables de entorno
load_dotenv()

# Crear aplicación FastAPI
app = FastAPI(
    title = "Request to Standard API",
    description = """
    API de Estandarización de Datos

    Convierte datos de clientes (CSV/XLSX) a formatos estandarizados RAG 1 o RAG 2.

    Flujo de Procesamiento:
    1. Ingesta: Lee archivos CSV/XLSX
    2. Limpieza: Preprocesa y limpia datos
    3. Normalización: Estructura consistente
    4. Análisis de Metadatos: Identifica contexto y tipo
    5. Routing: Selecciona RAG 1 o RAG 2
    6. Estandarización: Transforma a formato objetivo
    7. Validación: Verifica calidad y umbral

    Formatos RAG:
    - RAG 1: Documentos estructurados (artículos, leyes, normativas)
    - RAG 2: Servicios/tickets/solicitudes
    """,
    version = "0.1.0",
    docs_url = "/docs",
    redoc_url = "/redoc"
)

# CORS (para desarrollo)
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

# Instancia del pipeline
pipeline = StandardizationPipeline()

@app.get(
    "/health",
    tags = ["Health"],
    response_model = HealthResponse,
    summary = "Health Check Detallado"
)
async def health_check():
    """
    Verifica el estado de la API y configuración
    """
    # Verificar configuración Azure OpenAI
    config_status = "configured" if os.getenv("AZURE_OPENAI_O1MINI_API_KEY") else "missing"

    return HealthResponse(
        status = "healthy" if config_status == "configured" else "degraded",
        version = "0.1.0",
        environment = os.getenv("ENVIRONMENT", "development")
    )

@app.post(
    "/standardize",
    tags = ["Estandarización"],
    response_model = StandardizationResponse,
    responses = {
        400: {"model": ErrorResponse, "description": "Error en el archivo o parámetros"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"}
    },
    summary = "Estandarizar Datos (Flujo Completo)",
    description = """
    **Endpoint principal** - Ejecuta el flujo completo de estandarización.

    Pipeline completo (según diagrama):
    1. Ingesta de datos
    2. Limpieza
    3. Normalización
    4. Mapeo de columnas
    5. Estandarización al RAG especificado
    6. Validación y cálculo de umbral

    Entrada:
    - file: Archivo CSV o XLSX
    - target_rag: RAG objetivo ("rag1" o "rag2") - El orquestador decide esto

    Salida:
    - Datos estandarizados en el formato RAG especificado
    - Metadatos del procesamiento
    - Umbral de confianza (confidence_score)

    RAG 1: Documentos estructurados (leyes, artículos, normativas)
    RAG 2: Servicios/Tickets (solicitudes, incidentes, soporte)

    Flujo recomendado:
    - Opción A: POST /analyze → decidir → POST /standardize
    - Opción B: POST /standardize directamente (si ya sabes qué RAG usar)
    """
)
async def standardize_data(
    file: UploadFile = File(
        ...,
        description = "Archivo CSV o XLSX con datos a estandarizar"
    ),
    target_rag: Literal["rag1", "rag2"] = Form(
        ...,
        description = "RAG objetivo: 'rag1' para documentos estructurados, 'rag2' para servicios/tickets"
    ),
    generate_embeddings: bool = Form(
        False,
        description = "Generar embeddings para los datos (requiere configuración de embeddings)"
    )
):
    """
    Procesa archivo y retorna datos estandarizados

    Ejemplo de uso:
    ```python
    import requests

    files = {'file': open('datos.csv', 'rb')}
    data = {'target_rag': 'rag1', 'generate_embeddings': False}

    response = requests.post('http://localhost:8000/standardize', files=files, data=data)
    result = response.json()
    ```
    """
    try:
        # Validar tipo de archivo
        if not file.filename:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "Nombre de archivo no válido"
            )

        file_ext = file.filename.lower().split('.')[-1]
        if file_ext not in ['csv', 'xlsx', 'xls']:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = f"Tipo de archivo no soportado: {file_ext}. Use CSV o XLSX"
            )

        # Leer contenido del archivo
        file_content = await file.read()
        file_size = len(file_content)

        # Validar tamaño (máximo 50MB por defecto)
        max_size = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = f"Archivo muy grande. Máximo: {max_size / 1024 / 1024}MB"
            )

        # Procesar con pipeline
        result = await pipeline.process(
            file_content = file_content,
            filename = file.filename,
            file_size = file_size,
            target_rag = target_rag,
            generate_embeddings = generate_embeddings
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f"Error procesando archivo: {str(e)}"
        )

@app.post(
    "/analyze",
    tags = ["Análisis"],
    summary = "Preview y Análisis (OPCIONAL)",
    description = """
    **ENDPOINT OPCIONAL** - Preview del archivo antes de estandarizar.

    El orquestador puede usar este endpoint para obtener información y decidir qué RAG usar,
    O puede llamar directamente a /standardize si ya sabe qué RAG necesita.

    Retorna:
    - Estructura: filas, columnas, tipos de datos, muestra de datos
    - Contexto: tipo de datos, dominio, intención (análisis LLM)
    - Sugerencia: qué RAG usar (suggested_rag)

    NOTA: Este endpoint NO estandariza datos, solo analiza.
    Para estandarizar, usar POST /standardize
    """
)
async def analyze_file(
    file: UploadFile = File(..., description = "Archivo CSV o XLSX a analizar")
):
    """
    [OPCIONAL] Preview y análisis del archivo para ayudar al orquestador a decidir.

    Flujo recomendado:
    1. (Opcional) POST /analyze → obtener suggested_rag
    2. Orquestador decide basado en suggested_rag
    3. POST /standardize con target_rag especificado

    El orquestador puede saltarse el paso 1 si ya sabe qué RAG necesita.
    """
    try:
        from src.gpt.client import AzureOpenAIClient
        from src.gpt.prompts import PromptTemplates
        from src.utils.sampling import DataSampler
        from src.utils.json_utils import df_to_json_safe, clean_for_json
        import json

        # Leer y procesar hasta normalización
        file_content = await file.read()

        ingestion = DataIngestion()
        df = await ingestion.ingest(file_content, file.filename)

        cleaning = DataCleaning()
        df_clean = await cleaning.clean(df)

        normalization = DataNormalization()
        df_normalized = await normalization.normalize(df_clean)

        # Análisis con LLM
        sampler = DataSampler()
        data_summary = sampler.get_data_summary(df_normalized)

        # IMPORTANTE: Limpiar data_summary antes de enviar al LLM
        data_summary_clean = clean_for_json(data_summary)

        prompts = PromptTemplates()
        prompt = prompts.metadata_analysis_prompt(data_summary_clean)

        llm_client = AzureOpenAIClient()
        messages = [
            {
                "role": "system",
                "content": "Eres un experto en clasificación de datos. Respondes siempre en formato JSON válido."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        response = await llm_client.chat_completion(messages, temperature=0.2)

        try:
            analysis = json.loads(response)
        except json.JSONDecodeError:
            analysis = {
                "tipo_consulta": "No determinado",
                "contexto_negocio": "General",
                "parametros_relevantes": list(df_normalized.columns),
                "intencion_usuario": "Estandarización de datos",
                "nivel_confianza": 0.5
            }

        # Sugerencia de RAG basada en keywords simples
        columns_lower = [col.lower() for col in df_normalized.columns]
        rag1_keywords = ['titulo', 'texto', 'articulo', 'numero', 'ley']
        rag2_keywords = ['descripcion', 'servicio', 'categoria', 'subcategoria', 'ticket']

        rag1_score = sum(1 for kw in rag1_keywords if any(kw in col for col in columns_lower))
        rag2_score = sum(1 for kw in rag2_keywords if any(kw in col for col in columns_lower))

        suggested_rag = "rag1" if rag1_score > rag2_score else "rag2"

        # Limpiar datos para JSON (maneja NaN, fechas, infinity, etc.)
        sample_data = df_to_json_safe(df_normalized.head(3))

        return {
            "success": True,
            "filename": file.filename,
            "structure": {
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df_normalized.dtypes.items()}
            },
            "analysis": clean_for_json(analysis),  # Limpiar también el analysis
            "suggested_rag": suggested_rag,
            "suggestion_confidence": {
                "rag1_score": rag1_score,
                "rag2_score": rag2_score
            },
            "sample": sample_data,
            "next_step": f"POST /standardize con target_rag='{suggested_rag}'",
            "note": "Este es un preview OPCIONAL. Para estandarizar, llamar a POST /standardize con el target_rag deseado."
        }

    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f"Error analizando archivo: {str(e)}"
        )

@app.get(
    "/schemas",
    tags = ["Información"],
    summary = "Obtener Esquemas RAG"
)
async def get_schemas():
    """Retorna esquemas de RAG 1 y RAG 2"""

    return {
        "rag1": RAG1Schema.model_json_schema(),
        "rag2": RAG2Schema.model_json_schema()
    }

# Punto de entrada
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host = "0.0.0.0",
        port = 8000,
        reload = True,
        log_level = "info"
    )

# uvicorn main:app --reload