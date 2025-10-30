"""
Utilidades para muestreo de datos
Necesario para análisis con LLM sin enviar datasets completos
"""
import pandas as pd

class DataSampler:
    """Herramientas para muestreo de datos"""

    @staticmethod
    def get_representative_sample(df: pd.DataFrame, sample_size: int = 100) -> pd.DataFrame:
        """
        Obtiene una muestra representativa del DataFrame

        Args:
            df: DataFrame completo
            sample_size: Número de filas a muestrear

        Returns:
            DataFrame con muestra representativa
        """
        if len(df) <= sample_size:
            return df.copy()

        # Tomar muestra estratificada si es posible
        # Para PoC: muestra aleatoria simple
        return df.sample(n=min(sample_size, len(df)), random_state=42)

    @staticmethod
    def get_column_sample(df: pd.DataFrame, max_rows: int = 5) -> dict:
        """
        Obtiene una muestra de cada columna para análisis LLM

        Args:
            df: DataFrame
            max_rows: Número máximo de ejemplos por columna

        Returns:
            Dict con nombre de columna y ejemplos
        """
        sample = {}
        for col in df.columns:
            # Tomar valores no nulos únicos
            unique_values = df[col].dropna().unique()
            sample[col] = {
                "type": str(df[col].dtype),
                "examples": [str(v) for v in unique_values[:max_rows]],
                "null_count": int(df[col].isna().sum()),
                "total_count": len(df)
            }
        return sample

    @staticmethod
    def get_data_summary(df: pd.DataFrame) -> dict:
        """
        Genera un resumen del dataset para análisis

        Args:
            df: DataFrame

        Returns:
            Dict con resumen estadístico
        """
        return {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "null_counts": df.isnull().sum().to_dict(),
            "sample_data": df.head(3).to_dict(orient='records')
        }