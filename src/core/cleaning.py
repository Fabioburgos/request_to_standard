"""
Step 2: Limpieza de Datos
Preprocesamiento:
- Eliminación espacios
- Corrección encoding
- Remoción caracteres especiales
- Normalización formato
"""
import re
import pandas as pd
from typing import Optional


class DataCleaning:
    """Limpieza y preprocesamiento de datos"""

    @staticmethod
    def clean_whitespace(df: pd.DataFrame) -> pd.DataFrame:
        """Elimina espacios en blanco innecesarios"""
        df_clean = df.copy()

        # Limpiar nombres de columnas
        df_clean.columns = df_clean.columns.str.strip()

        # Limpiar valores de texto
        for col in df_clean.select_dtypes(include=['object']).columns:
            df_clean[col] = df_clean[col].apply(
                lambda x: x.strip() if isinstance(x, str) else x
            )

        return df_clean

    @staticmethod
    def remove_special_characters(
        df: pd.DataFrame,
        keep_basic_punctuation: bool = True
    ) -> pd.DataFrame:
        """
        Remueve caracteres especiales problemáticos

        Args:
            df: DataFrame
            keep_basic_punctuation: Mantener puntuación básica (.,;:-_)

        Returns:
            DataFrame limpio
        """
        df_clean = df.copy()

        if keep_basic_punctuation:
            # Patrón que mantiene letras, números, espacios y puntuación básica
            pattern = r'[^\w\s.,;:\-_áéíóúñÁÉÍÓÚÑ]'
        else:
            pattern = r'[^\w\s]'

        for col in df_clean.select_dtypes(include=['object']).columns:
            df_clean[col] = df_clean[col].apply(
                lambda x: re.sub(pattern, '', str(x)) if pd.notna(x) else x
            )

        return df_clean

    @staticmethod
    def normalize_encoding(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza encoding de caracteres"""
        df_clean = df.copy()

        for col in df_clean.select_dtypes(include=['object']).columns:
            df_clean[col] = df_clean[col].apply(
                lambda x: x.encode('utf-8', errors='ignore').decode('utf-8')
                if isinstance(x, str) else x
            )

        return df_clean

    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame,
        strategy: str = "keep"
    ) -> pd.DataFrame:
        """
        Maneja valores faltantes

        Args:
            df: DataFrame
            strategy: 'keep', 'drop', 'fill_empty'

        Returns:
            DataFrame procesado
        """
        df_clean = df.copy()

        if strategy == "drop":
            df_clean = df_clean.dropna()
        elif strategy == "fill_empty":
            df_clean = df_clean.fillna("")

        return df_clean

    async def clean(
        self,
        df: pd.DataFrame,
        remove_special_chars: bool = True,
        missing_value_strategy: str = "keep"
    ) -> pd.DataFrame:
        """
        Pipeline completo de limpieza

        Args:
            df: DataFrame crudo
            remove_special_chars: Si remover caracteres especiales
            missing_value_strategy: Estrategia para valores faltantes

        Returns:
            DataFrame limpio
        """
        # 1. Limpiar espacios
        df_clean = self.clean_whitespace(df)

        # 2. Normalizar encoding
        df_clean = self.normalize_encoding(df_clean)

        # 3. Remover caracteres especiales
        if remove_special_chars:
            df_clean = self.remove_special_characters(df_clean)

        # 4. Manejar valores faltantes
        df_clean = self.handle_missing_values(df_clean, missing_value_strategy)

        return df_clean