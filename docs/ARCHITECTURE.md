# Request to Standard - Documentación Técnica

**Servidor MCP para Estandarización Automática de Datos Multi-Tenant**

---

## Índice

1. [Resumen del Proyecto](#1-resumen-del-proyecto)
2. [Diferencia con Proyectos que Usan Wrapper](#2-diferencia-con-proyectos-que-usan-wrapper)
3. [Herramientas Expuestas](#3-herramientas-expuestas)
4. [Pipeline de Estandarización (7 Pasos)](#4-pipeline-de-estandarización-7-pasos)
5. [Integración con Orquestador](#5-integración-con-orquestador)
6. [Sistema Multi-Tenant con Aurora DSQL](#6-sistema-multi-tenant-con-aurora-dsql)
7. [Configuración y Dependencias](#7-configuración-y-dependencias)

---

## 1. Resumen del Proyecto

**Request to Standard** es un servidor MCP que estandariza archivos CSV/XLSX a formatos RAG optimizados, con análisis automático de imágenes mediante Azure OpenAI Vision y almacenamiento en PostgreSQL Aurora DSQL con schema isolation multi-tenant.

**Características principales:**
- Pipeline de 7 pasos automatizado
- Análisis de imágenes con AI (Azure OpenAI Vision)
- Multi-tenant con aislamiento completo por cliente
- Auto-provisioning de schemas y tablas
- Autenticación IAM para Aurora DSQL
- 2 formatos RAG: documentos (RAG1) y servicios/tickets (RAG2)

**Stack Tecnológico:**
- Python 3.12 + FastAPI
- Azure OpenAI (GPT-4o + Vision + Embeddings)
- PostgreSQL Aurora DSQL
- AWS Lambda (serverless)
- MCP (Model Context Protocol)

---

## 2. Diferencia con Proyectos que Usan Wrapper

### Este Proyecto: MCP Directo (Sin Wrapper SSE)

**Arquitectura:**
- **Invocación directa**: Lambda recibe JSON-RPC 2.0 del orquestador
- **Sin servidor MCP dedicado**: No usa `mcp.server.Server()`
- **Stateless**: Request-response simple, sin streaming
- **Handler manual**: Implementación manual de protocolo JSON-RPC

**Código clave** ([handler.py](../handler.py)):
```python
# Orquestador invoca directamente con JSON-RPC 2.0
async def handle_method(method: str, params: dict, msg_id):
    if method == "tools/call":
        client_id = arguments.get('client_id')  # Multi-tenant
        result = await invoke_standardize_tool(client_id, ...)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
```

### Proyectos con Wrapper SSE (Tradicionales)

**Arquitectura:**
- **Wrapper SSE**: Lambda mantiene conexión SSE con servidor MCP
- **Servidor MCP dedicado**: Usa `mcp.server.Server()` con decoradores
- **Streaming bidireccional**: stdio/SSE con eventos en tiempo real
- **Proceso persistente**: Servidor MCP corriendo continuamente

**Comparación:**

| Aspecto | MCP Directo (Este proyecto) | Wrapper SSE (Tradicional) |
|---------|----------------------------|---------------------------|
| Servidor MCP | ❌ No | ✅ Sí |
| Transporte | JSON-RPC sobre Lambda | stdio/SSE streaming |
| Despliegue | Serverless (Lambda) | Proceso dedicado |
| Escalabilidad | Auto-scaling Lambda | Limitada por servidor |
| Costo | Pay-per-invocation | Servidor 24/7 |

**¿Por qué MCP Directo?**
- Integración nativa con AWS (Lambda, DynamoDB, Aurora DSQL)
- Escalabilidad automática sin gestión de infraestructura
- Multi-tenant natural (client_id en cada invocación)
- Costo optimizado (solo paga por uso)

---

## 3. Herramientas Expuestas

### Tool: `standardize_data`

**Definición** ([src/tools/standardize_tool.py](../src/tools/standardize_tool.py)):

```python
Tool(
    name = "standardize_data",
    description = "Estandariza archivos CSV/XLSX a formatos RAG optimizados..."
)
```

### Parámetros de Entrada

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `client_id` | string | ✅ Sí | ID del cliente para schema isolation (ej: `"helpdesk_ivanti"`) |
| `file_content` | string | ✅ Sí | Archivo en base64 |
| `filename` | string | ✅ Sí | Nombre del archivo (`.csv` o `.xlsx`) |
| `target_rag` | enum | ✅ Sí | Formato: `"rag1"` (documentos) o `"rag2"` (servicios) |
| `generate_embeddings` | boolean | ❌ No | Generar embeddings (default: `true`) |
| `save_to_knowledge_base` | boolean | ❌ No | Guardar en PostgreSQL (default: `true`) |

### Outputs

**Response exitosa:**
```json
{
  "success": true,
  "result": {
    "format": "rag1_standard",
    "data": [/* registros estandarizados */],
    "metadata": {
      "client_id": "helpdesk_ivanti",
      "schema": "kb_helpdesk_ivanti",
      "column_mapping": {...},
      "validation": {...},
      "storage": {
        "table": "knowledge_base_rag1",
        "saved": 100,
        "failed": 0
      }
    },
    "confidence_score": 0.95
  },
  "processing_time_seconds": 12.3
}
```

### Formatos RAG

**RAG 1 - Documentos Estructurados:**
```json
{
  "id": "uuid",
  "articulo_id": "ART001",
  "tipo": "Ley",
  "numero": 42,
  "titulo": "Título del artículo",
  "texto": "Contenido completo...",
  "image_caption": "Descripción AI de imagen",
  "keywords": "palabra1, palabra2",
  "embedding": [0.1, 0.2, ...]
}
```

**RAG 2 - Servicios/Tickets:**
```json
{
  "id": "uuid",
  "descripcion": "Descripción del servicio",
  "tipo": "Soporte",
  "servicio": "IT",
  "categoria": "Redes",
  "subcategoria": "Configuración",
  "fuente": "csv",
  "embedding": [0.1, 0.2, ...]
}
```

---

## 4. Pipeline de Estandarización (7 Pasos)

**Archivo:** [src/core/pipeline.py](../src/core/pipeline.py)

### Diagrama de Flujo

```
Archivo CSV/XLSX
    ↓
[1] INGESTA → DataFrame + imágenes extraídas
    ↓
[2] LIMPIEZA → Espacios, UTF-8, caracteres especiales
    ↓
[3] IDENTIFICACIÓN → Mapeo de columnas relevantes
    ↓
[4] NORMALIZACIÓN → Tipos de datos, nombres de columnas
    ↓
[5] ESTANDARIZACIÓN → Análisis LLM + Vision + Embeddings
    ↓
[6] VALIDACIÓN → Confidence score + completeness
    ↓
[7] STORAGE → PostgreSQL (kb_<client_id>)
```

### Detalles de Cada Paso

#### Step 1: Ingesta
- **Archivo:** `src/core/ingestion.py`
- **Input:** Bytes del archivo (CSV/XLSX)
- **Proceso:** Lee archivo, extrae imágenes embebidas (XLSX)
- **Output:** `DataFrame`, `images_by_row`

#### Step 2: Limpieza
- **Archivo:** `src/core/cleaning.py`
- **Proceso:** Elimina espacios, normaliza UTF-8, remueve caracteres especiales
- **Output:** DataFrame limpio

#### Step 3: Identificación de Columnas
- **Archivo:** `src/core/pipeline.py` (líneas 226-364)
- **Proceso:** Mapea columnas origen → campos RAG destino
- **Detección automática:** Columnas con texto largo (>50 chars) → campo descriptivo
- **Output:** `column_mapping`

#### Step 4: Normalización
- **Archivo:** `src/core/normalization.py`
- **Proceso:** Normaliza nombres (lowercase, underscores), convierte tipos
- **Output:** DataFrame normalizado

#### Step 5: Estandarización (4 sub-pasos)
- **Archivo:** `src/core/standardization.py`
- **5.1:** LLM analiza muestra (10 registros) y genera reglas
- **5.2:** Aplica reglas a TODOS los registros
- **5.3:** Genera JSON validado con Pydantic + embeddings
- **5.4:** Análisis de imágenes con Azure Vision (solo RAG1 + XLSX)
- **Output:** Lista de registros estandarizados

#### Step 6: Validación
- **Archivo:** `src/core/validation.py`
- **Proceso:** Validación Pydantic, confidence score, completeness rate
- **Métricas:**
  - `confidence_score`: % registros válidos (umbral: 80%)
  - `completeness_rate`: % registros completos
  - `quality_score`: (60% confidence + 40% completeness)
- **Output:** `validation_result`

#### Step 7: Guardado en PostgreSQL
- **Archivo:** `src/storage/postgres_storage.py`
- **Proceso:**
  1. Verificar/crear schema `kb_<client_id>`
  2. Verificar/crear tablas RAG1/RAG2
  3. INSERT/UPSERT registros
- **Output:** Estadísticas de guardado

### Tabla de Inputs/Outputs

| Step | Input | Output | Tiempo Típico |
|------|-------|--------|---------------|
| 1 | Bytes del archivo | DataFrame + imágenes | 0.5-2s |
| 2 | DataFrame raw | DataFrame clean | 0.1-0.5s |
| 3 | DataFrame clean | column_mapping + DataFrame filtered | 0.1-0.3s |
| 4 | DataFrame filtered | DataFrame normalized | 0.1-0.3s |
| 5 | DataFrame normalized | standardized_records | 3-10s |
| 6 | standardized_records | validation_result | 0.1-0.5s |
| 7 | standardized_records | storage_result | 0.5-2s |

**Tiempo total típico:** 5-20 segundos

---

## 5. Integración con Orquestador

### Configuración en Orquestador

El orquestador debe configurar:

```python
MCP_WRAPPERS = {
    "request-to-standard": "dev-mcp-wrapper-request-to-standard"  # Lambda name
}
```

### Flujo de Invocación

```
1. Usuario envía email con archivo adjunto
2. Webhook → Orquestador
3. Orquestador busca client_id en DynamoDB (por subscription_id)
4. Orquestador codifica archivo en base64
5. Orquestador infiere target_rag del contenido
6. Orquestador invoca Lambda con JSON-RPC 2.0
```

### Payload JSON-RPC

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "standardize_data",
    "arguments": {
      "client_id": "helpdesk_ivanti",
      "file_content": "UEsDBBQABgAIAAAA...",
      "filename": "datos.xlsx",
      "target_rag": "rag1",
      "generate_embeddings": true,
      "save_to_knowledge_base": true
    }
  },
  "id": 1
}
```

### Responsabilidades del Orquestador

1. ✅ Extraer `client_id` de DynamoDB
2. ✅ Validar que `client_id` existe
3. ✅ Codificar archivo en base64
4. ✅ Inferir `target_rag` (rag1 o rag2)
5. ✅ Invocar Lambda con JSON-RPC bien formado

---

## 6. Sistema Multi-Tenant con Aurora DSQL

**Archivo:** [src/storage/postgres_storage.py](../src/storage/postgres_storage.py)

### Esquema Multi-Tenant: `kb_<client_id>`

**Arquitectura:**
- Cada cliente tiene su propio **schema** en PostgreSQL
- Formato: `kb_<client_id>`
- Ejemplos:
  - `client_id='helpdesk_ivanti'` → schema `kb_helpdesk_ivanti`
  - `client_id='empresa_a'` → schema `kb_empresa_a`
- **Base de datos:** Siempre `postgres` (única DB en Aurora DSQL)

**Validación de client_id** (líneas 68-119):
```python
if not self.client_id:
    raise ValueError("ERROR CRÍTICO: client_id es OBLIGATORIO")

if not client_id.replace('_', '').replace('-', '').isalnum():
    raise ValueError(f"client_id inválido: {client_id}")
```

### Tablas: knowledge_base_rag1 y rag2

#### Tabla RAG1 (Documentos)

**Ubicación:** `kb_<client_id>.knowledge_base_rag1`

**Schema SQL:**
```sql
CREATE TABLE "kb_<client_id>".knowledge_base_rag1 (
    id UUID PRIMARY KEY,
    articulo_id VARCHAR(255) NOT NULL,
    tipo VARCHAR(255) NOT NULL,
    numero SMALLINT NOT NULL CHECK (numero >= 0 AND numero <= 32767),
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    image_caption TEXT,
    keywords TEXT,
    embedding TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices (Aurora DSQL requiere ASYNC)
CREATE INDEX ASYNC idx_<schema>_rag1_articulo_id ON table(articulo_id);
CREATE INDEX ASYNC idx_<schema>_rag1_tipo ON table(tipo);
CREATE INDEX ASYNC idx_<schema>_rag1_created_at ON table(created_at);
```

#### Tabla RAG2 (Servicios/Tickets)

**Ubicación:** `kb_<client_id>.knowledge_base_rag2`

**Schema SQL:**
```sql
CREATE TABLE "kb_<client_id>".knowledge_base_rag2 (
    id UUID PRIMARY KEY,
    descripcion TEXT NOT NULL,
    tipo VARCHAR(255) NOT NULL,
    servicio VARCHAR(255) NOT NULL,
    categoria VARCHAR(255) NOT NULL,
    subcategoria VARCHAR(255) NOT NULL,
    fuente VARCHAR(255) NOT NULL,
    embedding TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX ASYNC idx_<schema>_rag2_tipo ON table(tipo);
CREATE INDEX ASYNC idx_<schema>_rag2_servicio ON table(servicio);
CREATE INDEX ASYNC idx_<schema>_rag2_categoria ON table(categoria);
```

### Autenticación IAM

**Implementación** (líneas 133-160):

```python
def _generate_iam_token(self) -> str:
    """Genera token IAM para Aurora DSQL (válido 15 minutos)"""
    client = boto3.client('dsql', region_name=self.aws_region)

    token = client.generate_db_connect_admin_auth_token(
        Hostname=self.host,
        Region=self.aws_region
    )

    return token

def _get_password(self) -> str:
    """Usa token IAM o contraseña según configuración"""
    if self.use_iam_auth:
        return self._generate_iam_token()  # Token dinámico
    else:
        return self.password  # Password tradicional
```

**Variables de entorno:**
```env
USE_IAM_AUTH=true
AWS_REGION=us-east-2
```

**Dependencias:** `boto3==1.40.60`, `botocore==1.40.60`

### Auto-Provisioning de Schemas y Tablas

**Proceso automático:**

#### 1. Verificar/Crear Schema (líneas 177-230)
```python
async def _ensure_schema_exists(self):
    # Conectar a DB 'postgres'
    conn = await asyncpg.connect(
        host=self.host,
        database='postgres',
        password=self._get_password(),  # Token IAM
        ssl='require'
    )

    # Verificar si schema existe
    schema_exists = await conn.fetchval(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = $1",
        self.schema
    )

    # Crear si no existe
    if not schema_exists and self.auto_create:
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
        logger.info(f"Schema '{self.schema}' creado")
```

#### 2. Verificar/Crear Tablas (líneas 232-275)
```python
async def _ensure_tables_exist(self):
    # Verificar existencia de tablas
    rag1_exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_schema = $1 AND table_name = 'knowledge_base_rag1')",
        self.schema
    )

    # Crear tablas si no existen
    if not rag1_exists:
        await self._create_rag1_table(conn)

    if not rag2_exists:
        await self._create_rag2_table(conn)
```

**Variables de entorno:**
```env
POSTGRES_AUTO_CREATE=true  # Si false, falla si no existen
```

### Limitaciones de Aurora DSQL

- **Solo 1 base de datos:** `postgres` (usa schemas para multi-tenant)
- **Índices ASYNC:** Requiere `CREATE INDEX ASYNC`
- **No soporta:** PL/pgSQL, triggers, advisory locks, GIN indexes
- **SSL obligatorio:** `POSTGRES_SSL=require`

---

## 7. Configuración y Dependencias

### Variables de Entorno

**Archivo:** [.env.example](../.env.example)

#### Azure OpenAI
```env
# API Keys y Endpoints
AZURE_OPENAI_O1MINI_API_KEY=your-api-key
AZURE_OPENAI_O1MINI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_O1MINI_API_VERSION=2024-08-01-preview

# Modelos
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o                      # Texto
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o                    # Visión
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002 # Embeddings
```

#### PostgreSQL / Aurora DSQL
```env
# Conexión
POSTGRES_HOST=<dsql-endpoint>.dsql.us-east-2.on.aws
POSTGRES_PORT=5432
POSTGRES_DB=postgres              # Única DB permitida en Aurora DSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=                # Vacío si usa IAM auth

# Seguridad
POSTGRES_SSL=require              # Obligatorio para Aurora DSQL
USE_IAM_AUTH=true                 # Genera tokens IAM automáticamente
AWS_REGION=us-east-2

# Multi-tenant
POSTGRES_SCHEMA_PREFIX=kb_        # Prefijo para schemas

# Auto-provisioning
POSTGRES_AUTO_CREATE=true         # Crear schema/tablas automáticamente
```

#### Configuración de Aplicación
```env
ENVIRONMENT=development
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=50
SAVE_TO_KNOWLEDGE_BASE=true
```

### Dependencias Principales

**Archivo:** [requirements.txt](../requirements.txt)

```
# Framework Web
fastapi==0.120.1
uvicorn==0.38.0
mangum==0.19.0                    # FastAPI → Lambda adapter

# MCP
mcp==1.20.0
mcp-server==0.1.4

# Datos
pandas==2.3.3
openpyxl==3.1.5                   # Excel
numpy==2.3.4

# AI
openai==2.6.1                     # Azure OpenAI

# Base de Datos
asyncpg==0.31.0                   # PostgreSQL async

# AWS
boto3==1.40.60                    # SDK AWS
botocore==1.40.60                 # Token IAM

# Validación
pydantic==2.12.3
pydantic-settings==2.11.0

# Imágenes
pillow==12.0.0

# Utilidades
python-dotenv==1.2.1
python-multipart==0.0.20
httpx==0.28.1
```

### Instalación Local

```bash
# 1. Crear virtualenv
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar .env
cp .env.example .env
# Editar .env con tus credenciales

# 4. Ejecutar localmente
uvicorn main:app --reload
# Swagger UI: http://localhost:8000/docs
```

### Despliegue en AWS Lambda

```bash
# 1. Build Docker image
docker build -t request-to-standard .

# 2. Push to ECR
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin <ecr-uri>
docker tag request-to-standard:latest <ecr-uri>/request-to-standard:latest
docker push <ecr-uri>/request-to-standard:latest

# 3. Configurar Lambda
# - Runtime: Container
# - Handler: handler.lambda_handler
# - Timeout: 300s
# - Memory: 1024MB
# - Variables de entorno: todas las anteriores
```

### Permisos IAM Necesarios

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dsql:DbConnectAdmin"
      ],
      "Resource": "arn:aws:dsql:us-east-2:*:cluster/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

## Archivos Clave del Proyecto

| Archivo | Descripción |
|---------|-------------|
| `handler.py` | MCP Handler (Lambda entry point) |
| `src/tools/standardize_tool.py` | Tool definition y validación multi-tenant |
| `src/core/pipeline.py` | Orquestador de 7 pasos |
| `src/core/ingestion.py` | Step 1: Ingesta + imágenes |
| `src/core/cleaning.py` | Step 2: Limpieza |
| `src/core/normalization.py` | Step 4: Normalización |
| `src/core/standardization.py` | Step 5: Estandarización LLM + Vision |
| `src/core/validation.py` | Step 6: Validación |
| `src/storage/postgres_storage.py` | Step 7: Storage multi-tenant |
| `src/models/rag1_schema.py` | Schema RAG1 (Pydantic) |
| `src/models/rag2_schema.py` | Schema RAG2 (Pydantic) |
| `src/gpt/client.py` | Cliente Azure OpenAI + Vision |
| `src/utils/image_extractor.py` | Extracción de imágenes XLSX |
| `.env.example` | Variables de entorno |
| `requirements.txt` | Dependencias Python |
| `Dockerfile` | Container para Lambda |

---

## Resumen de Cumplimiento T1.5

| Requisito | Cumplido | Ubicación |
|-----------|----------|-----------|
| Documentar proyecto | ✅ | Sección 1 |
| Diferencia con wrapper | ✅ | Sección 2 |
| Herramientas expuestas | ✅ | Sección 3 |
| Inputs/outputs | ✅ | Secciones 3, 4 |
| Integración Orquestador | ✅ | Sección 5 |
| Aurora DSQL multi-tenant | ✅ | Sección 6 |
| Tablas RAG1 y RAG2 | ✅ | Sección 6 |
| Autenticación IAM | ✅ | Sección 6 |
| Auto-provisioning | ✅ | Sección 6 |
| Pipeline 7 pasos | ✅ | Sección 4 |
| Configuración y dependencias | ✅ | Sección 7 |
