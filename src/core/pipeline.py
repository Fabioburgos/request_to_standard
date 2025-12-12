"""
Pipeline Principal de Estandarización - MULTI-TENANT VERSION
Orquesta todos los pasos del diagrama de flujo con soporte multi-tenant
"""
import time
import os
from src.core.cleaning import DataCleaning
from src.core.ingestion import DataIngestion
from src.models.request_models import FileInfo
from src.core.validation import DataValidation
from src.utils.file_handlers import FileHandler
from src.core.normalization import DataNormalization
from typing import Union, BinaryIO, Literal
from src.core.standardization import DataStandardization
from src.models.response_models import StandardizationResponse
from src.storage.postgres_storage import PostgreSQLStorage
from src.utils.json_utils import clean_for_json
from custom_logging import get_logger

logger = get_logger(__name__)


class StandardizationPipeline:
    """Pipeline simplificado de estandarización de datos - MULTI-TENANT"""

    def __init__(self):
        self.ingestion = DataIngestion()
        self.cleaning = DataCleaning()
        self.normalization = DataNormalization()
        self.standardization = DataStandardization()
        self.validation = DataValidation()
        self.file_handler = FileHandler()

    async def process(
        self,
        client_id: str,  # ← NUEVO: Parámetro client_id
        file_content: Union[bytes, BinaryIO],
        filename: str,
        file_size: int,
        target_rag: Literal["rag1", "rag2"],
        generate_embeddings: bool = False,
        save_to_db: bool = True
    ) -> StandardizationResponse:
        """
        Ejecuta pipeline completo de estandarización + guardado en PostgreSQL - MULTI-TENANT

        Args:
            client_id: ID del cliente para schema isolation (NUEVO)
            file_content: Contenido del archivo
            filename: Nombre del archivo
            file_size: Tamaño del archivo en bytes
            target_rag: RAG objetivo ("rag1" o "rag2")
            generate_embeddings: Generar embeddings
            save_to_db: Guardar en base de conocimiento PostgreSQL (default: True)

        Returns:
            StandardizationResponse con datos estandarizados
        """
        start_time = time.time()
        logger.info(f"=== Pipeline Multi-Tenant Iniciado ===")
        logger.info(f"Cliente: {client_id}")  # ← NUEVO: Log del cliente
        logger.info(f"Archivo: {filename} ({file_size} bytes)")
        logger.info(f"Target RAG: {target_rag.upper()}")

        try:
            # STEP 1: Ingesta de Datos Cliente (y extracción de imágenes)
            logger.info("STEP 1: Iniciando ingesta de datos")
            df_raw, images_by_row = await self.ingestion.ingest(file_content, filename)
            logger.info(f"STEP 1: Ingesta completada - {len(df_raw)} filas, {len(df_raw.columns)} columnas")
            if images_by_row:
                logger.info(f"STEP 1: Extraídas imágenes para {len(images_by_row)} filas")

            # Obtener info del archivo
            file_info = FileInfo(
                **self.file_handler.get_file_info(df_raw, filename, file_size)
            )

            # STEP 2: Limpieza de Datos
            logger.info("STEP 2: Iniciando limpieza de datos")
            df_clean = await self.cleaning.clean(df_raw)
            logger.info("STEP 2: Limpieza completada")

            # STEP 3: Identificación de columnas relevantes (ANTES de normalización)
            logger.info(f"STEP 3: Identificando columnas relevantes para {target_rag.upper()}")
            column_mapping = self._generate_column_mapping(df_clean, target_rag)
            logger.info(f"STEP 3: Mapeo generado - {len(column_mapping)} columnas relevantes identificadas")

            # Filtrar DataFrame para solo incluir columnas relevantes
            relevant_columns = list(column_mapping.keys())
            df_filtered = df_clean[relevant_columns].copy()
            logger.info(f"STEP 3: DataFrame filtrado - {len(df_filtered.columns)} columnas (ignorando {len(df_clean.columns) - len(df_filtered.columns)} columnas irrelevantes)")

            # STEP 4: Normalización SOLO de columnas relevantes
            logger.info("STEP 4: Iniciando normalización de columnas relevantes")
            df_normalized = await self.normalization.normalize(df_filtered, column_mapping, target_rag)

            # Actualizar column_mapping con nombres normalizados
            normalized_mapping = {}
            for orig_col, target_field in column_mapping.items():
                normalized_col = orig_col.lower().strip().replace(' ', '_').replace('-', '_')
                normalized_mapping[normalized_col] = target_field
            column_mapping = normalized_mapping

            logger.info("STEP 4: Normalización completada")

            # STEP 5: ESTANDARIZACIÓN (5.1, 5.2, 5.3, 5.4 con análisis de imágenes)
            logger.info(f"STEP 5: Iniciando estandarización a formato {target_rag.upper()}")
            standardized_records = await self.standardization.standardize(
                df_normalized,
                target_rag,
                column_mapping,
                generate_embeddings,
                images_by_row  # Pasar imágenes para análisis
            )
            logger.info(f"STEP 5: Estandarización completada - {len(standardized_records)} registros")

            # STEP 6: Validación de Data y Obtención de Umbral
            logger.info("STEP 6: Iniciando validación y cálculo de umbral")
            validation_result = self.validation.validate_structure(
                standardized_records,
                target_rag
            )
            logger.info(f"STEP 6: Validación completada - Confianza: {validation_result.get('confidence_score', 0):.2f}")

            # Calcular score de calidad
            quality_score = self.validation.calculate_quality_score(validation_result)

            # Limpiar datos para JSON (timestamps, NaN, etc.) ANTES de Pydantic
            standardized_records_clean = clean_for_json(standardized_records)

            # ================================================================
            # STEP 7: Guardar en PostgreSQL - MULTI-TENANT
            # ================================================================
            storage_result = None
            if save_to_db:
                logger.info("STEP 7: Guardando en base de conocimiento (PostgreSQL)")
                logger.info(f"[MULTI-TENANT] Usando client_id: {client_id}")
                logger.info(f"[MULTI-TENANT] Schema PostgreSQL: kb_{client_id}")
                
                try:
                    # ============================================================
                    # CAMBIO CRÍTICO: Usar client_id del parámetro (NO env var)
                    # ============================================================
                    storage = PostgreSQLStorage(client_id=client_id)  # ← CAMBIO AQUÍ
                    storage_result = await storage.save_to_knowledge_base(
                        records = standardized_records_clean,
                        rag_type = target_rag
                    )

                    logger.info(f"STEP 7: Guardado completado - {storage_result['saved']}/{storage_result['total_records']} registros en '{storage_result['table']}'")
                    logger.info(f"[MULTI-TENANT] Schema: kb_{client_id}, Tabla: {storage_result['table']}")

                    # Cerrar conexión
                    await storage.close()

                except Exception as storage_error:
                    logger.error(f"Error guardando en PostgreSQL: {str(storage_error)}", exc_info=True)
                    logger.error(f"[MULTI-TENANT] Cliente afectado: {client_id}")
                    # No fallar el pipeline completo si falla el guardado
                    storage_result = {
                        "error": str(storage_error),
                        "saved": 0,
                        "failed": len(standardized_records_clean),
                        "client_id": client_id  # ← NUEVO: Incluir en error
                    }
            else:
                logger.info("STEP 7: Saltado (save_to_db=False)")
            
            column_mapping_clean = clean_for_json(column_mapping)
            validation_result_clean = clean_for_json(validation_result)

            # Construir respuesta según RAG (sin validación Pydantic estricta)
            if target_rag == "rag1":
                result = {
                    "format": "rag1_standard",
                    "data": standardized_records_clean,
                    "metadata": {
                        "client_id": client_id,  # ← NUEVO: Info del cliente
                        "schema": f"kb_{client_id}",  # ← NUEVO: Info del schema
                        "column_mapping": column_mapping_clean,
                        "validation": validation_result_clean,
                        "storage": storage_result  # Info del guardado en PostgreSQL
                    },
                    "confidence_score": quality_score
                }
            else:
                result = {
                    "format": "rag2_standard",
                    "data": standardized_records_clean,
                    "metadata": {
                        "client_id": client_id,  # ← NUEVO: Info del cliente
                        "schema": f"kb_{client_id}",  # ← NUEVO: Info del schema
                        "column_mapping": column_mapping_clean,
                        "validation": validation_result_clean,
                        "storage": storage_result  # Info del guardado en PostgreSQL
                    },
                    "confidence_score": quality_score
                }

            # Tiempo de procesamiento
            processing_time = time.time() - start_time

            # Construir respuesta final
            response = StandardizationResponse(
                success = validation_result["is_valid"],
                message = f"Datos estandarizados exitosamente a formato {target_rag.upper()}",
                selected_rag = target_rag,
                file_info = file_info,
                result = result,
                processing_time_seconds = round(processing_time, 2)
            )

            logger.info(f"Pipeline completado exitosamente en {processing_time:.2f}s")
            logger.info(f"Cliente: {client_id}, RAG: {target_rag.upper()}, Registros: {len(standardized_records)}")
            return response

        except Exception as e:
            # En caso de error, retornar respuesta de error
            processing_time = time.time() - start_time
            logger.error(f"Error en pipeline después de {processing_time:.2f}s: {str(e)}", exc_info=True)
            logger.error(f"[MULTI-TENANT] Cliente afectado: {client_id}")

            # Para mantener la estructura, crear respuesta mínima
            raise Exception(f"Error en pipeline para cliente {client_id}: {str(e)}")

    def _generate_column_mapping(self, df, target_rag: str) -> dict:
        """
        Genera mapeo inteligente de columnas según el RAG objetivo

        Detecta columnas con contenido descriptivo/textual largo y las mapea apropiadamente

        Args:
            df: DataFrame normalizado
            target_rag: RAG objetivo

        Returns:
            Dict con mapeo de columnas
        """
        columns = list(df.columns)
        mapping = {}

        if target_rag == "rag1":
            # Mapeo para RAG1
            mapping_rules = {
                # Identificadores
                'articulo': 'articulo_id',
                'article': 'articulo_id',
                'doc_ref': 'articulo_id',
                'doc_id': 'articulo_id',
                'id': 'articulo_id',
                'ref': 'articulo_id',

                # Tipo/Categoría
                'tipo': 'tipo',
                'type': 'tipo',
                'category': 'tipo',
                'categoria': 'tipo',

                # Número/Sección
                'numero': 'numero',
                'num': 'numero',
                'section': 'numero',
                'seccion': 'numero',

                # Título/Header
                'titulo': 'titulo',
                'title': 'titulo',
                'header': 'titulo',
                'encabezado': 'titulo',
                'name': 'titulo',
                'nombre': 'titulo',

                # Texto/Contenido (PRIORIDAD: body_content, texto largo)
                'body_content': 'texto',
                'body': 'texto',
                'content': 'texto',
                'texto': 'texto',
                'text': 'texto',
                'contenido': 'texto',
                'descripcion': 'texto',
                'description': 'texto',
                'detalle': 'texto',
                'detail': 'texto',

                # Keywords/Tags
                'keywords': 'keywords',
                'tags': 'keywords',
                'palabras_clave': 'keywords',
                'etiquetas': 'keywords',

                # Image Caption
                'image_caption': 'image_caption',
                'fig_desc': 'image_caption',
                'caption': 'image_caption',
                'figura': 'image_caption'
            }
        else:
            # Mapeo para RAG2
            mapping_rules = {
                # Descripción (PRIORIDAD: body_content, description, texto largo)
                'body_content': 'descripcion',
                'body': 'descripcion',
                'descripcion': 'descripcion',
                'description': 'descripcion',
                'texto': 'descripcion',
                'text': 'descripcion',
                'contenido': 'descripcion',
                'detalle': 'descripcion',
                'detail': 'descripcion',

                # Tipo
                'tipo': 'tipo',
                'type': 'tipo',
                'category': 'tipo',
                'categoria': 'tipo',

                # Servicio
                'servicio': 'servicio',
                'service': 'servicio',

                # Categoría
                'categoria': 'categoria',
                'category': 'categoria',

                # Subcategoría
                'subcategoria': 'subcategoria',
                'subcategory': 'subcategoria',

                # Fuente
                'fuente': 'fuente',
                'source': 'fuente',
                'origen': 'fuente'
            }

        # Mapear columnas según reglas
        for col in columns:
            col_lower = col.lower()
            for source_key, target_field in mapping_rules.items():
                if source_key in col_lower:
                    mapping[col] = target_field
                    break

        # Validación: Asegurar que columnas de descripción/texto SIEMPRE se mapeen
        # Buscar columnas con texto largo que no se hayan mapeado
        for col in columns:
            if col not in mapping:
                # Revisar si tiene contenido textual significativo
                try:
                    sample_values = df[col].dropna().head(3)
                    if len(sample_values) > 0:
                        avg_length = sample_values.astype(str).str.len().mean()
                        # Si el promedio es > 50 caracteres, probablemente es texto descriptivo
                        if avg_length > 50:
                            if target_rag == "rag1" and 'texto' not in mapping.values():
                                mapping[col] = 'texto'
                                logger.info(f"Auto-mapeado columna '{col}' a 'texto' (longitud promedio: {avg_length:.0f})")
                            elif target_rag == "rag2" and 'descripcion' not in mapping.values():
                                mapping[col] = 'descripcion'
                                logger.info(f"Auto-mapeado columna '{col}' a 'descripcion' (longitud promedio: {avg_length:.0f})")
                except Exception as e:
                    # Si falla la detección, continuar
                    pass

        return mapping
