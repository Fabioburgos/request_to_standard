"""
Utilidades para serialización JSON
Maneja tipos de pandas que no son JSON-compliant
"""
import numpy as np
import pandas as pd
from typing import Any, Dict, List
from datetime import datetime, date


def clean_for_json(data: Any) -> Any:
    """
    Limpia datos para que sean serializables a JSON

    Maneja:
    - NaN, Infinity → None
    - datetime, Timestamp → string ISO 8601
    - numpy types → tipos Python nativos

    Args:
        data: Cualquier tipo de dato (dict, list, DataFrame, valor simple)

    Returns:
        Datos limpios serializables a JSON
    """
    # Verificar None primero (antes de cualquier operación)
    if data is None:
        return None

    # Verificar tipos específicos de pandas/numpy (en orden correcto)
    if isinstance(data, (pd.Timestamp, datetime, date)):
        # Convertir fechas a string ISO 8601
        return data.isoformat()

    elif isinstance(data, np.ndarray):
        # Convertir arrays numpy a listas (ANTES de verificar isna)
        return clean_for_json(data.tolist())

    elif isinstance(data, (np.integer, np.floating)):
        # Convertir numpy types a Python nativos
        try:
            if np.isnan(data) or np.isinf(data):
                return None
        except (TypeError, ValueError):
            pass
        return data.item()

    elif isinstance(data, pd.DataFrame):
        # Convertir DataFrame a dict y limpiar
        return clean_for_json(data.to_dict(orient='records'))

    elif isinstance(data, pd.Series):
        # Convertir Series a lista y limpiar
        return clean_for_json(data.tolist())

    elif isinstance(data, dict):
        return {key: clean_for_json(value) for key, value in data.items()}

    elif isinstance(data, (list, tuple)):
        return [clean_for_json(item) for item in data]

    elif isinstance(data, (float, int)):
        # Verificar si es NaN o Infinity
        try:
            if np.isnan(data) or np.isinf(data):
                return None
        except (TypeError, ValueError):
            pass
        return data

    # Verificar pd.isna al final (para scalars)
    try:
        if pd.isna(data):
            return None
    except (TypeError, ValueError):
        pass

    # Otros tipos: convertir a string si no es JSON serializable
    try:
        import json
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


def df_to_json_safe(df: pd.DataFrame, orient: str = 'records') -> List[Dict[str, Any]]:
    """
    Convierte DataFrame a formato JSON-safe

    Args:
        df: DataFrame de pandas
        orient: Orientación para to_dict ('records', 'index', etc.)

    Returns:
        Lista de diccionarios listos para JSON
    """
    # Reemplazar NaN, Infinity en el DataFrame
    df_clean = df.replace({
        np.nan: None,
        np.inf: None,
        -np.inf: None
    })

    # Convertir a dict
    data = df_clean.to_dict(orient=orient)

    # Limpiar recursivamente
    return clean_for_json(data)
