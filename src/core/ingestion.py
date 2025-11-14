"""
Step 1: Ingesta de Datos Cliente
Entrada: CSV, XLSX
"""
import pandas as pd
from typing import Union, BinaryIO, Dict, List, Tuple
from src.utils.file_handlers import FileHandler
from src.utils.image_extractor import ImageExtractor
import logging

logger = logging.getLogger(__name__)


class DataIngestion:
    """Maneja la ingesta de datos desde archivos CSV/XLSX"""

    def __init__(self):
        self.file_handler = FileHandler()
        self.image_extractor = ImageExtractor()

    async def ingest(
        self,
        file_content: Union[bytes, BinaryIO],
        filename: str
    ) -> Tuple[pd.DataFrame, Dict[int, List[Dict]]]:
        """
        Ingesta de datos desde archivo y extracción de imágenes (si existen)

        Args:
            file_content: Contenido del archivo
            filename: Nombre del archivo

        Returns:
            Tupla de (DataFrame con los datos crudos, Diccionario con imágenes por fila)
            El diccionario de imágenes tiene la estructura:
            {
                row_index: [
                    {'base64': str, 'format': str, 'width': int, 'height': int},
                    ...
                ]
            }
        """
        # Leer archivo
        df = self.file_handler.read_file(file_content, filename)

        # Validación básica
        if df.empty:
            raise ValueError("El archivo está vacío")

        if len(df.columns) == 0:
            raise ValueError("El archivo no tiene columnas")

        # Extraer imágenes si es un archivo XLSX
        images_by_row = {}
        if filename.lower().endswith(('.xlsx', '.xls')):
            logger.info(f"Detectado archivo Excel, extrayendo imágenes...")
            try:
                # Convertir bytes a archivo temporal y extraer imágenes
                images_by_row = self.image_extractor.extract_from_bytes(
                    file_content if isinstance(file_content, bytes) else file_content.read(),
                    filename
                )
                if images_by_row:
                    logger.info(f"Extraídas imágenes para {len(images_by_row)} filas")
                else:
                    logger.info("No se encontraron imágenes en el archivo Excel")
            except Exception as e:
                logger.warning(f"Error al extraer imágenes: {str(e)}")
                # Continuar sin imágenes en caso de error
                images_by_row = {}

        return df, images_by_row