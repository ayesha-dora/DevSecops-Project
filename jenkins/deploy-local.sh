#!/usr/bin/env bash
set -Eeuo pipefail
# Jenkins binds a file path only; never source, print, or archive its contents.
set +x
: "${APP_IMAGE:?}" "${APP_CONTAINER:?}" "${APP_VOLUME:?}" "${APP_ENV_FILE:?}" "${APP_PORT:?}"
[[ "$APP_PORT" =~ ^[0-9]{1,5}$ ]] && ((10#$APP_PORT >= 1 && 10#$APP_PORT <= 65535)) || {
    echo 'APP_PORT must be between 1 and 65535.' >&2; exit 1;
}
# Validate without exposing the API key. Reject extra Docker/app settings.
awk '
    /^[[:space:]]*(#|$)/ { next }
    /^APP_API_KEY=/ {
        key=substr($0,13); count++
        if (length(key)<32 || key ~ /CHANGE_ME|[[:space:]"\047]/) bad=1
        next
    }
    /^LOG_LEVEL=(DEBUG|INFO|WARNING|ERROR|CRITICAL)$/ { next }
    { bad=1 }
    END { if (count!=1 || bad) exit 1 }
' "$APP_ENV_FILE" || {
    echo 'Invalid env file: require one APP_API_KEY (32+ characters) and optional valid LOG_LEVEL. Use the supplied template and Unix line endings.' >&2
    exit 1
}

backup="${APP_CONTAINER}-previous"
docker image inspect "$APP_IMAGE" >/dev/null
if docker container inspect "$backup" >/dev/null 2>&1; then
    echo "Container $backup exists from an interrupted deployment. Restore or remove it before retrying." >&2
    exit 1
fi
# Refuse to replace a container owned by another workflow.
had_previous=false
was_running=false
if docker container inspect "$APP_CONTAINER" >/dev/null 2>&1; then
    owner=$(docker inspect -f '{{index .Config.Labels "devsecops.local-deploy"}}' "$APP_CONTAINER")
    [[ "$owner" == 'true' ]] || { echo 'Target container is not managed by this pipeline.' >&2; exit 1; }
    had_previous=true
    was_running=$(docker inspect -f '{{.State.Running}}' "$APP_CONTAINER")
fi
docker volume create "$APP_VOLUME" >/dev/null
docker run --rm --network none --user 0:0 --volume "$APP_VOLUME:/data" \
    "$APP_IMAGE" chown 10001:10001 /data

replacement_started=false
previous_renamed=false
rollback() {
    rc=$?
    trap - EXIT INT TERM
    if ((rc != 0)); then
        echo 'Deployment failed; restoring previous container if present.' >&2
        if "$replacement_started"; then docker rm -f "$APP_CONTAINER" >/dev/null || true; fi
        if "$previous_renamed"; then
            docker rename "$backup" "$APP_CONTAINER" || true
            if "$was_running"; then docker start "$APP_CONTAINER" >/dev/null || true; fi
        fi
    fi
    exit "$rc"
}
trap rollback EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if "$had_previous"; then
    docker rename "$APP_CONTAINER" "$backup"
    previous_renamed=true
    docker stop --time 30 "$backup" >/dev/null
fi
replacement_started=true
docker run -d --name "$APP_CONTAINER" \
    --label devsecops.local-deploy=true \
    --restart unless-stopped --read-only --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,nosuid,nodev,size=64m \
    --env-file "$APP_ENV_FILE" --env APP_DB=/data/users.db \
    --volume "$APP_VOLUME:/data" --publish "${APP_PORT}:5000" \
    --health-cmd 'python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:5000/health\", timeout=3)"' \
    --health-interval 5s --health-timeout 4s --health-retries 6 \
    "$APP_IMAGE" >/dev/null

healthy=false
for attempt in {1..30}; do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$APP_CONTAINER")
    if [[ "$status" == healthy ]]; then healthy=true; break; fi
    if [[ "$status" == unhealthy ]]; then break; fi
    sleep 2
done
"$healthy" || { echo 'App did not become healthy within 60 seconds.' >&2; exit 1; }
# Check app routes through its network namespace, including database access.
docker exec "$APP_CONTAINER" python -c '
import urllib.request
for path in ("/health", "/dashboard", "/users", "/metrics"):
    with urllib.request.urlopen("http://127.0.0.1:5000" + path, timeout=5) as response:
        assert response.status == 200, path
print("Application smoke checks passed")
'
trap - EXIT INT TERM
if "$previous_renamed"; then docker rm "$backup" >/dev/null; fi
echo "Deployment ready on Docker host port $APP_PORT; database volume: $APP_VOLUME"
