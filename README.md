# AlertFlow - InfoDengue ETL Pipeline

Airflow-based ETL system for the InfoDengue epidemiological surveillance project.

## Prerequisites

- Docker & Docker Compose
- GNU Make
- Python 3.14 (for local development)
- Conda/Mamba

## Quick Start

### 1. Environment Setup

Create `.env` file in the project root and populate the variables:

```bash
envsubst < .env.tpl > .env
```

Generate Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Build Containers

```bash
docker compose build
```

The build process:
- Uses multi-stage Dockerfile
- Installs system dependencies (git, postgres-client, build tools)
- Installs Python dependencies via Poetry
- Configures Airflow with Celery executor

### 3. Start Services

```bash
docker compose up -d
```

Services started:
- **postgres** - Metadata database (port 5432)
- **redis** - Message broker (port 6379)
- **airflow-webserver** - API server (port 8080)
- **airflow-scheduler** - DAG scheduler
- **airflow-worker** - Celery worker
- **airflow-dag-processor** - DAG file processor
- **airflow-triggerer** - Deferrable task triggerer

### 4. Initialize Airflow

On first run, the `airflow-init` service:
1. Creates admin user
2. Runs database migrations
3. Sets up connections and variables

Check initialization:
```bash
docker compose logs airflow-init
```

### 5. Access Airflow UI

Open: http://localhost:${AIRFLOW_PORT}/alertflow

Default credentials (set in `.env`):
- Username: (set via `_AIRFLOW_WWW_USER_USERNAME`)
- Password: (set via `_AIRFLOW_WWW_USER_PASSWORD`)

## Development Workflow

### Project Structure

```
AlertFlow/
├── alertflow/
│   ├── dags/              # Airflow DAG definitions
│   ├── plugins/           # Custom plugins
│   └── logs/              # Task logs
├── docker/
│   ├── compose.yaml       # Main compose file
│   ├── compose-dev.yaml   # Development overrides
│   └── Dockerfile         # Container image definition
├── pyproject.toml         # Python dependencies (Poetry)
├── Makefile               # Build/test automation
└── .env                   # Environment variables (not committed)
```

### Adding DAGs

Place DAG files in `alertflow/dags/`:
- Changes detected automatically (30s interval)
- No container restart needed
- View parsed DAGs at http://localhost:${AIRFLOW_PORT}/alertflow

### Running CLI Commands

```bash
./airflow.sh dags list
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f airflow-webserver
```

### Restarting Services

```bash
# All services
docker compose restart
# or:
docker compose down && docker compose up -d
```

## Configuration

### Airflow Config

Override any config via environment variables in `docker-compose.yaml`:

```yaml
environment:
  AIRFLOW__CORE__EXECUTOR: CeleryExecutor
  AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
```

## Common Tasks

### Database Migrations

```bash
docker compose run --rm airflow-cli db migrate
```

### Create Admin User

```bash
docker compose run --rm airflow-cli users create \
  --username admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com \
  --password admin
```

## Troubleshooting

### Port Already in Use

```bash
# Change port in .env
echo "AIRFLOW_PORT=8081" >> .env
docker compose -f docker-compose.yaml down
docker compose -f docker-compose.yaml up -d
```

### Database Connection Issues

```bash
# Check postgres health
docker compose exec postgres pg_isready -U airflow

# Reset database (WARNING: destroys data)
docker compose down -v
docker volume rm alertflow_postgres-db-volume
docker compose up -d
```

### View Container Resource Usage

```bash
docker stats
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make build` | Build all container images |
| `make up` | Start all services in background |
| `make down` | Stop all services |
| `make restart` | Restart all services |
| `make logs` | Tail logs from all services |

## InfoDengue Specific

This setup is tailored for the InfoDengue ETL pipeline:
- Processes epidemiological data for dengue, zika, chikungunya
- Integrates with climate data APIs (COPERNICUS)
- Uses geospatial analysis for disease mapping
- Outputs feed the InfoDengue dashboard

For more details on the ETL pipeline, see `alertflow/dags/`.
