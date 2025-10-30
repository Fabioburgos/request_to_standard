# Request to Standard - PoC

Servicio de estandarización de datos que convierte archivos CSV/XLSX a formatos RAG 1 o RAG 2.

## Descripción

Este proyecto implementa un pipeline completo de estandarización de datos siguiendo el flujo:

```
CSV/XLSX → Ingesta → Limpieza → Normalización → Análisis Metadatos → Routing (RAG1/RAG2) → Estandarización → Validación → Output
```

### Formatos RAG

**RAG 1** - Documentos estructurados:
- Campos: `id`, `articulo_id`, `tipo`, `numero`, `titulo`, `texto`, `image_caption`, `keywords`, `embedding`
- Uso: Leyes, artículos, normativas, documentos formales

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
│   │   ├── ingestion.py     # Step 1: Ingesta
│   │   ├── cleaning.py      # Step 2: Limpieza
│   │   ├── normalization.py # Step 3: Normalización
│   │   ├── metadata_analysis.py # Step 4: Análisis
│   │   ├── routing.py       # Step 4.1: Routing RAG
│   │   ├── standardization.py # Step 5: Estandarización
│   │   ├── validation.py    # Step 6: Validación
│   │   └── pipeline.py      # Orquestador principal
│   ├── gpt/                  # Azure OpenAI
│   │   ├── client.py        # Cliente Azure OpenAI
│   │   └── prompts.py       # Templates de prompts
│   ├── models/               # Schemas Pydantic
│   │   ├── rag1_schema.py   # Schema RAG 1
│   │   ├── rag2_schema.py   # Schema RAG 2
│   │   ├── request_models.py
│   │   └── response_models.py
│   ├── mcp/                  # MCP tools (futuro)
│   └── utils/                # Utilidades
│       ├── file_handlers.py
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

### 3. Configurar variables de entorno

Copiar [.env.example](.env.example) a `.env` y configurar:

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales Azure OpenAI:

```env
AZURE_OPENAI_O1MINI_API_KEY=tu-api-key
AZURE_OPENAI_O1MINI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_O1MINI_ENDPOINT=https://tu-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=tu-deployment-name
```

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

### Step 6: Validación
- Valida estructura con Pydantic
- Calcula umbral de confianza
- Verifica integridad de datos

## Testing

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio httpx

# Ejecutar tests
pytest tests/
```

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

## Roadmap

- [ ] Implementación completa de embeddings
- [ ] Procesamiento en chunks para datasets grandes
- [ ] Base de datos PostgreSQL/SQLite
- [ ] Caché de resultados
- [ ] Tests unitarios completos
- [ ] Integración MCP con agente orquestador
- [ ] Monitoreo y métricas

## Licencia

Propietario - Uso interno

## Contacto

Para preguntas sobre este proyecto, contactar al equipo de desarrollo.