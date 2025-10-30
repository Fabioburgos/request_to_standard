"""
Step 1: Ingesta de Datos Cliente
Entrada: CSV, XLSX
"""
import pandas as pd
from typing import Union, BinaryIO
from src.utils.file_handlers import FileHandler


class DataIngestion:
    """Maneja la ingesta de datos desde archivos CSV/XLSX"""

    def __init__(self):
        self.file_handler = FileHandler()

    async def ingest(
        self,
        file_content: Union[bytes, BinaryIO],
        filename: str
    ) -> pd.DataFrame:
        """
        Ingesta de datos desde archivo

        Args:
            file_content: Contenido del archivo
            filename: Nombre del archivo

        Returns:
            DataFrame con los datos crudos
        """
        # Leer archivo
        df = self.file_handler.read_file(file_content, filename)

        # Validación básica
        if df.empty:
            raise ValueError("El archivo está vacío")

        if len(df.columns) == 0:
            raise ValueError("El archivo no tiene columnas")

        return df