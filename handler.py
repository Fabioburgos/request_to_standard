# handler.py (MCP WRAPPER)

import json
import logging
import asyncio
from src.tools.standardize_tool import invoke_standardize_tool, get_tool_definition

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Handler MCP para invocación directa desde Lambda

    El orquestador invoca esta Lambda usando JSON-RPC 2.0 con:
    - method: "tools/list" o "tools/call"
    - params: argumentos de la tool
    - id: identificador del mensaje

    Configuración en orquestador:
    MCP_WRAPPERS: {"request-to-standard": "dev-mcp-wrapper-request-to-standard"}
    """
    try:
        logger.info("=== MCP Wrapper Handler - Request to Standard ===")

        method = event.get('method')
        params = event.get('params', {})
        msg_id = event.get('id', 1)

        logger.info(f"Method: {method}")
        logger.info(f"Message ID: {msg_id}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(handle_method(method, params, msg_id))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32603, "message": str(e)}
        }


async def handle_method(method: str, params: dict, msg_id):
    """Maneja métodos MCP: tools/list y tools/call"""

    if method == "tools/list":
        logger.info("Listing tools")
        tool_def = get_tool_definition()
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [{
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "inputSchema": tool_def.inputSchema
                }]
            }
        }

    elif method == "tools/call":
        logger.info("Calling tool")
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        if tool_name != "standardize_data":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            }

        try:
            # Extraer argumentos
            file_content = arguments.get('file_content')
            filename = arguments.get('filename')
            target_rag = arguments.get('target_rag')
            generate_embeddings = arguments.get('generate_embeddings', True)  # Default: True
            save_to_knowledge_base = arguments.get('save_to_knowledge_base', True)

            logger.info(f"Argumentos recibidos:")
            logger.info(f"  - filename: {filename}")
            logger.info(f"  - target_rag: {target_rag}")
            logger.info(f"  - generate_embeddings: {generate_embeddings}")
            logger.info(f"  - save_to_knowledge_base: {save_to_knowledge_base}")
            logger.info(f"  - file_content: {len(file_content) if file_content else 0} caracteres base64")

            # Invocar la tool
            result = await invoke_standardize_tool(
                file_content = file_content,
                filename = filename,
                target_rag = target_rag,
                generate_embeddings = generate_embeddings,
                save_to_knowledge_base = save_to_knowledge_base
            )

            # Formatear respuesta según resultado
            if result["success"]:
                data = result["result"]

                # Extraer estadísticas
                records_count = len(data['result']['data'])
                confidence_score = data['result']['confidence_score']
                processing_time = data.get('processing_time_seconds', 0)
                selected_rag = data['selected_rag'].upper()

                # Información de imágenes (si aplica)
                image_info = ""
                if target_rag == "rag1" and filename.lower().endswith(('.xlsx', '.xls')):
                    image_info = "\n5. Análisis de imágenes con Azure OpenAI Vision (si hay imágenes embebidas)"

                # Información de guardado en PostgreSQL
                storage_info = data['result']['metadata'].get('storage')
                db_status = ""
                if storage_info:
                    if storage_info.get('saved', 0) > 0:
                        db_status = f"\n\nBASE DE CONOCIMIENTO (PostgreSQL):\n"
                        db_status += f"Tabla: {storage_info.get('table', 'N/A')}\n"
                        db_status += f"Registros guardados: {storage_info['saved']}/{storage_info['total_records']}"
                        if storage_info.get('failed', 0) > 0:
                            db_status += f"\nFallos: {storage_info['failed']}"
                    elif storage_info.get('error'):
                        db_status = f"\n\nError guardando en PostgreSQL: {storage_info['error']}"
                else:
                    db_status = "\n\nDatos estandarizados (no guardados en DB)"

                text_response = (
                    f"DATOS ESTANDARIZADOS EXITOSAMENTE\n\n"
                    f"Archivo: {filename}\n"
                    f"Formato: {selected_rag}\n"
                    f"Registros procesados: {records_count}\n"
                    f"Confidence Score: {confidence_score:.2f}\n"
                    f"Tiempo de procesamiento: {processing_time}s\n\n"
                    f"Pipeline ejecutado (7 pasos):\n"
                    f"1. Ingesta de datos + extracción de imágenes\n"
                    f"2. Limpieza de datos\n"
                    f"3. Identificación de columnas relevantes\n"
                    f"4. Normalización de estructura{image_info}\n"
                    f"6. Validación y cálculo de umbral\n"
                    f"7. Guardado en base de conocimiento (PostgreSQL){db_status}"
                )
            else:
                error_msg = result.get('error', 'Error desconocido')
                text_response = f"ERROR: {error_msg}"
                logger.error(f"Error en tool execution: {error_msg}")

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": text_response}]}
            }

        except Exception as e:
            logger.error(f"Error ejecutando tool: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Tool execution failed: {str(e)}"}
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }