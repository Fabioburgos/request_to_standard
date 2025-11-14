"""
Prompts para Azure OpenAI
Conceptualización y mapeo de datos
"""
import json


class PromptTemplates:
    """Templates de prompts para diferentes etapas del pipeline"""

    @staticmethod
    def metadata_analysis_prompt(data_summary: dict) -> str:
        """
        Prompt para Step 4: Identificación de Metadatos

        Analiza el tipo de consulta, contexto de negocio, parámetros relevantes
        """
        return f"""Analiza el siguiente conjunto de datos y extrae metadatos clave.

        DATOS A ANALIZAR:
        {json.dumps(data_summary, indent=2, ensure_ascii=False)}

        TAREA:
        1. Identifica el tipo de consulta/documento (ej: legal, servicios, tickets, artículos, etc.)
        2. Determina el contexto de negocio
        3. Identifica parámetros relevantes
        4. Infiere la intención o propósito de estos datos

        RESPONDE EN FORMATO JSON:
        {{
            "tipo_consulta": "descripción del tipo de datos",
            "contexto_negocio": "dominio o industria",
            "parametros_relevantes": ["lista", "de", "campos", "importantes"],
            "intencion_usuario": "propósito inferido",
            "nivel_confianza": 0.95
        }}

        Responde SOLO con el JSON, sin texto adicional."""

    # NOTA: rag_selection_prompt fue removido
    # La decisión de qué RAG usar ahora es responsabilidad del orquestador
    # El endpoint /analyze proporciona información para que el orquestador decida

    @staticmethod
    def standardization_prompt(
        df_sample: dict,
        target_rag: str,
        column_mapping: dict
    ) -> str:
        """
        Prompt para Step 5: Estandarización

        El LLM analiza 10 filas de muestra y devuelve REGLAS de transformación
        Luego aplicamos esas reglas a TODAS las filas
        """
        rag_schema = {
            "rag1": {
                "campos": ["id", "articulo_id", "tipo", "numero", "titulo", "texto", "image_caption", "keywords"],
                "descripcion": "Documentos estructurados con artículos/normativas"
            },
            "rag2": {
                "campos": ["id", "descripcion", "tipo", "servicio", "categoria", "subcategoria", "fuente"],
                "descripcion": "Servicios, tickets y solicitudes"
            }
        }

        schema_info = rag_schema.get(target_rag, rag_schema["rag1"])

        return f"""Analiza esta MUESTRA de 10 registros y genera REGLAS DE TRANSFORMACIÓN para convertir datos al formato {target_rag.upper()}.

        IMPORTANTE: NO transformes los registros. Solo analiza el contexto y genera las REGLAS.

        ESQUEMA DESTINO ({target_rag.upper()}):
        {json.dumps(schema_info, indent=2, ensure_ascii=False)}

        MAPEO DE COLUMNAS YA IDENTIFICADO:
        {json.dumps(column_mapping, indent=2, ensure_ascii=False)}

        MUESTRA DE DATOS (10 registros para análisis de contexto):
        {json.dumps(df_sample, indent=2, ensure_ascii=False)}

        TU TAREA:
        Analiza la muestra y genera reglas de transformación que se aplicarán a TODOS los registros del dataset.

        REGLAS REQUERIDAS:
        1. Para cada campo del esquema {target_rag.upper()}, especifica:
           - De qué columna(s) origen proviene el valor
           - Qué transformación aplicar (copiar tal cual, limpiar, combinar, extraer keywords, etc.)
           - Si hay que preservar contenido completo (para texto/descripcion)

        2. Reglas especiales según el tipo de dato:
           - **Campos de texto largo (texto/descripcion)**: SIEMPRE copiar contenido COMPLETO sin resumir
           - **Keywords/tags**: Si contienen separadores como ";" o ",", especificar cómo unificar
           - **Campos numéricos**: Convertir a entero, valor por defecto si falta
           - **Campos opcionales**: Indicar qué hacer si están vacíos (null o valor por defecto)

        RESPONDE EN FORMATO JSON:
        {{
            "reglas_transformacion": {{
                "articulo_id": {{
                    "columna_origen": "doc_ref",
                    "transformacion": "copiar_tal_cual",
                    "valor_por_defecto": null
                }},
                "tipo": {{
                    "columna_origen": "category",
                    "transformacion": "copiar_tal_cual",
                    "valor_por_defecto": "General"
                }},
                "numero": {{
                    "columna_origen": "section_num",
                    "transformacion": "convertir_a_entero",
                    "valor_por_defecto": 0
                }},
                "titulo": {{
                    "columna_origen": "header",
                    "transformacion": "copiar_tal_cual",
                    "valor_por_defecto": "Sin título"
                }},
                "texto": {{
                    "columna_origen": "body_content",
                    "transformacion": "copiar_completo_sin_resumir",
                    "valor_por_defecto": ""
                }},
                "image_caption": {{
                    "columna_origen": "fig_desc",
                    "transformacion": "copiar_si_existe_sino_null",
                    "valor_por_defecto": null
                }},
                "keywords": {{
                    "columna_origen": "tags",
                    "transformacion": "separar_por_punto_coma_unir_con_coma",
                    "valor_por_defecto": null
                }}
            }},
            "validaciones": [
                "texto debe tener más de 20 caracteres",
                "titulo no puede estar vacío"
            ],
            "contexto_analizado": {{
                "tipo_de_datos": "documentos legales estructurados",
                "observaciones": "Los tags usan punto y coma como separador"
            }}
        }}

        Responde SOLO con el JSON de reglas, sin markdown ni texto adicional."""

    @staticmethod
    def validation_prompt(standardized_data: dict, target_rag: str) -> str:
        """
        Prompt para Step 6: Validación

        Valida la estructura y calcula umbral de confianza
        """
        return f"""Valida los siguientes datos estandarizados para {target_rag.upper()}.

        DATOS ESTANDARIZADOS:
        {json.dumps(standardized_data, indent=2, ensure_ascii=False)}

        TAREA:
        1. Verifica que todos los campos requeridos estén presentes
        2. Valida tipos de datos
        3. Calcula un umbral de confianza (0-1)
        4. Identifica problemas de integridad

        RESPONDE EN FORMATO JSON:
        {{
            "es_valido": true/false,
            "umbral_confianza": 0.95,
            "problemas": ["lista de problemas encontrados"],
            "campos_faltantes": [],
            "recomendaciones": []
        }}

        Responde SOLO con el JSON, sin texto adicional."""

    @staticmethod
    def image_analysis_prompt() -> str:
        """
        Prompt para análisis de imágenes con visión AI.

        Enfocado en extraer información procedural, pasos, diagramas, y contenido instructivo.
        """
        return """Analiza esta imagen y proporciona una descripción concisa y precisa.

ENFOQUE PRIORITARIO:
- Si la imagen contiene pasos o instrucciones secuenciales, extrae y enumera cada paso claramente
- Si es un diagrama de flujo, describe el proceso que representa
- Si es una captura de pantalla de un procedimiento, describe el proceso paso a paso
- Si contiene texto importante, transcribe los elementos clave
- Si es un gráfico o tabla, describe los datos más relevantes

FORMATO DE RESPUESTA:
- Usa un lenguaje claro y directo
- Si hay pasos numerados, usa formato: "Paso 1: ..., Paso 2: ..., Paso 3: ..."
- Si hay múltiples elementos, sepáralos claramente
- Máximo 2-3 oraciones si no hay pasos; formato estructurado si hay procedimiento
- No incluyas opiniones, solo describe lo que se ve

IMPORTANTE:
- Concéntrate en información accionable (qué hacer, cómo hacerlo)
- Omite detalles visuales irrelevantes (colores, diseño) a menos que sean cruciales
- Si la imagen no contiene información útil o está borrosa, indica: "Imagen no contiene información relevante"

Proporciona la descripción directamente, sin preámbulos."""

    @staticmethod
    def multiple_images_analysis_prompt(num_images: int) -> str:
        """
        Prompt para análisis de múltiples imágenes.

        Args:
            num_images: Número de imágenes a analizar

        Returns:
            Prompt formateado para análisis de múltiples imágenes
        """
        return f"""Analiza estas {num_images} imágenes y proporciona una descripción integrada.

ENFOQUE PRIORITARIO:
- Si las imágenes muestran un proceso secuencial, describe cada paso en orden
- Si son diferentes aspectos del mismo tema, describe cada uno por separado
- Identifica relaciones entre las imágenes si existen
- Extrae información procedural, pasos, o instrucciones de cada imagen

FORMATO DE RESPUESTA:
Para cada imagen, usa el formato:
"Imagen 1: [descripción concisa]. Imagen 2: [descripción concisa]."

Si representan pasos secuenciales:
"Paso 1 (Imagen 1): [descripción]. Paso 2 (Imagen 2): [descripción]."

IMPORTANTE:
- Mantén cada descripción concisa (1-2 oraciones por imagen)
- Enfócate en información accionable
- Si alguna imagen no aporta información relevante, indícalo brevemente
- Máximo 3-4 oraciones por imagen

Proporciona la descripción directamente, sin preámbulos."""
