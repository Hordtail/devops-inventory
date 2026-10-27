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
