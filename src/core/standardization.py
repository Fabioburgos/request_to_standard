"""
Step 5: ESTANDARIZACIÓN
5.1 Conceptualización de Estándar
5.2 Traducción de Data Cliente → Estándar
5.3 Generación de Estándar
"""
import json
import uuid
import pandas as pd
from typing import Dict, Any, List, Literal
from src.gpt.prompts import PromptTemplates
from src.gpt.client import AzureOpenAIClient
from src.models.rag1_schema import RAG1Schema
from src.models.rag2_schema import RAG2Schema
from custom_logging import get_logger

logger = get_logger(__name__)


class DataStandardization:
    """Estandariza datos al formato RAG seleccionado"""

    def __init__(self):
        self.llm_client = AzureOpenAIClient()
        self.prompts = PromptTemplates()

    async def standardize(
        self,
        df: pd.DataFrame,
        target_rag: Literal["rag1", "rag2"],
        column_mapping: Dict[str, str],
        generate_embeddings: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Pipeline completo de estandarización

        Args:
            df: DataFrame normalizado
            target_rag: RAG objetivo (rag1 o rag2)
            column_mapping: Mapeo de columnas
            generate_embeddings: Si generar embeddings

        Returns:
            Lista de registros estandarizados
        """
        logger.info(f"Estandarizando {len(df)} registros al formato {target_rag.upper()}")

        # Convertir TODAS las filas del DataFrame a dict
        # (LLM solo analiza 10, pero procesamos todas)
        data_dict = df.to_dict(orient='records')

        # Step 5.1 y 5.2: Conceptualización y Traducción con LLM
        standardized_records = await self._transform_with_llm(
            data_dict,
            target_rag,
            column_mapping
        )

        # Step 5.3: Generar registros estandarizados
        validated_records = []
        for record in standardized_records:
            try:
                if target_rag == "rag1":
                    validated = self._create_rag1_record(record, generate_embeddings)
                else:
                    validated = self._create_rag2_record(record, generate_embeddings)

                validated_records.append(validated)
            except Exception as e:
                # Log error pero continuar
                logger.error(f"Error procesando registro: {e}", exc_info=True)
                continue

        return validated_records

    async def _transform_with_llm(
        self,
        data_records: List[Dict],
        target_rag: str,
        column_mapping: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Transforma datos usando LLM para analizar contexto

        Flujo:
        1. LLM analiza 10 filas de muestra → Devuelve REGLAS de transformación
        2. Aplicamos esas reglas a TODAS las filas (con UUID generado por nosotros)

        Args:
            data_records: TODOS los registros a transformar
            target_rag: RAG objetivo
            column_mapping: Mapeo de columnas

        Returns:
            TODOS los registros transformados
        """
        import time
        start_time = time.time()

        logger.info(f"Iniciando transformación con LLM para {len(data_records)} registros ({target_rag.upper()})")

        # 1. Tomar muestra significativa para el LLM (primeros 10 registros)
        sample = data_records[:10]
        logger.info(f"Muestra de {len(sample)} registros seleccionada")

        # Limpiar sample para JSON (remover Timestamps, NaN, etc.)
        from src.utils.json_utils import clean_for_json
        sample_clean = clean_for_json(sample)

        # 2. Generar prompt que pide REGLAS, no registros transformados
        prompt = self.prompts.standardization_prompt(
            sample_clean,
            target_rag,
            column_mapping
        )

        # 3. Llamar al LLM para obtener reglas
        messages = [
            {
                "role": "system",
                "content": f"Eres un experto en análisis de datos. Analizas muestras y generas reglas de transformación al formato {target_rag.upper()}. Respondes siempre en formato JSON válido."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        logger.info(f"Enviando petición al LLM...")
        llm_start = time.time()
        response = await self.llm_client.chat_completion(messages, temperature=0.1)
        llm_duration = time.time() - llm_start
        logger.info(f"LLM respondió en {llm_duration:.2f}s")

        # 4. Parsear reglas de transformación
        try:
            result = json.loads(response)
            transformation_rules = result.get("reglas_transformacion", {})

            logger.info(f"Reglas de transformación obtenidas del LLM: {len(transformation_rules)} campos")

            # 5. Aplicar reglas a TODAS las filas (no solo muestra)
            logger.info(f"Aplicando reglas a {len(data_records)} registros...")
            apply_start = time.time()
            all_transformed = self._apply_transformation_rules(
                data_records,  # TODAS las filas
                transformation_rules,
                column_mapping,
                target_rag
            )
            apply_duration = time.time() - apply_start
            logger.info(f"Reglas aplicadas en {apply_duration:.2f}s")

            total_duration = time.time() - start_time
            logger.info(f"Transformación completa en {total_duration:.2f}s (LLM: {llm_duration:.2f}s, Aplicación: {apply_duration:.2f}s)")

            return all_transformed

        except json.JSONDecodeError as e:
            logger.warning(f"Error parseando reglas del LLM: {e}. Usando mapeo directo fallback.")
            # Fallback: mapeo directo para todas las filas
            return self._apply_direct_mapping(data_records, column_mapping, target_rag)

    def _apply_transformation_rules(
        self,
        data_records: List[Dict],
        transformation_rules: Dict[str, Any],
        column_mapping: Dict[str, str],
        target_rag: str
    ) -> List[Dict[str, Any]]:
        """
        Aplica reglas de transformación del LLM a TODAS las filas

        Args:
            data_records: TODOS los registros
            transformation_rules: Reglas generadas por el LLM
            column_mapping: Mapeo de columnas
            target_rag: RAG objetivo

        Returns:
            TODOS los registros transformados con UUID
        """
        transformed = []

        for idx, record in enumerate(data_records):
            # Generar UUID único para cada registro
            record_id = self._generate_id()

            if target_rag == "rag1":
                new_record = self._apply_rules_to_rag1(
                    record,
                    transformation_rules,
                    column_mapping,
                    record_id
                )
            else:
                new_record = self._apply_rules_to_rag2(
                    record,
                    transformation_rules,
                    column_mapping,
                    record_id
                )

            transformed.append(new_record)

        return transformed

    def _apply_rules_to_rag1(
        self,
        record: Dict,
        rules: Dict[str, Any],
        column_mapping: Dict[str, str],
        record_id: str
    ) -> Dict[str, Any]:
        """Aplica reglas de transformación a un registro RAG1"""
        transformed = {"id": record_id}

        # Campos del schema RAG1
        rag1_fields = ["articulo_id", "tipo", "numero", "titulo", "texto", "image_caption", "keywords"]

        for field in rag1_fields:
            if field in rules:
                rule = rules[field]
                columna_origen = rule.get("columna_origen")
                transformacion = rule.get("transformacion", "copiar_tal_cual")
                valor_por_defecto = rule.get("valor_por_defecto")

                # Obtener valor de la columna origen
                valor = record.get(columna_origen) if columna_origen else None

                # Aplicar transformación según la regla
                transformed[field] = self._apply_transformation(
                    valor,
                    transformacion,
                    valor_por_defecto,
                    field
                )
            else:
                # Fallback: usar mapeo directo
                transformed[field] = self._safe_get(record, column_mapping, field, self._get_default_value(field, "rag1"))

        transformed["embedding"] = None
        return transformed

    def _apply_rules_to_rag2(
        self,
        record: Dict,
        rules: Dict[str, Any],
        column_mapping: Dict[str, str],
        record_id: str
    ) -> Dict[str, Any]:
        """Aplica reglas de transformación a un registro RAG2"""
        transformed = {"id": record_id}

        # Campos del schema RAG2
        rag2_fields = ["descripcion", "tipo", "servicio", "categoria", "subcategoria", "fuente"]

        for field in rag2_fields:
            if field in rules:
                rule = rules[field]
                columna_origen = rule.get("columna_origen")
                transformacion = rule.get("transformacion", "copiar_tal_cual")
                valor_por_defecto = rule.get("valor_por_defecto")

                valor = record.get(columna_origen) if columna_origen else None

                transformed[field] = self._apply_transformation(
                    valor,
                    transformacion,
                    valor_por_defecto,
                    field
                )
            else:
                # Fallback: usar mapeo directo
                transformed[field] = self._safe_get(record, column_mapping, field, self._get_default_value(field, "rag2"))

        transformed["embedding"] = None
        return transformed

    def _apply_transformation(
        self,
        valor: Any,
        transformacion: str,
        valor_por_defecto: Any,
        field_name: str
    ) -> Any:
        """Aplica una transformación específica a un valor"""
        # Si el valor es None o vacío, usar valor por defecto
        if pd.isna(valor) or valor == "" or valor is None:
            return valor_por_defecto

        # Aplicar transformación según el tipo
        if transformacion == "copiar_tal_cual":
            return str(valor) if valor is not None else valor_por_defecto

        elif transformacion == "copiar_completo_sin_resumir":
            # Para campos de texto largo, preservar contenido completo
            return str(valor) if valor is not None else valor_por_defecto

        elif transformacion == "copiar_si_existe_sino_null":
            return str(valor) if valor else None

        elif transformacion == "convertir_a_entero":
            try:
                return int(valor)
            except (ValueError, TypeError):
                return valor_por_defecto if valor_por_defecto is not None else 0

        elif transformacion == "separar_por_punto_coma_unir_con_coma":
            # Transformar "tag1;tag2;tag3" → "tag1, tag2, tag3"
            if isinstance(valor, str):
                if ";" in valor:
                    return ", ".join([tag.strip() for tag in valor.split(";")])
                elif "," in valor:
                    return ", ".join([tag.strip() for tag in valor.split(",")])
            return str(valor) if valor else valor_por_defecto

        else:
            # Transformación desconocida, copiar tal cual
            return str(valor) if valor is not None else valor_por_defecto

    def _get_default_value(self, field: str, target_rag: str) -> Any:
        """Obtiene el valor por defecto para un campo"""
        defaults = {
            "rag1": {
                "articulo_id": "ART-0000",
                "tipo": "General",
                "numero": 0,
                "titulo": "Sin título",
                "texto": "",
                "image_caption": None,
                "keywords": None
            },
            "rag2": {
                "descripcion": "",
                "tipo": "General",
                "servicio": "Sin especificar",
                "categoria": "General",
                "subcategoria": "General",
                "fuente": "csv"
            }
        }
        return defaults.get(target_rag, {}).get(field)

    def _apply_direct_mapping(
        self,
        data_records: List[Dict],
        column_mapping: Dict[str, str],
        target_rag: str
    ) -> List[Dict[str, Any]]:
        """Aplica mapeo directo de columnas sin LLM (fallback)"""
        transformed = []

        for idx, record in enumerate(data_records):
            if target_rag == "rag1":
                new_record = self._map_to_rag1(record, column_mapping, idx)
            else:
                new_record = self._map_to_rag2(record, column_mapping, idx)

            transformed.append(new_record)

        return transformed

    def _map_to_rag1(
        self,
        record: Dict,
        mapping: Dict[str, str],
        index: int
    ) -> Dict[str, Any]:
        """Mapea registro a formato RAG1"""
        # Generar ID único con UUID
        record_id = self._generate_id()

        # Mapear campos
        mapped = {
            "id": record_id,
            "articulo_id": self._safe_get(record, mapping, "articulo_id", f"ART{index:04d}"),
            "tipo": self._safe_get(record, mapping, "tipo", "General"),
            "numero": self._safe_get_int(record, mapping, "numero", index),
            "titulo": self._safe_get(record, mapping, "titulo", "Sin título"),
            "texto": self._safe_get(record, mapping, "texto", ""),
            "image_caption": self._safe_get(record, mapping, "image_caption", None),
            "keywords": self._safe_get(record, mapping, "keywords", None),
            "embedding": None
        }

        return mapped

    def _map_to_rag2(
        self,
        record: Dict,
        mapping: Dict[str, str],
        index: int
    ) -> Dict[str, Any]:
        """Mapea registro a formato RAG2"""
        # Obtener descripción
        descripcion = self._safe_get(record, mapping, "descripcion", f"Registro {index}")

        mapped = {
            "id": self._generate_id(),
            "descripcion": descripcion,
            "tipo": self._safe_get(record, mapping, "tipo", "General"),
            "servicio": self._safe_get(record, mapping, "servicio", "Sin especificar"),
            "categoria": self._safe_get(record, mapping, "categoria", "General"),
            "subcategoria": self._safe_get(record, mapping, "subcategoria", "General"),
            "fuente": self._safe_get(record, mapping, "fuente", "csv"),
            "embedding": None
        }

        return mapped

    def _safe_get(
        self,
        record: Dict,
        mapping: Dict[str, str],
        field: str,
        default: Any
    ) -> Any:
        """Obtiene valor de campo mapeado de forma segura"""
        # Buscar columna original que mapea a este campo
        source_col = None
        for orig_col, dest_field in mapping.items():
            if dest_field == field:
                source_col = orig_col
                break

        if source_col and source_col in record:
            value = record[source_col]
            return value if pd.notna(value) else default

        return default

    def _safe_get_int(
        self,
        record: Dict,
        mapping: Dict[str, str],
        field: str,
        default: int
    ) -> int:
        """Obtiene valor entero de forma segura"""
        value = self._safe_get(record, mapping, field, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _generate_id(self, text: str = None, suffix: int = 0) -> str:
        """Genera ID único usando UUID"""
        return str(uuid.uuid4())

    def _create_rag1_record(
        self,
        record: Dict[str, Any],
        generate_embedding: bool
    ) -> Dict[str, Any]:
        """Crea y valida registro RAG1"""
        # Normalizar tipos para Pydantic (convertir a los tipos esperados)
        normalized_record = {
            "id": str(record.get("id", "")),
            "articulo_id": str(record.get("articulo_id", "")),
            "tipo": str(record.get("tipo", "General")),
            "numero": int(record.get("numero", 0)) if record.get("numero") is not None else 0,
            "titulo": str(record.get("titulo", "")),
            "texto": str(record.get("texto", "")),
            "image_caption": str(record.get("image_caption")) if record.get("image_caption") else None,
            "keywords": str(record.get("keywords")) if record.get("keywords") else None,
            "embedding": record.get("embedding")
        }

        # Validar con Pydantic
        rag1_obj = RAG1Schema(**normalized_record)
        return rag1_obj.model_dump()

    def _create_rag2_record(
        self,
        record: Dict[str, Any],
        generate_embedding: bool
    ) -> Dict[str, Any]:
        """Crea y valida registro RAG2"""
        # Normalizar tipos para Pydantic
        normalized_record = {
            "id": str(record.get("id", "")),
            "descripcion": str(record.get("descripcion", "")),
            "tipo": str(record.get("tipo", "General")),
            "servicio": str(record.get("servicio", "Sin especificar")),
            "categoria": str(record.get("categoria", "General")),
            "subcategoria": str(record.get("subcategoria", "General")),
            "fuente": str(record.get("fuente", "csv")),
            "embedding": record.get("embedding")
        }

        # Validar con Pydantic
        rag2_obj = RAG2Schema(**normalized_record)
        return rag2_obj.model_dump()