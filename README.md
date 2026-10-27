# devops-inventory

## Automatic Raspberry Pi deployment

The `deploy` job runs only after the `publish` job succeeds on a push to `main`. It joins the Tailscale network, connects to the Raspberry Pi over SSH, and runs `ansible/playbooks/deploy.yml`. The playbook reuses the `inventory` role and deploys the `sha-<7 character commit>` image tag published by that workflow. The role waits for `http://127.0.0.1:8000/health` to return HTTP 200. Compose uses named persistent volumes and the deployment does not run `down` or remove volumes.

Create these GitHub Actions secrets:

- `RASPBERRY_SSH_PRIVATE_KEY`: private SSH key whose public key is authorized for the Raspberry Pi account.
- `ANSIBLE_VAULT_PASSWORD`: password used to decrypt `ansible/inventory/group_vars/vault.yml`.
- `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_SECRET`: Tailscale OAuth credentials that can create ephemeral tagged devices.

Create these GitHub Actions variables:

- `RASPBERRY_HOST`: Raspberry Pi Tailscale IP address or MagicDNS name.
- `RASPBERRY_USER`: SSH account on the Raspberry Pi.
- `RASPBERRY_SSH_KNOWN_HOSTS`: the verified `known_hosts` entry for `RASPBERRY_HOST`.

The Tailscale OAuth credentials must be allowed to apply `tag:ci`, and the tailnet policy must allow that tag to reach the Raspberry Pi on SSH port 22. The Raspberry Pi account must be able to use passwordless sudo, as the existing Ansible deployment uses privilege escalation. GHCR credentials and the PostgreSQL password continue to come from the existing Ansible Vault variables.

## Production frontend and API

Production Compose runs the React frontend in its own Nginx container and the FastAPI application in the existing API container. The frontend is available at `http://<RASPBERRY_HOST>:8080`; the API remains available at `http://<RASPBERRY_HOST>:8000`. PostgreSQL is not exposed on a host port.

The production frontend is built with `VITE_API_BASE_URL=/api`. Its Nginx server serves the React files and forwards `/api/...` requests to the Compose `api` service after removing the `/api` prefix. It also forwards `/health` and `/version` to the API, so browser requests stay on the frontend origin without relying on Vite's development proxy or browser CORS configuration. The existing API health endpoint remains at port 8000.

The production images are published to GHCR with matching `latest` and `sha-<7 character commit>` tags:

- API: `ghcr.io/<owner>/devops-inventory`
- Frontend: `ghcr.io/<owner>/devops-inventory-frontend`

To build the frontend locally, run `npm ci`, `npm run lint`, and `npm run build` from `frontend/`; `docker build -t inventory-frontend:local frontend/` builds the production Nginx image. CI runs those checks and builds the frontend image. On a push to `main`, the publish job pushes both API and frontend images for `linux/amd64` and `linux/arm64`.

The Ansible `inventory` role writes one `IMAGE_TAG` into the production environment file. Its existing Compose pull and start tasks then update both images with that same tag. The API entrypoint applies Alembic migrations before starting FastAPI. The API remains on host port 8000 and the frontend uses host port 8080; the named `postgres_data` and `item_images` volumes remain persistent.

Automatic deployment still requires the repository variable `ENABLE_PRODUCTION_DEPLOY` to equal `true` and approval through the GitHub Environment `production`. After configuring that gate, merge the feature PR to `main`; CI tests and builds first, publishes both image tags, and then Ansible pulls and starts the matching production images after approval.
