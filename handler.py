"""
AWS Lambda Handler - Request to Standard
Maneja eventos de AWS Lambda (API Gateway, S3, etc.)

Desplegar con:
    - AWS SAM
    - Serverless Framework
    - AWS CDK
"""
import json
import boto3
import asyncio
from main import app
from mangum import Mangum
from typing import Any, Dict
from custom_logging import get_logger
from src.core.pipeline import StandardizationPipeline

logger = get_logger(__name__)

# Adapter Mangum para convertir FastAPI a Lambda handler
lambda_handler = Mangum(app, lifespan="off")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler principal

    Soporta:
    - API Gateway events (HTTP API, REST API)
    - S3 events (para procesar archivos subidos a S3)
    - EventBridge events

    Args:
        event: Evento de Lambda
        context: Contexto de Lambda

    Returns:
        Response formateado para Lambda
    """
    # Detectar tipo de evento
    event_source = detect_event_source(event)

    if event_source == "s3":
        return handle_s3_event(event, context)
    elif event_source in ["api_gateway", "alb"]:
        # Usar Mangum para eventos HTTP
        return lambda_handler(event, context)
    else:
        # Evento no soportado
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Tipo de evento no soportado",
                "event_source": event_source
            })
        }


def detect_event_source(event: Dict[str, Any]) -> str:
    """
    Detecta la fuente del evento

    Returns:
        Tipo de evento: 's3', 'api_gateway', 'alb', 'unknown'
    """
    if "Records" in event and len(event["Records"]) > 0:
        record = event["Records"][0]
        if "s3" in record:
            return "s3"

    if "requestContext" in event:
        if "elb" in event["requestContext"]:
            return "alb"
        return "api_gateway"

    if "version" in event and "routeKey" in event:
        return "api_gateway"

    return "unknown"


def handle_s3_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Procesa evento de S3

    Cuando se sube un archivo CSV/XLSX a S3, procesar automáticamente

    Args:
        event: S3 event
        context: Lambda context

    Returns:
        Response con resultado del procesamiento
    """
    try:
        # Obtener información del archivo S3
        s3 = boto3.client('s3')
        record = event["Records"][0]["s3"]
        bucket = record["bucket"]["name"]
        key = record["object"]["key"]

        # Descargar archivo de S3
        response = s3.get_object(Bucket=bucket, Key=key)
        file_content = response["Body"].read()
        file_size = response["ContentLength"]

        # Obtener nombre del archivo
        filename = key.split('/')[-1]

        # Procesar con pipeline
        pipeline = StandardizationPipeline()

        # Ejecutar pipeline de forma síncrona en Lambda
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            pipeline.process(
                file_content=file_content,
                filename=filename,
                file_size=file_size
            )
        )
        loop.close()

        # Guardar resultado en S3 (opcional)
        output_key = f"standardized/{filename.rsplit('.', 1)[0]}_standardized.json"
        s3.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=json.dumps(result.model_dump(), indent=2),
            ContentType="application/json"
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Archivo procesado exitosamente",
                "input": f"s3://{bucket}/{key}",
                "output": f"s3://{bucket}/{output_key}",
                "result_summary": {
                    "selected_rag": result.selected_rag,
                    "records_count": len(result.result.data),
                    "confidence_score": result.result.confidence_score
                }
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Error procesando archivo S3: {str(e)}"
            })
        }


# Para testing local
if __name__ == "__main__":
    # Ejemplo de evento API Gateway para testing
    test_event = {
        "version": "2.0",
        "routeKey": "GET /health",
        "rawPath": "/health",
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/health"
            }
        },
        "headers": {},
        "isBase64Encoded": False
    }

    result = handler(test_event, None)
    logger.info(json.dumps(result, indent=2))