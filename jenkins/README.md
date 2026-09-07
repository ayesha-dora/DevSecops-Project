# Local Jenkins deployment

Use `jenkins/Jenkinsfile` as the job's **Script Path**. It builds the existing
`app/Dockerfile`, runs the app tests inside that image, and deploys to the Docker
daemon on the Jenkins agent machine. Default URL: `http://localhost:5001/dashboard`
(use the Docker host's IP if accessing from another machine).

## Jenkins setup

1. Use one Linux Jenkins agent with Bash, Git, Docker CLI and permission to access
   `/var/run/docker.sock`. The repository's Jenkins Docker image includes these tools.
   Verify from the host with `docker exec jenkins docker info`.
   The current local Jenkins container reports permission denied. From the repo
   root, apply the included override (this restarts Jenkins, retaining its volume):

   ```bash
   export DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
   docker compose -f docker-compose.yml -f jenkins/compose.socket.yml up -d --no-deps jenkins
   docker exec jenkins docker info
   ```

   Keep using both Compose files when recreating Jenkins. This host currently has
   socket group `986`; the command detects it rather than hardcoding it. The root
   Compose file still needs its existing Grafana settings in the host `.env`.
   `DOCKER_SOCKET_GID` is a host setting, not part of the Jenkins secret file.
2. Jenkins needs Pipeline, Git, and Credentials Binding plugins, plus Timestamper
   for the `timestamps()` option. Use one job for this fixed deployment target;
   do not run multiple jobs/agents against the same container and volume.
3. Copy `jenkins/app.env.example` to a file outside the repository. Generate a key
   with `openssl rand -hex 32` and replace `CHANGE_ME`. Save as UTF-8 (`.env` or
   `.txt` is fine); Unix LF, Windows CRLF, and UTF-8 BOM are supported. Spaces
   around `=` and at line edges are trimmed. Do not include quotes, `export`,
   or Markdown backticks:

   ```dotenv
   APP_API_KEY=replace_with_your_generated_64_character_hex_key
   LOG_LEVEL=INFO
   ```

4. In **Manage Jenkins → Credentials → System → Global credentials → Add Credentials**,
   select **Secret file**, upload that file, and set ID to `devsecops-local-env`.
   The pipeline passes it directly to Docker without sourcing or printing it.
   `APP_DB=/data/users.db` is set by the pipeline, so omit it from the file.
5. Create a **Pipeline** job → **Pipeline script from SCM** → **Git**. Set the repo
   URL, branch, optional Git credentials for a private repository, and Script Path
   `jenkins/Jenkinsfile`. Commit/push these new files to that branch first.
6. Click **Build Now**. Subsequent runs expose **Build with Parameters** for
   `APP_PORT` and `ENV_CREDENTIALS_ID`. For automatic builds on code changes, enable
   **Poll SCM** with `H/2 * * * *` (checks roughly every two minutes), or configure
   your Git provider's webhook if it can reach Jenkins.

No Docker Hub, AWS, Kubernetes, SonarQube, or AI service credentials are required
for this local app pipeline. The root Jenkinsfile remains the broader DevSecOps
workflow; this local pipeline covers build, tests, deployment and smoke checks.

## Deployment behavior

- Default port `5001` replaces `devsecops-app`, using persistent volume
  `devsecops-app-data`. On the first takeover, the expected Compose app is stopped
  and its `/tmp/users.db` is copied into that volume. Copy failure restores the old
  container. Existing Docker networks are preserved for monitoring and service DNS.
- Subsequent builds replace the same container and reuse its database volume.
  Select `APP_PORT=5001` explicitly if Jenkins still shows the old `5002` default.
- Port `5002` continues to use the separate `devsecops-local-app` container and
  `devsecops-local-data` volume. Other occupied ports are not automatically cleared.
- After takeover, manage the app through Jenkins; recreating `devsecops-app` with
  Compose can conflict with or overwrite this deployment. Other Compose services
  can still be managed individually. The app is published on Docker host interfaces.
- Tests or build failures stop deployment. The previous container is kept during
  replacement and restored if startup or smoke checks fail. There is a brief outage
  while replacing it. Rollback restores the container, not database contents; this
  app has no schema migration step.
- The secret file accepts only `APP_API_KEY` and optional `LOG_LEVEL`. Do not upload
  the repository-wide `.env` with unrelated service credentials.
- `/health`, `/dashboard`, `/users`, and `/metrics` are checked inside the deployed
  container. External firewall/routing access must be checked from your browser.
- If Jenkins is forcibly terminated mid-deployment and a `-previous` container
  remains, inspect and restore/remove it before retrying. Failed deployments keep
  the database volume. Old build images are retained for manual housekeeping.

To use the app API, send your key as the `X-API-Key` header for `POST /users`.
The optional port-5002 deployment stays separate from the port-5001 application.

## Verification performed

The application image built successfully and all 10 existing tests passed. The
deployment script passed a first deployment, replacement deployment, and deliberate
occupied-port failure with restoration of the previous running container. Bash
syntax and whitespace checks passed. A live Jenkins job has not been run; configure
the credentials and SCM job above before the first build.

Deployment control-flow checks: `python3 jenkins/tests/test_deploy.py` (mock Docker;
checks Compose takeover, repeat deployment, port 5002, rollback, and ownership refusal).
