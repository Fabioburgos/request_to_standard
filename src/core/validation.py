"""
Step 6: Validación de Data y Obtención de Umbral
Control de Calidad:
- Validación estructura
- Cálculo umbral confianza
- Verificación integridad
- Aprobación para envío
"""
from pydantic import ValidationError
from src.models.rag1_schema import RAG1Schema
from src.models.rag2_schema import RAG2Schema
from typing import List, Dict, Any, Literal, Tuple


class DataValidation:
    """Valida datos estandarizados y calcula umbral de confianza"""

    def validate(
        self,
        standardized_records: List[Dict[str, Any]],
        target_rag: Literal["rag1", "rag2"]
    ) -> Tuple[bool, float, List[str]]:
        """
        Valida registros estandarizados

        Args:
            standardized_records: Lista de registros a validar
            target_rag: Formato RAG usado

        Returns:
            Tuple: (is_valid, confidence_score, errors)
        """
        if not standardized_records:
            return False, 0.0, ["No hay registros para validar"]

        errors = []
        valid_count = 0
        total_count = len(standardized_records)

        # Validar cada registro
        for idx, record in enumerate(standardized_records):
            try:
                if target_rag == "rag1":
                    RAG1Schema(**record)
                else:
                    RAG2Schema(**record)

                valid_count += 1

            except ValidationError as e:
                errors.append(f"Registro {idx}: {str(e)}")

        # Calcular umbral de confianza
        confidence_score = valid_count / total_count if total_count > 0 else 0.0

        # Considerar válido si al menos 80% de registros son correctos
        is_valid = confidence_score >= 0.8

        return is_valid, confidence_score, errors

    def validate_structure(
        self,
        standardized_records: List[Dict[str, Any]],
        target_rag: Literal["rag1", "rag2"]
    ) -> Dict[str, Any]:
        """
        Validación detallada de estructura

        Returns:
            Dict con resultado de validación
        """
        is_valid, confidence, errors = self.validate(standardized_records, target_rag)

        # Análisis de integridad
        integrity_check = self._check_integrity(standardized_records, target_rag)

        return {
            "is_valid": is_valid,
            "confidence_score": confidence,
            "errors": errors,
            "total_records": len(standardized_records),
            "valid_records": int(len(standardized_records) * confidence),
            "integrity": integrity_check
        }

    def _check_integrity(
        self,
        records: List[Dict[str, Any]],
        target_rag: str
    ) -> Dict[str, Any]:
        """
        Verifica integridad de datos

        IMPORTANTE: Independientemente del RAG, valida que existan campos de descripción/texto

        Returns:
            Dict con métricas de integridad
        """
        if not records:
            return {"status": "empty"}

        # Verificar campos requeridos
        required_fields_rag1 = ["id", "articulo_id", "tipo", "numero", "titulo", "texto"]
        required_fields_rag2 = ["id", "descripcion", "tipo", "servicio", "categoria", "subcategoria", "fuente"]

        required_fields = required_fields_rag1 if target_rag == "rag1" else required_fields_rag2

        # Contar registros con todos los campos
        complete_records = 0
        missing_fields_count = {field: 0 for field in required_fields}

        # Validación específica para campos de descripción/texto (independiente del RAG)
        description_warnings = []
        short_description_count = 0
        empty_description_count = 0

        for record in records:
            is_complete = True
            for field in required_fields:
                if field not in record or record[field] is None or record[field] == "":
                    missing_fields_count[field] += 1
                    is_complete = False

            if is_complete:
                complete_records += 1

            # VALIDACIÓN UNIVERSAL: Verificar campo descriptivo (texto o descripcion)
            description_field = "texto" if target_rag == "rag1" else "descripcion"

            if description_field in record:
                desc_value = record[description_field]
                if desc_value is None or desc_value == "":
                    empty_description_count += 1
                elif isinstance(desc_value, str) and len(desc_value) < 20:
                    # Advertencia: descripción muy corta (menos de 20 caracteres)
                    short_description_count += 1

        # Generar advertencias si hay problemas con descripciones
        if empty_description_count > 0:
            description_warnings.append(
                f"{empty_description_count} registros tienen descripción/texto vacío"
            )

        if short_description_count > 0:
            description_warnings.append(
                f"{short_description_count} registros tienen descripción/texto muy corto (< 20 caracteres)"
            )

        completeness_rate = complete_records / len(records) if records else 0

        result = {
            "status": "good" if completeness_rate >= 0.9 else "needs_review",
            "completeness_rate": completeness_rate,
            "complete_records": complete_records,
            "total_records": len(records),
            "missing_fields": {k: v for k, v in missing_fields_count.items() if v > 0}
        }

        # Agregar advertencias de descripción si existen
        if description_warnings:
            result["description_warnings"] = description_warnings
            if completeness_rate >= 0.9:
                result["status"] = "needs_review"  # Degradar status si hay problemas de descripción

        return result

    def calculate_quality_score(
        self,
        validation_result: Dict[str, Any]
    ) -> float:
        """
        Calcula score de calidad final

        Combina:
        - Confidence score (validación de schema)
        - Completeness rate (integridad de campos)

        Returns:
            Score de calidad (0-1)
        """
        confidence = validation_result.get("confidence_score", 0.0)
        completeness = validation_result.get("integrity", {}).get("completeness_rate", 0.0)

        # Promedio ponderado: 60% confidence, 40% completeness
        quality_score = (confidence * 0.6) + (completeness * 0.4)

        return round(quality_score, 3)