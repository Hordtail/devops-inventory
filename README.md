# DevOps Inventory

A containerized inventory management application built with React, FastAPI and PostgreSQL, deployed through an automated CI/CD pipeline to a Raspberry Pi.

The project combines full-stack application development with practical DevOps practices, including Docker, GitHub Actions, multi-architecture container images, Ansible automation and infrastructure monitoring.

> **Project status: Beta**
>
> This project is under active development. Features and deployment configuration may evolve.

## Overview

DevOps Inventory is a web application for managing server inventories and tracking stock levels of inventory items.

It provides a centralized interface to manage inventory records, monitor available quantities and maintain a history of stock movements.

The project also serves as a practical DevOps implementation, covering containerization, automated testing, image publishing, infrastructure automation and monitoring.

## Features

### Inventory management

- Create and update inventory items.
- Manage item codes, names, descriptions and units.
- Configure minimum stock levels.
- Track available quantities.
- Activate and deactivate items.
- Upload and display item images.
- View individual item details.

### Stock management

- Register incoming stock movements.
- Register outgoing stock movements.
- Maintain a history of movements for each item.
- Prevent stock operations that exceed available quantities.
- Record movement dates and optional notes.

### Server management

- Create, update and delete server records.
- Retrieve server inventory information through the API.

### Monitoring

- Expose application metrics through Prometheus.
- Monitor Raspberry Pi system resources using Node Exporter.
- Visualize monitoring data with Grafana.

## Architecture

The application and monitoring services run in separate Docker Compose projects.

```mermaid
flowchart LR
    User[User / Browser]

    subgraph Application[Application stack]
        Nginx[Nginx<br/>React static files + reverse proxy]
        API[FastAPI]
        DB[(PostgreSQL)]
        Nginx -->|Web app files| User
        User -->|/api requests| Nginx
        Nginx -->|/api to API| API
        API --> DB
    end

    subgraph Monitoring[Monitoring stack]
        Prometheus[Prometheus]
        Grafana[Grafana]
        NodeExporter[Node Exporter]
        Prometheus -->|scrapes /metrics| API
        Prometheus -->|scrapes :9100| NodeExporter
        Grafana -->|queries| Prometheus
    end
```

### Application components

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React, TypeScript, Vite | User interface |
| Web server | Nginx | Serves built React static files and reverse proxies `/api` requests to FastAPI |
| Backend | FastAPI | REST API and application logic |
| Database | PostgreSQL 18 | Persistent application data |
| ORM | SQLAlchemy | Database access |
| Migrations | Alembic | Database schema management |
| Containers | Docker | Application packaging and execution |
| Monitoring | Prometheus | Metrics collection |
| Visualization | Grafana | Monitoring dashboards |
| System metrics | Node Exporter | Host resource monitoring |
| Automation | Ansible | Infrastructure configuration and deployment |
| CI/CD | GitHub Actions | Testing, building, publishing and deployment |
| Container registry | GitHub Container Registry | Docker image storage |
| Private connectivity | Tailscale | Secure runner-to-Raspberry connectivity |

### Application communication

In local development, Vite proxies `/api` requests to the FastAPI service running on port `8000`.

In production, Nginx serves the React build and forwards `/api` requests to the API container through the internal Docker network. FastAPI communicates with PostgreSQL over that network.

PostgreSQL is not exposed on a host port in the production Compose configuration.

## Repository structure

```text
devops-inventory/
├── .github/
│   └── workflows/
│       └── ci.yml
├── ansible/
│   ├── inventory/
│   ├── playbooks/
│   └── roles/
│       ├── common/
│       ├── docker/
│       ├── inventory/
│       └── monitoring/
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── inventory-api/
│   ├── alembic/
│   ├── app/
│   │   ├── metrics/
│   │   ├── routers/
│   │   └── services/
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── .env.example
├── LICENSE
└── README.md
```

## Requirements

For local development:

- Git
- Docker Engine
- Docker Compose plugin
- Node.js 24 or compatible version (for running Vite locally)
- npm (for running Vite locally)

The backend and database run in Docker, so a local Python installation is not required for the standard development workflow. The frontend can also be built with its Dockerfile without installing Node.js locally.

## Local development

The local development setup runs PostgreSQL and FastAPI using Docker Compose, while the frontend can run through the Vite development server.

### 1. Clone the repository

```bash
git clone https://github.com/Hordtail/devops-inventory.git
cd devops-inventory
```

### 2. Configure environment variables

Create the backend Compose environment file:

```bash
cp inventory-api/.env.example inventory-api/.env
```

Edit `inventory-api/.env` and set a local PostgreSQL password. The example file also contains `GHCR_OWNER` and `IMAGE_TAG`, which are used by the production Compose configuration.

```env
POSTGRES_DB=inventory
POSTGRES_USER=devops
POSTGRES_PASSWORD=change_me
```

Do not commit `.env` files or production credentials.

### 3. Start PostgreSQL and the API

```bash
cd inventory-api
docker compose -p inventory-api up -d --build
```

This starts:

| Service | Address |
|---|---|
| FastAPI | http://localhost:8000 |
| PostgreSQL | `127.0.0.1:15432` |

The API container applies pending Alembic migrations before starting FastAPI. The PostgreSQL initialization script creates the `inventory_test` database on first initialization of its data volume.

Check the API health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

### 4. Start the frontend with Vite

Open another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the application at http://localhost:5173. Vite proxies `/api` requests to the backend on port `8000`.

### Alternative: build the frontend with Docker

From the repository root, start the backend and database from `inventory-api/`, then build and run the frontend image without installing Node.js locally:

```bash
docker build -t inventory-frontend:local ./frontend
docker run -d --name inventory-frontend --network inventory-api_default -p 8080:80 inventory-frontend:local
```

The image builds the React assets and serves them with Nginx. The run command joins the Compose network created by the `inventory-api/` project, where the Nginx configuration can reach the API service by its `api` hostname. Open http://localhost:8080. Remove the container when finished with `docker rm -f inventory-frontend`.

### 5. Stop the application

From `inventory-api/`:

```bash
docker compose -p inventory-api down
```

To remove the database and uploaded-image volumes as well:

```bash
docker compose -p inventory-api down -v
```

**Warning:** Removing volumes deletes persisted database data and uploaded images.

## Production Docker deployment

The production configuration is located at `inventory-api/docker-compose.prod.yml`.

It uses prebuilt images from GitHub Container Registry instead of building the application locally. The production stack contains PostgreSQL, the FastAPI backend and the React frontend served by Nginx.

The frontend is published on host port `8080` (container port `80`), and the API on host port `8000`. The database is not published on a host port. Persistent Docker volumes are used for PostgreSQL data and uploaded item images. Nginx serves the frontend and proxies `/api` requests to the internal API service.

## Testing

The backend test suite uses PostgreSQL. Run all commands in this section from `inventory-api/`; `pytest` must be executed from this directory.

Install backend dependencies if you want to run the tests outside Docker:

```bash
cd inventory-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The tests use three PostgreSQL URLs with distinct purposes:

| Variable | Purpose | Safety behavior |
|---|---|---|
| `DATABASE_URL` | Database used by Alembic and the application configuration. For the commands below it points to the local `inventory` database. | The regular test fixture overrides the app database connection with `TEST_DATABASE_URL`. |
| `TEST_DATABASE_URL` | Required by the regular pytest client fixture. It must target `127.0.0.1:15432/inventory_test` using `postgresql+psycopg` and no URL query parameters. | The fixture verifies the database identity, then drops and recreates its tables for tests. All existing data in this dedicated test database is removed. |
| `STOCK_CONCURRENCY_TEST_DATABASE_URL` | Required by the PostgreSQL concurrency test. It must target a loopback host on port `15432` and the exact database `inventory_stock_concurrency_test`. | This database must already be migrated. The test does not create, migrate or drop its schema; it inserts and later deletes only its own test item and movement rows. |

The Compose service publishes PostgreSQL on `127.0.0.1:15432`. The `inventory_test` database is created by `inventory-api/docker/postgres/init.sql` when PostgreSQL initializes a new data volume. Create the separate concurrency database if it does not already exist, then apply migrations to both the application database and the concurrency database:

```bash
# Run from inventory-api/ after `docker compose -p inventory-api up -d db`.
docker compose -p inventory-api exec -T db psql -U devops -d inventory -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE DATABASE inventory_test'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'inventory_test'
)
\gexec

SELECT 'CREATE DATABASE inventory_stock_concurrency_test'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'inventory_stock_concurrency_test'
)
\gexec
SQL

export DATABASE_URL='postgresql+psycopg://devops:change_me@127.0.0.1:15432/inventory'
export TEST_DATABASE_URL='postgresql+psycopg://devops:change_me@127.0.0.1:15432/inventory_test'
export STOCK_CONCURRENCY_TEST_DATABASE_URL='postgresql+psycopg://devops:change_me@127.0.0.1:15432/inventory_stock_concurrency_test'

alembic upgrade head
DATABASE_URL="$STOCK_CONCURRENCY_TEST_DATABASE_URL" alembic upgrade head
pytest
```

Replace `change_me` with the password configured in `inventory-api/.env`. The SQL block creates the two dedicated test databases only if they are missing, including when an existing PostgreSQL volume predates the initialization script. Never point `TEST_DATABASE_URL` at `inventory`, a production database, or any database with data you want to preserve: its fixture drops and recreates the schema.

The latest validated local run completed with **82 tests passed**.

## CI/CD pipeline

GitHub Actions automates validation, image publication and optional production deployment. The workflow is defined in `.github/workflows/ci.yml`.

### Pipeline stages

```mermaid
flowchart TD
    Trigger[Push to main or pull request targeting main]
    Test[Backend tests, syntax and migrations]
    Docker[Build backend and frontend Docker images]
    Compose[Docker Compose integration check]
    Frontend[Frontend lint, type check and build]
    Publish[Publish multi-architecture images]
    Deploy[Deploy to production when enabled]

    Trigger --> Test
    Test --> Docker
    Test --> Compose
    Trigger --> Frontend
    Docker --> Publish
    Compose --> Publish
    Frontend --> Publish
    Test --> Publish
    Publish --> Deploy
```

The `test` job runs Python syntax checks, creates isolated test databases, applies and checks Alembic migrations, migrates the concurrency database, and runs pytest. The `docker` and `compose` jobs both depend on `test`; the frontend checks run independently. Image publication runs only for a push to `main` after `test`, `docker`, `compose` and `frontend` succeed. Deployment runs after publication only when `ENABLE_PRODUCTION_DEPLOY` is set to `true`.

### Docker image publication

On a successful push to `main`, the workflow publishes:

| Image | Registry path |
|---|---|
| Backend | `ghcr.io/<repository-owner>/devops-inventory` |
| Frontend | `ghcr.io/<repository-owner>/devops-inventory-frontend` |

Both images target `linux/amd64` and `linux/arm64`. The workflow tags each image with `latest` and a short commit tag in the `sha-<commit>` format. The deployment uses that commit-specific tag for both application images.

## Raspberry Pi deployment

The project supports deployment to a Raspberry Pi using Ansible, Docker Compose, GitHub Actions, Tailscale and GitHub Container Registry. The deployment workflow connects the GitHub Actions runner to the private Tailscale network and uses SSH to access the host.

### Ansible dependencies

Install Ansible and the required collections before running the playbooks:

```bash
python -m pip install ansible-core
ansible-galaxy collection install -r ansible/requirements.yml
```

### Initial provisioning and updates

`ansible/playbooks/bootstrap.yml` installs basic packages and ensures Docker is running; it is an initial host bootstrap, not the application deployment. `ansible/playbooks/site.yml` applies the full configuration through the `common`, `docker`, `inventory` and `monitoring` roles. Run this full site playbook when provisioning and configuring a host for the first time; it installs Docker, configures the application and monitoring stacks, and requires the Ansible Vault variables.

For application updates, the GitHub Actions workflow runs `ansible/playbooks/deploy.yml`. That playbook applies the `inventory` role to copy the production Compose file, write the environment file, log in to GHCR, pull the requested image tag and update the application containers. It preserves Docker volumes and checks API and frontend health. It does not install/configure the monitoring stack; that is handled by `site.yml`.

The default inventory in `ansible/inventory/hosts.yml` contains documentation-only example connection values. The workflow overrides the host and SSH user using repository variables. `ansible/inventory/group_vars/all.yml` defines the default GHCR owner and user-based application/monitoring paths. The workflow passes the repository owner and commit tag dynamically for the deployment.

### Required GitHub configuration

Configure the following Actions secrets:

| Secret | Purpose |
|---|---|
| `RASPBERRY_SSH_PRIVATE_KEY` | SSH private key for the managed host |
| `ANSIBLE_VAULT_PASSWORD` | Ansible Vault decryption password |
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client |
| `TS_OAUTH_SECRET` | Tailscale OAuth secret |

Configure these repository variables:

| Variable | Purpose |
|---|---|
| `RASPBERRY_HOST` | Host address or MagicDNS name reachable over Tailscale |
| `RASPBERRY_USER` | SSH account on the managed host |
| `RASPBERRY_SSH_KNOWN_HOSTS` | Verified SSH host key entry |
| `ENABLE_PRODUCTION_DEPLOY` | Must be `true` to enable automated deployment |

The workflow targets the GitHub Environment `production`, which can be configured to require manual approval. The managed host must have SSH access and a working Docker installation; the Ansible roles install/configure Docker during full site provisioning. Tailscale access policies must allow the CI runner to connect to SSH port `22`. Ansible Vault stores sensitive deployment credentials and must be provisioned securely; do not put its contents in this README or commit plaintext secrets.

## Monitoring

The monitoring stack is deployed by the Ansible `monitoring` role in a separate Compose project. Prometheus uses host networking and scrapes its configured targets every 15 seconds:

| Job | Target | Purpose |
|---|---|---|
| `raspberry` | `localhost:9100` | Host metrics from Node Exporter |
| `inventory-api` | `localhost:8000/metrics` | FastAPI application metrics |

The API exposes HTTP request and response counters (labeled by method, endpoint and, for responses, status code) and an HTTP request duration histogram. The `/metrics` endpoint is available from the host on port `8000`.

Grafana queries Prometheus. The monitoring Compose template publishes Grafana on port `3000`; Prometheus uses host networking on its default port `9090`. Node Exporter uses host networking on its default port `9100`.

| Service | Address |
|---|---|
| Prometheus | `http://<HOST>:9090` |
| Grafana | `http://<HOST>:3000` |
| Node Exporter | `http://<HOST>:9100/metrics` |
| FastAPI metrics | `http://<HOST>:8000/metrics` |

Prometheus and Grafana use persistent Docker volumes for monitoring data.

## Screenshots

Screenshots will be added here before the public beta announcement.

<!-- TODO: Replace these placeholders with real screenshots before publication. -->
- [ ] Application overview screenshot
- [ ] Inventory item details screenshot
- [ ] Monitoring dashboard screenshot

## API endpoints

The FastAPI application exposes the following main endpoint groups:

| Endpoint | Description |
|---|---|
| `/health` | Application health check |
| `/version` | API version |
| `/metrics` | Prometheus metrics |
| `/servers/` | Server management |
| `/items/` | Inventory item management |
| `/items/{item_id}` | Individual item details |
| `/items/{item_id}/image` | Item image operations |
| `/items/{item_id}/movements` | Stock movement history |

FastAPI's interactive API documentation is available at `http://localhost:8000/docs`.

## License

This project is licensed under the MIT License.

See the [LICENSE](LICENSE) file for details.
