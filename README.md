# Request to Standard - PoC

Servicio de estandarización de datos que convierte archivos CSV/XLSX a formatos RAG 1 o RAG 2, con análisis automático de imágenes mediante AI.

## Descripción

Este proyecto implementa un pipeline completo de estandarización de datos siguiendo el flujo:

```
CSV/XLSX → Ingesta → Limpieza → Normalización → Análisis Metadatos → Routing (RAG1/RAG2) → Estandarización → Análisis de Imágenes (AI) → Validación → Output
```

### ✨ Características Destacadas

- **Estandarización Inteligente**: Convierte datos no estructurados a formatos RAG optimizados
- **Análisis de Imágenes con AI**: Extrae automáticamente descripciones de imágenes embebidas en archivos Excel
- **Procesamiento con Azure OpenAI**: Usa modelos avanzados de lenguaje y visión
- **Validación Automática**: Verifica integridad y calcula umbrales de confianza

### Formatos RAG

**RAG 1** - Documentos estructurados:
- Campos: `id`, `articulo_id`, `tipo`, `numero`, `titulo`, `texto`, `image_caption`, `keywords`, `embedding`
- Uso: Leyes, artículos, normativas, documentos formales
- **✨ Análisis de Imágenes**: El campo `image_caption` se genera automáticamente mediante AI cuando hay imágenes embebidas en archivos XLSX

**RAG 2** - Servicios/Tickets:
- Campos: `id`, `descripcion`, `tipo`, `servicio`, `categoria`, `subcategoria`, `fuente`, `embedding`
- Uso: Tickets de soporte, solicitudes, servicios

## Estructura del Proyecto

```
request-to-standard/
├── main.py                    # FastAPI app (ejecución local)
├── handler.py                 # Lambda handler (AWS)
├── mcp_server.py             # MCP server (futuro agente orquestador)
├── custom_logging.py         # Logging personalizado
├── requirements.txt          # Dependencias Python
├── .env.example             # Ejemplo de variables de entorno
├── src/
│   ├── api/                  # Routes FastAPI
│   ├── core/                 # Pipeline de procesamiento
│   │   ├── ingestion.py     # Step 1: Ingesta + extracción de imágenes
│   │   ├── cleaning.py      # Step 2: Limpieza
│   │   ├── normalization.py # Step 3: Normalización
│   │   ├── metadata_analysis.py # Step 4: Análisis
│   │   ├── routing.py       # Step 4.1: Routing RAG
│   │   ├── standardization.py # Step 5: Estandarización + análisis de imágenes
│   │   ├── validation.py    # Step 6: Validación
│   │   └── pipeline.py      # Orquestador principal
│   ├── gpt/                  # Azure OpenAI
│   │   ├── client.py        # Cliente Azure OpenAI + Vision API
│   │   └── prompts.py       # Templates de prompts (texto + visión)
│   ├── models/               # Schemas Pydantic
│   │   ├── rag1_schema.py   # Schema RAG 1
│   │   ├── rag2_schema.py   # Schema RAG 2
│   │   ├── request_models.py
│   │   └── response_models.py
│   ├── mcp/                  # MCP tools (futuro)
│   └── utils/                # Utilidades
│       ├── file_handlers.py
│       ├── image_extractor.py  # ✨ Extracción de imágenes de XLSX
│       └── sampling.py
├── docs/
│   └── diagrams/
│       └── standardization-flow.mmd
└── tests/
```

## Instalación

### 1. Crear entorno virtual con Python 3.12

```bash
# Windows
py -3.12 -m venv venv
venv\Scripts\activate

# Linux/Mac
python3.12 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

**Dependencias principales:**
- `fastapi` - Framework web
- `pandas` - Procesamiento de datos
- `openpyxl` - Lectura de archivos Excel
- `Pillow` - ✨ Procesamiento de imágenes
- `openai` - Cliente Azure OpenAI (incluye Vision API)
- `pydantic` - Validación de esquemas

### 3. Configurar variables de entorno

Copiar [.env.example](.env.example) a `.env` y configurar:

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales Azure OpenAI:

```env
# Azure OpenAI - Configuración principal
AZURE_OPENAI_O1MINI_API_KEY=tu-api-key
AZURE_OPENAI_O1MINI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_O1MINI_ENDPOINT=https://tu-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=tu-deployment-name

# Azure OpenAI - Embeddings (opcional)
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# ✨ Azure OpenAI - Vision (para análisis de imágenes en XLSX)
# Opcional - Si no se especifica, usa AZURE_OPENAI_DEPLOYMENT_NAME
# Recomendado: usar un modelo con capacidad de visión como gpt-4o
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o

# Configuración de la aplicación
ENVIRONMENT=development
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=50
```

#### Configuración del Modelo de Visión

Para habilitar el **análisis automático de imágenes** en archivos XLSX:

1. **Despliega un modelo de visión** en Azure OpenAI:
   - Modelos recomendados: `gpt-4o`, `gpt-4-vision-preview`, `gpt-4-turbo`
   - Región: Asegúrate que la región soporte modelos de visión

2. **Configura la variable de entorno**:
   ```env
   AZURE_OPENAI_VISION_DEPLOYMENT=nombre-de-tu-deployment-vision
   ```

3. **Opcional**: Si tu deployment principal ya soporta visión, puedes omitir esta variable:
   ```env
   # Si AZURE_OPENAI_DEPLOYMENT_NAME ya es un modelo de visión (ej: gpt-4o)
   # No necesitas configurar AZURE_OPENAI_VISION_DEPLOYMENT
   ```

**Nota**: El análisis de imágenes solo funciona con:
- Archivos XLSX (no CSV)
- Formato RAG 1 (RAG 2 no tiene campo `image_caption`)
- Imágenes embebidas en las celdas de Excel

## Uso

### Ejecución Local (FastAPI)

```bash
# Opción 1: Usando uvicorn directamente
uvicorn main:app --reload

# Opción 2: Ejecutando main.py
python main.py
```

Acceder a:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Endpoints Disponibles

#### 1. `POST /standardize` ⭐ (Principal)

**Flujo completo de estandarización** - Ejecuta todos los pasos del diagrama (1-6)

**Pipeline interno:**
```
Ingesta → Limpieza → Normalización → Mapeo → Estandarización → Validación
```

**Parámetros:**
- `file`: Archivo CSV/XLSX (required)
- `target_rag`: "rag1" o "rag2" (required) - El orquestador decide esto
- `generate_embeddings`: boolean (optional, default: false)

**RAG Options:**
- `rag1`: Documentos estructurados (leyes, artículos, normativas)
- `rag2`: Servicios/Tickets (solicitudes, incidentes, soporte)

**Ejemplo con cURL:**

```bash
curl -X POST "http://localhost:8000/standardize" \
  -F "file=@datos.csv" \
  -F "target_rag=rag1" \
  -F "generate_embeddings=false"
```

**Ejemplo con Python:**

```python
import requests

url = "http://localhost:8000/standardize"
files = {'file': open('datos.csv', 'rb')}
data = {'target_rag': 'rag1', 'generate_embeddings': False}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"RAG utilizado: {result['selected_rag']}")
print(f"Registros procesados: {len(result['result']['data'])}")
print(f"Confianza: {result['result']['confidence_score']}")
```

#### 2. `POST /analyze` (Opcional - Preview)

**Preview del archivo** - Analiza y sugiere qué RAG usar (NO estandariza)

El orquestador puede usar este endpoint para obtener información antes de decidir,
o puede llamar directamente a `/standardize` si ya sabe qué RAG necesita.

**Retorna:**
- Estructura del archivo (filas, columnas, tipos)
- Análisis de contexto con LLM (tipo de datos, dominio, intención)
- Sugerencia de RAG (`suggested_rag`)
- Muestra de 3 registros

**Ejemplo:**

```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "file=@datos.csv"
```

**Respuesta:**

```json
{
  "success": true,
  "suggested_rag": "rag1",
  "analysis": {
    "tipo_consulta": "documentos legales",
    "contexto_negocio": "Legal",
    "nivel_confianza": 0.95
  },
  "next_step": "POST /standardize con target_rag='rag1'"
}
```

#### 3. `GET /schemas`

Obtiene esquemas RAG 1 y RAG 2

```bash
curl "http://localhost:8000/schemas"
```

### Ejecución en AWS Lambda

#### Despliegue con Serverless Framework

```bash
# Instalar serverless
npm install -g serverless

# Desplegar
serverless deploy
```

**serverless.yml ejemplo:**

```yaml
service: request-to-standard

provider:
  name: aws
  runtime: python3.12
  region: us-east-1
  timeout: 300
  memorySize: 1024

functions:
  api:
    handler: handler.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
      - s3:
          bucket: my-data-bucket
          event: s3:ObjectCreated:*
          rules:
            - prefix: uploads/
            - suffix: .csv
```

### MCP Server (Futuro)

El servidor MCP está preparado como placeholder para integración futura con el agente orquestador.

```bash
# Cuando esté listo
python mcp_server.py
```

**Tools disponibles:**
- `standardize_data`: Estandarizar archivo
- `analyze_structure`: Analizar estructura
- `get_schemas`: Obtener esquemas

## Pipeline de Procesamiento

### Step 1: Ingesta de Datos
- Lee archivos CSV/XLSX
- Detecta encoding automáticamente
- Valida estructura básica
- **✨ Extrae imágenes embebidas** (solo XLSX)
- Mapea imágenes a sus filas correspondientes

### Step 2: Limpieza
- Elimina espacios en blanco
- Normaliza encoding UTF-8
- Remueve caracteres especiales
- Maneja valores faltantes

### Step 3: Normalización
- Normaliza nombres de columnas
- Infiere y convierte tipos de datos
- Valida estructura

### Step 4: Análisis de Metadatos
- Usa LLM (Azure OpenAI) para analizar:
  - Tipo de consulta/documento
  - Contexto de negocio
  - Parámetros relevantes
  - Intención del usuario

### Step 4.1: Routing RAG
- Determina RAG apropiado (1 o 2)
- Genera mapeo de columnas
- Usa LLM + heurísticas

### Step 5: Estandarización
- **5.1**: Conceptualización con LLM
- **5.2**: Traducción de datos
- **5.3**: Generación de registros estandarizados
- **5.4**: ✨ **Análisis de Imágenes con AI** (solo RAG 1):
  - Detecta imágenes asociadas a cada registro
  - Analiza imágenes con Azure OpenAI Vision
  - Extrae descripciones enfocadas en:
    - Pasos e instrucciones secuenciales
    - Procesos y diagramas de flujo
    - Información procedural
    - Texto relevante en imágenes
  - Genera descripciones concisas y accionables
  - Popula campo `image_caption` automáticamente

### Step 6: Validación
- Valida estructura con Pydantic
- Calcula umbral de confianza
- Verifica integridad de datos

## ✨ Análisis Automático de Imágenes con AI

El sistema incluye análisis automático de imágenes embebidas en archivos Excel usando Azure OpenAI Vision.

### Características

- **Extracción Automática**: Detecta y extrae imágenes de archivos XLSX
- **Análisis Inteligente**: Usa modelos de visión (GPT-4o) para entender el contenido
- **Enfoque Procedural**: Extrae pasos, instrucciones y procesos
- **Múltiples Imágenes**: Soporta múltiples imágenes por fila
- **Sin Configuración**: Se activa automáticamente cuando detecta imágenes

### Cómo Funciona

1. **Subir archivo XLSX con imágenes embebidas**
2. El sistema automáticamente:
   - Extrae las imágenes durante la ingesta
   - Las mapea a sus filas correspondientes
   - Las analiza con Azure OpenAI Vision
   - Genera descripciones inteligentes
   - Popula el campo `image_caption` en RAG 1

### Ejemplo de Uso

**Archivo Excel de entrada:**
```
| doc_ref | titulo           | texto                    | [Imagen Embebida]     |
|---------|------------------|--------------------------|-----------------------|
| ART001  | Setup Guide      | Complete instructions... | [3 imágenes de pasos] |
```

**Salida RAG 1:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "articulo_id": "ART001",
  "tipo": "Tutorial",
  "numero": 1,
  "titulo": "Setup Guide",
  "texto": "Complete instructions...",
  "image_caption": "Paso 1 (Imagen 1): Abrir el menú de configuración. Paso 2 (Imagen 2): Navegar a la pestaña de opciones. Paso 3 (Imagen 3): Hacer clic en guardar cambios.",
  "keywords": null,
  "embedding": null
}
```

### Tipos de Contenido Detectado

El modelo de visión está optimizado para extraer:

- ✅ **Pasos secuenciales**: "Paso 1: ..., Paso 2: ..., Paso 3: ..."
- ✅ **Diagramas de flujo**: Descripción del proceso representado
- ✅ **Capturas de pantalla**: Procedimientos paso a paso
- ✅ **Texto en imágenes**: Transcripción de elementos clave
- ✅ **Gráficos y tablas**: Datos relevantes extraídos

### Requisitos

1. **Archivo XLSX** (no funciona con CSV)
2. **Formato RAG 1** (RAG 2 no tiene campo `image_caption`)
3. **Imágenes embebidas en celdas** (Insert → Pictures → Place in Cell en Excel)
4. **Modelo de visión configurado** (ver sección de configuración arriba)

### Manejo de Errores

Si el análisis de imágenes falla:
- El campo `image_caption` se establece como `null`
- El procesamiento continúa sin interrupciones
- Los errores se registran en los logs

### Documentación Detallada

Para más información, consulta [IMAGE_ANALYSIS_FEATURE.md](IMAGE_ANALYSIS_FEATURE.md)

## Testing

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio httpx

# Ejecutar tests
pytest tests/
```

### Probar con Imágenes

Para probar el análisis automático de imágenes:

1. **Crear un archivo Excel de prueba**:
   - Abre Excel y crea datos de prueba
   - Inserta imágenes: `Insert → Pictures → Place in Cell`
   - Guarda como `.xlsx`

2. **Subir el archivo**:
   ```bash
   curl -X POST "http://localhost:8000/standardize" \
     -F "file=@test_with_images.xlsx" \
     -F "target_rag=rag1"
   ```

3. **Verificar resultados**:
   - El campo `image_caption` debe contener descripciones de las imágenes
   - Si no hay imágenes, `image_caption` será `null`
   - Revisa los logs para ver el progreso del análisis

**Tipos de imágenes recomendadas para testing:**
- Capturas de pantalla con instrucciones
- Diagramas de flujo o procesos
- Imágenes con texto visible
- Gráficos o tablas

## Desarrollo

### Agregar nuevo campo a RAG

Editar [src/models/rag1_schema.py](src/models/rag1_schema.py) o [src/models/rag2_schema.py](src/models/rag2_schema.py):

```python
class RAG1Schema(BaseModel):
    # ... campos existentes
    nuevo_campo: str = Field(..., description="Descripción")
```

### Personalizar prompts

Editar [src/gpt/prompts.py](src/gpt/prompts.py):

```python
@staticmethod
def custom_prompt(data: dict) -> str:
    return f"""Tu prompt aquí...
    {json.dumps(data)}
    """
```

## Limitaciones del PoC

- Procesa máximo 100 filas con LLM (muestra)
- No incluye base de datos persistente
- Embeddings opcionales (requiere configuración adicional)
- Validación básica de umbral (80%)
- Análisis de imágenes secuencial (no paralelo)
- Análisis de imágenes solo para XLSX y RAG 1

## Roadmap

### Completado ✅
- [x] ✨ **Análisis automático de imágenes con AI** (Nov 2024)
- [x] Extracción de imágenes de archivos XLSX
- [x] Integración con Azure OpenAI Vision
- [x] Generación automática de `image_caption`

### Pendiente
- [ ] Implementación completa de embeddings
- [ ] Procesamiento en chunks para datasets grandes
- [ ] Base de datos PostgreSQL/SQLite
- [ ] Caché de resultados
- [ ] Tests unitarios completos
- [ ] Integración MCP con agente orquestador
- [ ] Monitoreo y métricas
- [ ] Análisis de imágenes en paralelo
- [ ] Soporte de imágenes para RAG 2
- [ ] OCR especializado para imágenes con mucho texto

## Licencia

Propietario - Uso interno

## Contacto

Para preguntas sobre este proyecto, contactar al equipo de desarrollo.