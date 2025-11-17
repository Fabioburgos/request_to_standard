"""
Tool MCP: Estandarización de Datos
Expone funcionalidad de estandarización al orquestador
"""
import os
import base64
import logging
from typing import Literal, Optional

logger = logging.getLogger(__name__)

def get_tool_definition():
    """
    Retorna la definición de la herramienta MCP.
    """
    from mcp.types import Tool

    return Tool(
        name="standardize_data",
        description=(
            "Estandariza archivos CSV/XLSX a formatos RAG optimizados con análisis automático de imágenes mediante AI.\n\n"

            "CASOS DE USO PRINCIPALES:\n"
            "• Convertir datos no estructurados a formato RAG 1 (documentos legales, artículos, normativas)\n"
            "• Convertir datos no estructurados a formato RAG 2 (tickets de soporte, servicios, solicitudes)\n"
            "• Análisis automático de imágenes embebidas en archivos XLSX con Azure OpenAI Vision\n"
            "• Validación de estructura y cálculo de umbral de confianza\n"
            "• Generación de embeddings (opcional)\n\n"

            "PROCESO AUTOMÁTICO (PIPELINE DE 6 PASOS):\n"
            "1. Ingesta de datos + extracción de imágenes embebidas (solo XLSX)\n"
            "2. Limpieza y preprocesamiento de datos\n"
            "3. Identificación de columnas relevantes\n"
            "4. Normalización de estructura\n"
            "5. Estandarización a formato RAG + análisis de imágenes con AI\n"
            "6. Validación y cálculo de confidence_score\n\n"

            "FORMATOS RAG DISPONIBLES:\n"
            "• RAG 1: Documentos estructurados\n"
            "  - Campos: id, articulo_id, tipo, numero, titulo, texto, image_caption, keywords, embedding\n"
            "  - Uso: Leyes, artículos, normativas, documentación formal\n"
            "  - Análisis de imágenes: Activo (genera image_caption automáticamente)\n"
            "\n"
            "• RAG 2: Servicios/Tickets\n"
            "  - Campos: id, descripcion, tipo, servicio, categoria, subcategoria, fuente, embedding\n"
            "  - Uso: Tickets de soporte, solicitudes, incidentes, servicios\n"
            "  - Análisis de imágenes: No aplicable\n\n"

            "ANÁLISIS AUTOMÁTICO DE IMÁGENES (solo RAG 1 + XLSX):\n"
            "• Extrae imágenes embebidas de archivos Excel\n"
            "• Analiza contenido con Azure OpenAI Vision (GPT-4o)\n"
            "• Genera descripciones enfocadas en: pasos secuenciales, procesos, diagramas, texto en imágenes\n"
            "• Popula automáticamente el campo image_caption\n"
            "• Soporta múltiples imágenes por fila\n\n"

            "PARÁMETROS DE ENTRADA:\n"
            "• file_content (requerido): Contenido del archivo en base64\n"
            "• filename (requerido): Nombre del archivo (ej: datos.csv, documentos.xlsx)\n"
            "• target_rag (requerido): 'rag1' para documentos, 'rag2' para servicios\n"
            "• generate_embeddings (opcional): true para generar embeddings, false por defecto\n\n"

            "USAR CUANDO:\n"
            "• Necesitas estructurar datos de clientes en formatos estándar\n"
            "• Preparar documentos para sistemas RAG (Retrieval-Augmented Generation)\n"
            "• Analizar imágenes procedurales automáticamente\n"
            "• Convertir Excel/CSV a JSON estructurado\n"
            "• Validar calidad de datos con scoring automático\n\n"

            "NO USAR para:\n"
            "• Archivos que NO son CSV o XLSX\n"
            "• Datos ya completamente estandarizados\n"
            "• Archivos sin estructura tabular\n"
            "• Procesamiento de imágenes independientes (usa esta tool solo si vienen en Excel)\n\n"

            "RESPUESTA:\n"
            "• success: boolean indicando éxito/fallo\n"
            "• result: Objeto con datos estandarizados, metadatos, confidence_score\n"
            "• Tiempo de procesamiento y estadísticas detalladas"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_content": {
                    "type": "string",
                    "description": "Contenido del archivo codificado en base64. Ejemplo: base64.b64encode(open('archivo.csv', 'rb').read()).decode('utf-8')"
                },
                "filename": {
                    "type": "string",
                    "description": "Nombre del archivo incluyendo extensión (.csv o .xlsx). Ejemplos: 'datos.csv', 'documentos.xlsx', 'tickets.csv'"
                },
                "target_rag": {
                    "type": "string",
                    "enum": ["rag1", "rag2"],
                    "description": "Formato de salida objetivo. 'rag1' para documentos estructurados (leyes, artículos), 'rag2' para servicios/tickets"
                },
                "generate_embeddings": {
                    "type": "boolean",
                    "description": "Si se deben generar embeddings para los datos. Default: false. Requiere configuración de Azure OpenAI Embeddings"
                }
            },
            "required": ["file_content", "filename", "target_rag"]
        }
    )


async def invoke_standardize_tool(
    file_content: str,
    filename: str,
    target_rag: Literal["rag1", "rag2"],
    generate_embeddings: bool = False
) -> dict:
    """
    Invoca el pipeline de estandarización de datos.

    Args:
        file_content: Contenido del archivo en base64
        filename: Nombre del archivo (debe terminar en .csv o .xlsx)
        target_rag: Formato objetivo ('rag1' o 'rag2')
        generate_embeddings: Si generar embeddings (default: False)

    Returns:
        dict con:
            - success: bool
            - result: dict con datos estandarizados (si success=True)
            - error: str con mensaje de error (si success=False)
    """
    try:
        logger.info(f"=== Invocando Standardize Tool ===")
        logger.info(f"Archivo: {filename}")
        logger.info(f"Target RAG: {target_rag.upper()}")
        logger.info(f"Generate Embeddings: {generate_embeddings}")

        # Validar que file_content no sea None o vacío
        if not file_content:
            logger.error("file_content es None o vacío")
            return {
                'success': False,
                'error': 'file_content es requerido pero no fue proporcionado'
            }

        # Validar filename
        if not filename:
            logger.error("filename es None o vacío")
            return {
                'success': False,
                'error': 'filename es requerido pero no fue proporcionado'
            }

        # Validar extensión del archivo
        valid_extensions = ['.csv', '.xlsx', '.xls']
        file_ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
        if file_ext not in valid_extensions:
            logger.error(f"Extensión de archivo no válida: {file_ext}")
            return {
                'success': False,
                'error': f'Tipo de archivo no soportado: {file_ext}. Use CSV o XLSX'
            }

        # Validar target_rag
        if target_rag not in ["rag1", "rag2"]:
            logger.error(f"target_rag inválido: {target_rag}")
            return {
                'success': False,
                'error': f'target_rag debe ser "rag1" o "rag2", recibido: {target_rag}'
            }

        logger.info(f"Validaciones completadas - Decodificando contenido base64")

        # Decodificar contenido base64
        try:
            file_bytes = base64.b64decode(file_content)
            file_size = len(file_bytes)
            logger.info(f"Archivo decodificado - Tamaño: {file_size} bytes ({file_size / 1024:.2f} KB)")
        except Exception as decode_error:
            logger.error(f"Error decodificando base64: {decode_error}")
            return {
                'success': False,
                'error': f'Error decodificando file_content base64: {str(decode_error)}'
            }

        # Validar tamaño del archivo
        max_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            logger.error(f"Archivo muy grande: {file_size} bytes (máx: {max_size_bytes})")
            return {
                'success': False,
                'error': f'Archivo muy grande. Máximo: {max_size_mb}MB, recibido: {file_size / 1024 / 1024:.2f}MB'
            }

        # Ejecutar pipeline de estandarización
        logger.info("Iniciando pipeline de estandarización...")

        from src.core.pipeline import StandardizationPipeline

        pipeline = StandardizationPipeline()
        result = await pipeline.process(
            file_content=file_bytes,
            filename=filename,
            file_size=file_size,
            target_rag=target_rag,
            generate_embeddings=generate_embeddings
        )

        logger.info(f"Pipeline completado exitosamente")
        logger.info(f"RAG seleccionado: {result.selected_rag.upper()}")
        logger.info(f"Registros procesados: {len(result.result['data'])}")
        logger.info(f"Confidence Score: {result.result['confidence_score']:.2f}")
        logger.info(f"Tiempo de procesamiento: {result.processing_time_seconds}s")

        return {
            'success': True,
            'result': result.model_dump()
        }

    except Exception as e:
        logger.error(f"Error en standardize_tool: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
