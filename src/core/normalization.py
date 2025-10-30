"""
Step 3: Normalización de Datos
Estructuración:
- Extracción campos clave
- Tipado de datos
- Estructuración consistente
- Validación sintáctica
"""
import pandas as pd
from typing import Dict, Any


class DataNormalization:
    """Normalización y estructuración de datos"""

    @staticmethod
    def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza nombres de columnas a formato estándar

        Convierte a lowercase, reemplaza espacios por guiones bajos
        """
        df_norm = df.copy()
        df_norm.columns = [
            col.lower()
            .strip()
            .replace(' ', '_')
            .replace('-', '_')
            for col in df_norm.columns
        ]
        return df_norm

    @staticmethod
    def infer_and_convert_types(df: pd.DataFrame, column_mapping: dict, target_rag: str) -> pd.DataFrame:
        """
        Convierte tipos de datos SOLO para columnas relevantes al payload final

        IMPORTANTE: No procesa fechas ni timestamps porque los esquemas RAG1/RAG2 no los incluyen

        Args:
            df: DataFrame con columnas relevantes
            column_mapping: Mapeo de columnas origen → destino
            target_rag: RAG objetivo

        Returns:
            DataFrame con tipos normalizados para campos del payload
        """
        df_norm = df.copy()

        # Identificar qué tipo de campo es cada columna según el mapeo
        for col in df_norm.columns:
            target_field = column_mapping.get(col)

            if not target_field:
                continue

            # Solo convertir a numérico si el campo destino es 'numero' (RAG1)
            if target_field == 'numero':
                try:
                    df_norm[col] = pd.to_numeric(df_norm[col], errors='coerce').fillna(0).astype(int)
                except (ValueError, TypeError):
                    df_norm[col] = 0

            # Para todos los demás campos (texto, descripcion, titulo, etc.), mantener como string
            else:
                try:
                    df_norm[col] = df_norm[col].astype(str)
                    # Limpiar valores NaN convertidos a string "nan"
                    df_norm[col] = df_norm[col].replace('nan', '').replace('None', '')
                except (ValueError, TypeError):
                    pass

        return df_norm

    @staticmethod
    def validate_data_structure(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Valida la estructura de datos y genera reporte

        Returns:
            Dict con estadísticas de validación
        """
        validation = {
            "is_valid": True,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "column_types": {},
            "issues": []
        }

        # Validar que haya datos
        if df.empty:
            validation["is_valid"] = False
            validation["issues"].append("DataFrame está vacío")
            return validation

        # Analizar tipos de columnas
        for col in df.columns:
            validation["column_types"][col] = {
                "dtype": str(df[col].dtype),
                "null_percentage": float(df[col].isna().sum() / len(df) * 100)
            }

            # Detectar columnas con muchos nulos
            if df[col].isna().sum() / len(df) > 0.9:
                validation["issues"].append(
                    f"Columna '{col}' tiene más de 90% valores nulos"
                )

        return validation

    async def normalize(
        self,
        df: pd.DataFrame,
        column_mapping: dict,
        target_rag: str
    ) -> pd.DataFrame:
        """
        Pipeline de normalización SOLO para columnas relevantes

        IMPORTANTE: Solo procesa columnas que están en column_mapping (las que van al payload)

        Args:
            df: DataFrame filtrado con columnas relevantes
            column_mapping: Mapeo de columnas origen → destino
            target_rag: RAG objetivo

        Returns:
            DataFrame normalizado
        """
        # 1. Normalizar nombres de columnas
        df_norm = self.normalize_column_names(df)

        # 2. Actualizar column_mapping con nombres normalizados
        normalized_mapping = {}
        for orig_col, target_field in column_mapping.items():
            normalized_col = orig_col.lower().strip().replace(' ', '_').replace('-', '_')
            normalized_mapping[normalized_col] = target_field

        # 3. Inferir y convertir tipos SOLO para columnas relevantes
        df_norm = self.infer_and_convert_types(df_norm, normalized_mapping, target_rag)

        # 4. Validar estructura (solo logging, no modifica)
        validation = self.validate_data_structure(df_norm)

        if not validation["is_valid"]:
            raise ValueError(f"Validación falló: {validation['issues']}")

        return df_norm