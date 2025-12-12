"""
PostgreSQL Storage - Guarda datos estandarizados como base de conocimiento
Sistema multi-tenant con auto-provisioning de base de datos y tablas
Soporta Aurora DSQL con autenticación IAM automática
"""
import os
import asyncpg
import boto3
from typing import List, Dict, Any, Literal, Optional
from custom_logging import get_logger

logger = get_logger(__name__)


class PostgreSQLStorage:
    """
    Guarda datos estandarizados en PostgreSQL como base de conocimiento

    Características:
    - Multi-tenant: Soporta múltiples clientes/empresas
    - Auto-provisioning: Crea DB y tablas automáticamente si no existen
    - Flexible: Configuración completa por variables de entorno
    """

    def __init__(self, client_id: Optional[str] = None):
        """
        Inicializa conexión a PostgreSQL usando variables de entorno

        Args:
            client_id: ID del cliente/empresa (opcional). Si se provee, se usa para
                      nombrar la base de datos de forma única (ej: kb_cliente1)

        Variables de entorno:
        - POSTGRES_HOST: Host del servidor PostgreSQL
        - POSTGRES_PORT: Puerto (default: 5432)
        - POSTGRES_DB: Nombre base de datos (default: knowledge_base)
        - POSTGRES_USER: Usuario (default: postgres)
        - POSTGRES_PASSWORD: Contraseña (opcional si se usa Aurora DSQL)
        - POSTGRES_DB_PREFIX: Prefijo para bases de datos multi-tenant (default: kb_)
        - POSTGRES_AUTO_CREATE: Auto-crear DB/tablas si no existen (default: true)
        - POSTGRES_SSL: Modo SSL - 'require' (Aurora DSQL), 'prefer', 'disable' (default: require)
        - AWS_REGION: Región de AWS para Aurora DSQL (ej: us-east-2)
        - USE_IAM_AUTH: Usar autenticación IAM para Aurora DSQL (default: false)
        """
        self.host = os.getenv('POSTGRES_HOST', 'localhost')
        self.port = int(os.getenv('POSTGRES_PORT', '5432'))
        self.user = os.getenv('POSTGRES_USER', 'postgres')
        self.password = os.getenv('POSTGRES_PASSWORD', '')

        # SSL configuration (required for Aurora DSQL)
        self.ssl = os.getenv('POSTGRES_SSL', 'require')

        # Aurora DSQL IAM authentication
        self.use_iam_auth = os.getenv('USE_IAM_AUTH', 'false').lower() == 'true'
        self.aws_region = os.getenv('AWS_REGION', 'us-east-2')

        # Aurora DSQL: Usar siempre DB 'postgres' (única DB permitida)
        # Multi-tenant: Usar SCHEMAS en lugar de múltiples DBs
        self.database = os.getenv('POSTGRES_DB', 'postgres')
        
        # ================================================================
        # MULTI-TENANT: client_id es OBLIGATORIO
        # ================================================================
        # NO usamos fallback a variable de entorno para evitar errores
        # de aislamiento entre clientes en producción multi-tenant
        self.client_id = client_id
        
        if not self.client_id:
            raise ValueError(
                "\n"
                "════════════════════════════════════════════════════════════════════════\n"
                "ERROR CRÍTICO: client_id es OBLIGATORIO para PostgreSQLStorage\n"
                "════════════════════════════════════════════════════════════════════════\n"
                "\n"
                "PostgreSQLStorage requiere un client_id explícito para aislamiento\n"
                "multi-tenant. El client_id se usa para crear schemas aislados en\n"
                "PostgreSQL (formato: kb_<client_id>).\n"
                "\n"
                "Esto previene:\n"
                "  ❌ Uso accidental del cliente incorrecto\n"
                "  ❌ Datos guardados en el schema equivocado\n"
                "  ❌ Violaciones de aislamiento entre clientes\n"
                "\n"
                "Solución:\n"
                "  ✅ storage = PostgreSQLStorage(client_id='nombre_cliente')\n"
                "\n"
                "Ejemplo:\n"
                "  storage = PostgreSQLStorage(client_id='helpdesk_ivanti')\n"
                "  # Esto creará/usará el schema: kb_helpdesk_ivanti\n"
                "\n"
                "════════════════════════════════════════════════════════════════════════\n"
            )
        
        # Validar formato de client_id (solo alfanumérico, guiones y guiones bajos)
        if not client_id.replace('_', '').replace('-', '').isalnum():
            raise ValueError(
                f"\n"
                f"════════════════════════════════════════════════════════════════════════\n"
                f"ERROR: client_id tiene formato inválido: '{client_id}'\n"
                f"════════════════════════════════════════════════════════════════════════\n"
                f"\n"
                f"El client_id solo puede contener:\n"
                f"  ✅ Letras (a-z, A-Z)\n"
                f"  ✅ Números (0-9)\n"
                f"  ✅ Guiones (-)\n"
                f"  ✅ Guiones bajos (_)\n"
                f"\n"
                f"Ejemplos válidos:\n"
                f"  ✅ helpdesk_ivanti\n"
                f"  ✅ empresa-a\n"
                f"  ✅ cliente123\n"
                f"\n"
                f"Ejemplos inválidos:\n"
                f"  ❌ cliente@empresa (contiene @)\n"
                f"  ❌ cliente.123 (contiene .)\n"
                f"  ❌ cliente/test (contiene /)\n"
                f"\n"
                f"════════════════════════════════════════════════════════════════════════\n"
            )
        
        logger.info(f"[MULTI-TENANT] client_id validado: '{self.client_id}'")
        
        schema_prefix = os.getenv('POSTGRES_SCHEMA_PREFIX', 'kb_')
        
        # Schema específico del cliente: kb_empresa1
        self.schema = f"{schema_prefix}{self.client_id}"
        logger.info(f"[MULTI-TENANT] Schema PostgreSQL: '{self.schema}' en DB '{self.database}'")

        self.auto_create = os.getenv('POSTGRES_AUTO_CREATE', 'true').lower() == 'true'
        self.pool: Optional[asyncpg.Pool] = None
        self._db_initialized = False

    def _generate_iam_token(self) -> str:
        """
        Genera un token de autenticación IAM para Aurora DSQL.

        Este token es válido por 15 minutos y se genera usando las credenciales
        de AWS configuradas en tu máquina (AWS CLI).

        Returns:
            Token de autenticación para usar como contraseña
        """
        try:
            client = boto3.client('dsql', region_name = self.aws_region)

            # Generar token usando la acción DbConnectAdmin
            token = client.generate_db_connect_admin_auth_token(
                Hostname=self.host,
                Region=self.aws_region
            )

            logger.info(f"Token IAM generado exitosamente para {self.host}")
            return token

        except Exception as e:
            logger.error(f"Error generando token IAM: {e}", exc_info=True)
            raise Exception(
                f"No se pudo generar token IAM para Aurora DSQL. "
                f"Verifica que AWS CLI esté configurado correctamente: {e}"
            )

    def _get_password(self) -> str:
        """
        Obtiene la contraseña a usar para la conexión.

        Si USE_IAM_AUTH=true, genera un token IAM automáticamente.
        Si no, usa la contraseña de la variable de entorno.

        Returns:
            Contraseña o token IAM
        """
        if self.use_iam_auth:
            return self._generate_iam_token()
        else:
            return self.password

    async def _ensure_schema_exists(self):
        """
        Verifica si el schema existe, y lo crea si no existe.

        Aurora DSQL solo permite la DB 'postgres', pero soporta múltiples schemas.
        Este método verifica/crea el schema para multi-tenant.
        """
        if self._db_initialized:
            return

        logger.info(f"Verificando existencia de schema '{self.schema}'...")

        # Conectar a la DB 'postgres' (única DB en Aurora DSQL)
        try:
            # Generar token IAM si es necesario
            password = self._get_password()

            conn = await asyncpg.connect(
                host = self.host,
                port = self.port,
                database = self.database,  # postgres
                user = self.user,
                password = password,
                ssl = self.ssl  # SSL requerido para Aurora DSQL
            )

            try:
                # Verificar si el schema existe
                schema_exists = await conn.fetchval(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = $1",
                    self.schema
                )

                if schema_exists:
                    logger.info(f"Schema '{self.schema}' ya existe")
                else:
                    if self.auto_create:
                        logger.info(f"Creando schema '{self.schema}'...")
                        # Crear el schema
                        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
                        logger.info(f"Schema '{self.schema}' creado exitosamente")
                    else:
                        raise Exception(
                            f"Schema '{self.schema}' no existe y POSTGRES_AUTO_CREATE=false"
                        )

            finally:
                await conn.close()

            self._db_initialized = True

        except Exception as e:
            logger.error(f"Error verificando/creando schema: {e}", exc_info=True)
            raise

    async def _ensure_tables_exist(self):
        """
        Verifica si las tablas existen en el schema, y las crea si no existen.

        Crea las tablas knowledge_base_rag1 y knowledge_base_rag2 dentro del
        schema específico del cliente (o 'public' si no hay client_id).
        """
        # Usar el pool directamente (ya fue creado en _get_connection_pool)
        async with self.pool.acquire() as conn:
            # Verificar si las tablas existen en el schema
            rag1_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = $1
                    AND table_name = 'knowledge_base_rag1'
                )
            """, self.schema)

            rag2_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = $1
                    AND table_name = 'knowledge_base_rag2'
                )
            """, self.schema)

            if rag1_exists and rag2_exists:
                logger.info("Tablas knowledge_base_rag1 y rag2 ya existen")
                return

            if not self.auto_create:
                raise Exception("Tablas no existen y POSTGRES_AUTO_CREATE=false")

            logger.info("Creando tablas de knowledge base...")

            # Crear tabla RAG1
            if not rag1_exists:
                await self._create_rag1_table(conn)
                logger.info("Tabla knowledge_base_rag1 creada")

            # Crear tabla RAG2
            if not rag2_exists:
                await self._create_rag2_table(conn)
                logger.info("Tabla knowledge_base_rag2 creada")

    async def _create_rag1_table(self, conn: asyncpg.Connection):
        """Crea la tabla knowledge_base_rag1 en el schema especificado"""
        table_name = f'"{self.schema}".knowledge_base_rag1'

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
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
            )
        """)

        # Índices (Aurora DSQL requiere CREATE INDEX ASYNC)
        # Aurora DSQL NO soporta: USING gin, DESC/ASC, to_tsvector
        # Solo soporta índices B-tree básicos
        try:
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag1_articulo_id ON {table_name}(articulo_id)")
        except Exception as e:
            logger.warning(f"Error creando índice articulo_id (puede ya existir): {e}")

        try:
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag1_tipo ON {table_name}(tipo)")
        except Exception as e:
            logger.warning(f"Error creando índice tipo (puede ya existir): {e}")

        try:
            # Aurora DSQL no soporta DESC en índices
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag1_created_at ON {table_name}(created_at)")
        except Exception as e:
            logger.warning(f"Error creando índice created_at (puede ya existir): {e}")

        # Aurora DSQL no soporta full-text search con GIN indices
        # Si necesitas búsqueda de texto, deberás usar LIKE/ILIKE queries

        # Aurora DSQL NO soporta PL/pgSQL ni triggers
        # El campo updated_at se actualizará manualmente en las queries UPDATE

    async def _create_rag2_table(self, conn: asyncpg.Connection):
        """Crea la tabla knowledge_base_rag2 en el schema especificado"""
        table_name = f'"{self.schema}".knowledge_base_rag2'

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
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
            )
        """)

        # Índices (Aurora DSQL requiere CREATE INDEX ASYNC)
        # Aurora DSQL NO soporta: USING gin, DESC/ASC, to_tsvector
        # Solo soporta índices B-tree básicos
        try:
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag2_tipo ON {table_name}(tipo)")
        except Exception as e:
            logger.warning(f"Error creando índice tipo (puede ya existir): {e}")

        try:
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag2_servicio ON {table_name}(servicio)")
        except Exception as e:
            logger.warning(f"Error creando índice servicio (puede ya existir): {e}")

        try:
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag2_categoria ON {table_name}(categoria)")
        except Exception as e:
            logger.warning(f"Error creando índice categoria (puede ya existir): {e}")

        try:
            # Aurora DSQL no soporta DESC en índices
            await conn.execute(f"CREATE INDEX ASYNC IF NOT EXISTS idx_{self.schema}_rag2_created_at ON {table_name}(created_at)")
        except Exception as e:
            logger.warning(f"Error creando índice created_at (puede ya existir): {e}")

        # Aurora DSQL no soporta full-text search con GIN indices
        # Si necesitas búsqueda de texto, deberás usar LIKE/ILIKE queries

        # Aurora DSQL NO soporta PL/pgSQL ni triggers
        # El campo updated_at se actualizará manualmente en las queries UPDATE

    async def _get_connection_pool(self) -> asyncpg.Pool:
        """
        Crea o retorna el pool de conexiones existente.

        Auto-provisioning: Antes de crear el pool, verifica/crea schema y tablas.
        """
        if self.pool is None:
            # PASO 1: Asegurar que el schema exista
            await self._ensure_schema_exists()

            # PASO 2: Crear pool de conexiones a la DB
            # Generar token IAM si es necesario
            password = self._get_password()

            # Aurora DSQL no soporta pg_advisory_unlock_all que asyncpg usa en el reset
            # Solución: proporcionar una función reset personalizada que no use advisory locks
            async def aurora_dsql_reset(conn):
                """Reset personalizado para Aurora DSQL sin advisory locks"""
                # Aurora DSQL no soporta DISCARD ALL ni advisory locks
                # Solo hacer un reset básico de transacción
                try:
                    await conn.execute('ROLLBACK')
                except:
                    pass

            self.pool = await asyncpg.create_pool(
                host = self.host,
                port = self.port,
                database = self.database,
                user = self.user,
                password = password,
                ssl = self.ssl,  # SSL requerido para Aurora DSQL
                min_size = 2,
                max_size = 10,
                command_timeout = 60,
                reset = aurora_dsql_reset  # Función reset personalizada para Aurora DSQL
            )
            logger.info(f"Pool de conexiones creado: {self.host}:{self.port}/{self.database}")
            # PASO 3: Asegurar que las tablas existan
            await self._ensure_tables_exist()

        return self.pool

    async def close(self):
        """Cierra el pool de conexiones"""
        if self.pool:
            await self.pool.close()
            logger.info("Pool de conexiones PostgreSQL cerrado")

    def _convert_embedding_to_pgvector(self, embedding: Optional[List[float]]) -> Optional[str]:
        """
        Convierte lista de floats a formato pgvector string

        Args:
            embedding: Lista de floats o None

        Returns:
            String en formato '[0.1, 0.2, ...]' o None
        """
        if embedding is None:
            return None

        # Convertir lista a string formato pgvector: '[0.1, 0.2, 0.3]'
        return '[' + ','.join(str(x) for x in embedding) + ']'

    async def save_to_knowledge_base(
        self,
        records: List[Dict[str, Any]],
        rag_type: Literal["rag1", "rag2"]
    ) -> Dict[str, Any]:
        """
        Guarda registros estandarizados en PostgreSQL

        Args:
            records: Lista de registros ya estandarizados (salida del pipeline)
            rag_type: Tipo de RAG ("rag1" o "rag2")

        Returns:
            Resultado de la operación con estadísticas
        """
        if not records:
            logger.warning("No hay registros para guardar")
            return {
                "table": f"knowledge_base_{rag_type}",
                "total_records": 0,
                "saved": 0,
                "failed": 0,
                "errors": None
            }

        pool = await self._get_connection_pool()
        table_name = f"knowledge_base_{rag_type}"

        saved_count = 0
        failed_count = 0
        errors = []

        logger.info(f"Guardando {len(records)} registros en tabla '{table_name}'")

        async with pool.acquire() as conn:
            async with conn.transaction():
                for record in records:
                    try:
                        if rag_type == "rag1":
                            await self._insert_rag1(conn, record)
                        else:
                            await self._insert_rag2(conn, record)

                        saved_count += 1

                    except Exception as e:
                        failed_count += 1
                        error_msg = f"Error guardando registro {record.get('id')}: {str(e)}"
                        errors.append({
                            "record_id": record.get("id"),
                            "error": str(e)
                        })
                        logger.error(error_msg)
                        # Continuar con los demás registros

        logger.info(f"Guardado completado: {saved_count} exitosos, {failed_count} fallidos en '{table_name}'")

        return {
            "table": table_name,
            "total_records": len(records),
            "saved": saved_count,
            "failed": failed_count,
            "errors": errors if errors else None
        }

    async def _insert_rag1(self, conn: asyncpg.Connection, record: Dict[str, Any]):
        """
        Inserta un registro RAG1 en PostgreSQL

        Args:
            conn: Conexión a PostgreSQL
            record: Registro con schema RAG1
        """
        table_name = f'"{self.schema}".knowledge_base_rag1'

        query = f"""
            INSERT INTO {table_name} (
                id, articulo_id, tipo, numero, titulo, texto,
                image_caption, keywords, embedding
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
            )
            ON CONFLICT (id) DO UPDATE SET
                articulo_id = EXCLUDED.articulo_id,
                tipo = EXCLUDED.tipo,
                numero = EXCLUDED.numero,
                titulo = EXCLUDED.titulo,
                texto = EXCLUDED.texto,
                image_caption = EXCLUDED.image_caption,
                keywords = EXCLUDED.keywords,
                embedding = EXCLUDED.embedding,
                updated_at = CURRENT_TIMESTAMP
        """

        # Convertir embedding a formato pgvector
        embedding_str = self._convert_embedding_to_pgvector(record.get('embedding'))

        await conn.execute(
            query,
            record.get('id'),
            record.get('articulo_id'),
            record.get('tipo'),
            record.get('numero'),
            record.get('titulo'),
            record.get('texto'),
            record.get('image_caption'),
            record.get('keywords'),
            embedding_str  # String formato '[0.1, 0.2, ...]' o None
        )

    async def _insert_rag2(self, conn: asyncpg.Connection, record: Dict[str, Any]):
        """
        Inserta un registro RAG2 en PostgreSQL

        Args:
            conn: Conexión a PostgreSQL
            record: Registro con schema RAG2
        """
        table_name = f'"{self.schema}".knowledge_base_rag2'

        query = f"""
            INSERT INTO {table_name} (
                id, descripcion, tipo, servicio, categoria,
                subcategoria, fuente, embedding
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8
            )
            ON CONFLICT (id) DO UPDATE SET
                descripcion = EXCLUDED.descripcion,
                tipo = EXCLUDED.tipo,
                servicio = EXCLUDED.servicio,
                categoria = EXCLUDED.categoria,
                subcategoria = EXCLUDED.subcategoria,
                fuente = EXCLUDED.fuente,
                embedding = EXCLUDED.embedding,
                updated_at = CURRENT_TIMESTAMP
        """

        # Convertir embedding a formato pgvector
        embedding_str = self._convert_embedding_to_pgvector(record.get('embedding'))

        await conn.execute(
            query,
            record.get('id'),
            record.get('descripcion'),
            record.get('tipo'),
            record.get('servicio'),
            record.get('categoria'),
            record.get('subcategoria'),
            record.get('fuente'),
            embedding_str  # String formato '[0.1, 0.2, ...]' o None
        )

    async def get_record_by_id(
        self,
        record_id: str,
        rag_type: Literal["rag1", "rag2"]
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene un registro por ID

        Args:
            record_id: UUID del registro
            rag_type: Tipo de RAG

        Returns:
            Registro o None si no existe
        """
        pool = await self._get_connection_pool()
        table_name = f'"{self.schema}".knowledge_base_{rag_type}'

        async with pool.acquire() as conn:
            query = f"SELECT * FROM {table_name} WHERE id = $1"
            row = await conn.fetchrow(query, record_id)

            if row:
                return dict(row)
            return None

    async def search_by_keywords(
        self,
        keywords: str,
        rag_type: Literal["rag1", "rag2"],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda por palabras clave usando ILIKE (Aurora DSQL no soporta full-text search)

        Aurora DSQL no soporta to_tsvector, plainto_tsquery, ni ts_rank.
        Usamos ILIKE como alternativa más simple.

        Args:
            keywords: Palabras clave a buscar
            rag_type: Tipo de RAG
            limit: Máximo de resultados

        Returns:
            Lista de registros que coinciden
        """
        pool = await self._get_connection_pool()
        table_name = f'"{self.schema}".knowledge_base_{rag_type}'

        # Preparar patrón de búsqueda: '%keyword%'
        search_pattern = f'%{keywords}%'

        async with pool.acquire() as conn:
            if rag_type == "rag1":
                # Buscar en texto, titulo y keywords usando ILIKE
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE texto ILIKE $1
                       OR titulo ILIKE $1
                       OR keywords ILIKE $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """
            else:
                # Buscar en descripcion usando ILIKE
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE descripcion ILIKE $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """

            rows = await conn.fetch(query, search_pattern, limit)
            return [dict(row) for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la base de conocimiento

        Returns:
            Diccionario con estadísticas
        """
        pool = await self._get_connection_pool()
        rag1_table = f'"{self.schema}".knowledge_base_rag1'
        rag2_table = f'"{self.schema}".knowledge_base_rag2'

        async with pool.acquire() as conn:
            rag1_count = await conn.fetchval(f"SELECT COUNT(*) FROM {rag1_table}")
            rag2_count = await conn.fetchval(f"SELECT COUNT(*) FROM {rag2_table}")

            # Contar registros con imágenes (RAG1)
            rag1_with_images = await conn.fetchval(
                f"SELECT COUNT(*) FROM {rag1_table} WHERE image_caption IS NOT NULL"
            )

            # Contar registros con embeddings
            rag1_with_embeddings = await conn.fetchval(
                f"SELECT COUNT(*) FROM {rag1_table} WHERE embedding IS NOT NULL"
            )
            rag2_with_embeddings = await conn.fetchval(
                f"SELECT COUNT(*) FROM {rag2_table} WHERE embedding IS NOT NULL"
            )

        return {
            "total_records": rag1_count + rag2_count,
            "rag1": {
                "total": rag1_count,
                "with_images": rag1_with_images,
                "with_embeddings": rag1_with_embeddings
            },
            "rag2": {
                "total": rag2_count,
                "with_embeddings": rag2_with_embeddings
            }
        }