"""
Utilidades para manejo de archivos CSV y XLSX
Step 1: Ingesta de Datos
"""
import io
import pandas as pd
from pathlib import Path
from typing import Union, BinaryIO


class FileHandler:
    """Manejador de archivos CSV y XLSX"""

    @staticmethod
    def detect_file_type(filename: str) -> str:
        """Detecta el tipo de archivo por extensión"""
        suffix = Path(filename).suffix.lower()
        if suffix == '.csv':
            return 'csv'
        elif suffix in ['.xlsx', '.xls']:
            return 'xlsx'
        else:
            raise ValueError(f"Tipo de archivo no soportado: {suffix}. Use CSV o XLSX")

    @staticmethod
    def read_file(file_content: Union[bytes, BinaryIO], filename: str) -> pd.DataFrame:
        """
        Lee archivo CSV o XLSX y retorna DataFrame

        Args:
            file_content: Contenido del archivo en bytes o file-like object
            filename: Nombre del archivo para detectar tipo

        Returns:
            pd.DataFrame con los datos
        """
        file_type = FileHandler.detect_file_type(filename)

        # Convertir a BytesIO si es necesario
        if isinstance(file_content, bytes):
            file_obj = io.BytesIO(file_content)
        else:
            file_obj = file_content

        try:
            if file_type == 'csv':
                # Intentar detectar encoding
                df = pd.read_csv(file_obj, encoding='utf-8')
            else:  # xlsx
                df = pd.read_excel(file_obj, engine='openpyxl')

            return df

        except UnicodeDecodeError:
            # Reintentar con encoding latin-1
            file_obj.seek(0)
            df = pd.read_csv(file_obj, encoding='latin-1')
            return df

        except Exception as e:
            raise ValueError(f"Error al leer archivo: {str(e)}")

    @staticmethod
    def get_file_info(df: pd.DataFrame, filename: str, file_size: int) -> dict:
        """Obtiene información del archivo procesado"""
        return {
            "filename": filename,
            "size_bytes": file_size,
            "rows_count": len(df),
            "columns_count": len(df.columns),
            "file_type": FileHandler.detect_file_type(filename)
        }
