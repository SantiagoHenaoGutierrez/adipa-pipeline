# ADIPA Pipeline — Sincronización de Tipos de Cambio y Precios

Sistema de orquestación de pipelines con **Prefect** que mantiene actualizados los precios
localizados de cursos de psicología para estudiantes en Chile, México, Colombia y Argentina.

---

## El problema de negocio

ADIPA vende cursos con precio base en USD. Los precios se muestran en moneda local según el
país del estudiante. Si el tipo de cambio varía significativamente, los precios localizados
quedan desactualizados — generando pérdida de margen o espantando estudiantes con precios
que no reflejan la realidad.

**Solución:** dos pipelines encadenados. Uno liviano que recolecta tipos de cambio cada
15 minutos. Uno pesado que cada día consume ese acumulado, calcula precios locales por curso
y país, y genera alertas cuando la variación supera el 5%.

**Países cubiertos:** Chile (CLP), México (MXN), Colombia (COP), Argentina (ARS)

---

## Por qué Prefect y no Airflow

Airflow es el estándar de la industria para equipos grandes con pipelines complejos y
dedicados de ingeniería de datos. Prefect resuelve el mismo problema con un modelo mental
más simple, y esa diferencia importa mucho en equipos pequeños.

**Las razones concretas:**

**Setup y operación.** Airflow requiere un scheduler, un webserver, un executor, una base
de datos de metadatos propia y en producción típicamente Celery o Kubernetes como executor.
Son cinco componentes para mantener. Prefect en su modo `serve()` (usado aquí) es un único
proceso Python que se registra contra el servidor — dos componentes: el servidor y el worker.
La diferencia en overhead operacional es significativa cuando no hay un equipo dedicado de
infraestructura.

**El código es Python normal.** En Airflow los DAGs tienen restricciones de ejecución
importantes: el archivo del DAG se importa constantemente para detectar cambios, lo que
significa que no puedes tener código con efectos secundarios en el nivel del módulo, las
fechas de ejecución funcionan con un modelo de "data interval" que confunde a todos la
primera vez, y la parametrización requiere `Jinja templating` mezclado con Python. En
Prefect decorás una función normal con `@flow` y la llamás como cualquier función Python.
El modelo mental es cero fricción.

**Reintentos y observabilidad.** Ambas herramientas tienen reintentos configurables. La
diferencia es que en Prefect se configuran directamente en el decorador `@task(retries=3,
retry_delay_seconds=[1, 2, 4])` — está en el código, visible, versionado en git. En Airflow
se configuran en múltiples lugares y el comportamiento varía según el executor.

**Cuándo elegiría Airflow.** Si el equipo ya lo opera, si hay necesidad de dependencias
complejas entre DAGs de distintos equipos, o si la escala requiere miles de tareas
concurrentes con Kubernetes executor. Para el perfil de ADIPA (pipelines claros, equipo
pequeño, setup rápido), Prefect es la elección correcta.

---

## Decisiones técnicas

**`open.er-api.com` como fuente de tipos de cambio.**
API gratuita, sin API key, sin límites de rate. Cubre las cuatro monedas latinoamericanas
necesarias (CLP, MXN, COP, ARS). Se descartó `frankfurter.app` porque solo cubre monedas
del Banco Central Europeo, que no incluye CLP, COP ni ARS.

**PostgreSQL como storage.**
Persistencia garantizada, queries complejos para promedios diarios, y soporte de constraints
`UNIQUE` que son la base de la estrategia de idempotencia. No es Redis (no persiste en disco
por defecto) ni SQLite (no soporta concurrencia real).

**Contenedor HTTP para aislar el pipeline pesado.**
El worker de Prefect no tiene Pandas instalado — su imagen es liviana. El procesamiento
pesado corre en un contenedor separado (`heavy-worker`) con FastAPI + Pandas, que expone
`POST /process`. El orquestador lo llama por HTTP y espera la respuesta. Esto significa que
el worker de Prefect no acumula dependencias pesadas, el heavy-worker puede escalarse
independientemente, y si el procesamiento falla, el orquestador recibe un error HTTP claro.

**psycopg2 directo, sin ORM.**
Control total sobre los queries. Los UPSERTs con `ON CONFLICT` son explícitos y legibles.
Un ORM abstraería esa lógica y haría menos obvio qué pasa con los duplicados — que es
exactamente lo más crítico del sistema.

---

## Cómo levantar el proyecto

**Requisitos previos:**
- Docker Desktop instalado y corriendo
- `make` disponible (Linux/Mac: nativo; Windows: Git Bash o WSL)

**Pasos:**

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/adipa-pipeline.git
cd adipa-pipeline

# 2. Crear el archivo de configuración
cp .env.example .env
# Los valores por defecto funcionan para desarrollo local sin modificar nada

# 3. Levantar todos los servicios
make up
# Construye las imágenes, levanta los 4 contenedores y espera que estén healthy
# Primera vez puede tardar 2-3 minutos descargando imágenes base

# 4. Verificar que todo está corriendo
docker compose ps
# Todos los servicios deben mostrar "healthy" o "running"

# 5. Verificar que los flows están registrados
docker compose logs prefect-worker
# Debes ver: "Your deployments are being served and polling for scheduled runs!"
```

**Desde este punto los pipelines corren solos según su schedule.** Para probar manualmente:

```bash
# Ejecutar el pipeline liviano (trae tipos de cambio ahora)
make run-light

# Ejecutar el pipeline pesado (calcula precios con los datos del liviano)
make run-heavy
```

**UI de Prefect:** abrir `http://localhost:4200` en el navegador.
- **Deployments** → los dos pipelines con sus schedules
- **Flow Runs** → historial de ejecuciones con logs
- Botón **Run** en cualquier deployment para trigger manual

---

## Cómo verificar que funciona

```bash
# Entrar a la base de datos
make shell-db
```

**1. Tipos de cambio capturados por el pipeline liviano:**

```sql
SELECT currency_to, rate, window_start
FROM exchange_rates
ORDER BY window_start DESC
LIMIT 8;
-- Resultado esperado: 4 filas (CLP, MXN, COP, ARS) por cada ventana de 15 min
```

**2. Precios calculados por el pipeline pesado:**

```sql
SELECT
    c.title,
    cp.country,
    cp.currency,
    cp.price_local,
    cp.exchange_rate_used,
    cp.variation_pct
FROM course_prices cp
JOIN courses c ON c.id = cp.course_id
WHERE cp.calculated_date = CURRENT_DATE
ORDER BY c.title, cp.country;
-- Resultado esperado: 20 filas (5 cursos × 4 países)
```

**3. Alertas de variación significativa (>5%):**

```sql
SELECT
    c.title,
    pa.country,
    pa.previous_price,
    pa.current_price,
    pa.variation_pct,
    pa.alert_date
FROM price_alerts pa
JOIN courses c ON c.id = pa.course_id
ORDER BY ABS(pa.variation_pct) DESC;
-- Aparecen a partir del segundo día de ejecución
```

**4. Verificar idempotencia — correr el pipeline dos veces no debe duplicar datos:**

```sql
SELECT currency_from, currency_to, window_start, COUNT(*)
FROM exchange_rates
GROUP BY currency_from, currency_to, window_start
HAVING COUNT(*) > 1;
-- Resultado esperado: 0 filas (el UNIQUE constraint rechaza duplicados)
```

**5. Ver el promedio diario de tasas que usa el pipeline pesado:**

```sql
SELECT
    currency_to,
    DATE(window_start AT TIME ZONE 'UTC') AS fecha,
    AVG(rate)::NUMERIC(12, 4) AS avg_rate,
    COUNT(*) AS muestras
FROM exchange_rates
GROUP BY currency_to, DATE(window_start AT TIME ZONE 'UTC')
ORDER BY fecha DESC, currency_to;
```

---

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `POSTGRES_USER` | `adipa` | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | `adipa_secret` | Contraseña de PostgreSQL |
| `POSTGRES_DB` | `adipa_db` | Nombre de la base de datos |
| `POSTGRES_HOST` | `postgres` | Host de PostgreSQL (nombre del servicio en Docker) |
| `POSTGRES_PORT` | `5432` | Puerto de PostgreSQL |
| `PREFECT_API_URL` | `http://prefect-server:4200/api` | URL del servidor Prefect |
| `HEAVY_WORKER_URL` | `http://heavy-worker:8000` | URL del heavy-worker |
| `ALERT_THRESHOLD_PCT` | `5.0` | Umbral de variación para generar alertas (%) |
| `LOG_LEVEL` | `INFO` | Nivel de logging (DEBUG, INFO, WARNING, ERROR) |
| `ENVIRONMENT` | `development` | Entorno de ejecución |

---

## Comandos disponibles

```bash
make up           # Construir imágenes y levantar todos los servicios
make down         # Bajar todos los servicios
make logs         # Ver logs de todos los servicios en tiempo real
make logs-worker  # Ver logs solo del prefect-worker
make shell-db     # Abrir psql dentro del contenedor de postgres
make run-light    # Ejecutar el pipeline liviano manualmente
make run-heavy    # Ejecutar el pipeline pesado manualmente
make deploy-flows # Reiniciar el worker (re-registra los deployments)
make reset        # Bajar, borrar volúmenes y volver a levantar desde cero
```

---

## Segunda iteración — qué haría a continuación

**Notificaciones activas.** Las alertas hoy se persisten en la tabla `price_alerts` pero no
se envían. El siguiente paso es integrar Slack o SendGrid: cuando el pipeline pesado detecta
una variación >5%, además de insertar en la DB, envía un mensaje al canal de pricing del
equipo.

**Migraciones versionadas.** El schema hoy se crea con `init.sql` que corre una sola vez.
Si necesito agregar una columna, tengo que hacer `make reset` (borrar todo) o aplicar el
ALTER manualmente. Con Alembic o Flyway cada cambio de schema es un archivo versionado que
se aplica incrementalmente.

**Tests.** El pipeline pesado tiene lógica de negocio que merece tests: el cálculo de
`variation_pct`, la detección del umbral, el manejo del caso sin datos del día anterior.
Usaría pytest con fixtures de Pandas y testcontainers para PostgreSQL real en los tests
de integración.

**CI/CD.** GitHub Actions que corra los tests en cada PR, construya las imágenes Docker y
las publique en un registro. En merge a main, despliegue automático a la VM.

**Backfill.** Un comando `make backfill DATE=2026-01-15` que recalcule precios para una
fecha histórica. Útil cuando el pipeline pesado falla un día y hay que recuperar el dato
sin tocar el código.

**Configuración de mercados dinámica.** El mapa país→moneda está hardcodeado en
`price_calculator.py`. Moviéndolo a una tabla `markets` en la DB, agregar Chile Norte como
mercado separado o incorporar Perú (PEN) sería un INSERT, no un deploy.
