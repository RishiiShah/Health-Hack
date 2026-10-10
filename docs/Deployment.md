# Deployment: Render first, AWS second, Azure last

The same Python 3.14.7 Docker image runs on all three providers. It binds `0.0.0.0:$PORT` (default 8000), keeps one uvicorn worker, writes logs to stdout/stderr, handles SIGTERM directly and closes SQLite during application shutdown. `/health` is liveness; `/ready` checks startup of the implemented consult-replay foundation and reports unsupported capabilities. Authentication and the remaining operations gates are still pending.

| Preference | Deployment | Durable storage | Process count |
| --- | --- | --- | --- |
| 1 | Render Docker web service, root `render.yaml` | Persistent disk mounted at `/data` | 1 service instance, 1 worker |
| 2 | AWS EC2 Linux VM running `deploy/compose.yaml` | EBS data volume formatted with a local filesystem, mounted into the container at `/data` | 1 container, 1 worker |
| 3 | Azure Linux VM running the same Compose file | Managed data disk with a local filesystem, mounted into the container at `/data` | 1 container, 1 worker |

These are executable deployment configurations and a documented fallback path, not completed cloud deployments. No infrastructure has been provisioned. Until mutation authentication is implemented, use private access or an authenticated gateway for hosted demos.

The runtime is pinned to standard CPython 3.14.7 in `backend/Dockerfile` (`python:3.14.7-slim`), CI and `backend/.python-version`. Render, AWS and Azure use that same image. Package metadata allows Python >=3.14.7,<3.15. Validate tests and the container persistence probe before advancing the pinned patch version; free-threaded/JIT builds and performance improvements are not claimed.

## Render

1. Commit the backend, `render.yaml` and CI configuration to the Git repository. The supplied source `data/` folder and `.venv` are gitignored and are not built into the image.
2. Create a Render Blueprint from the repository and use the root `render.yaml`. It specifies the Dockerfile/build context, a disk-backed paid service, one instance, `/ready`, and `CC_DB_PATH=/data/cc.db`.
3. Keep `PORT` managed by Render. `python -m app` reads it at startup. Do not replace the image command with a multi-worker server or enable replica autoscaling.
4. Confirm `/ready` responds and check its capability flags. A new disk starts with an empty event log. The sample fixture helper is available in Python, but CSV upload/reference activation is not implemented yet.
5. Verify persistence with synthetic test events and a manual redeploy in a disposable environment before loading real operational data. Disk-backed redeploys briefly stop the existing instance.

Render specifies `0.0.0.0` binding and recommends `PORT`; persistent storage is limited to the mount path and belongs to one instance. See [Render web services](https://render.com/docs/web-services), [Blueprint specification](https://render.com/docs/blueprint-spec) and [persistent disk constraints](https://render.com/docs/disks).

## AWS fallback

Use an EC2 Linux VM with Docker Engine and Compose installed. Attach an EBS data volume, mount its local filesystem persistently at a directory such as `/srv/command-center-data`, and set `DeleteOnTermination=false` for the data volume. Keep this disk attached to only the active writer VM. See [EBS persistence](https://docs.aws.amazon.com/ebs/latest/userguide/EBSFeatures.html) and [EC2 volume retention](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/preserving-volumes-on-termination.html).

From the repository root on that VM:

```sh
mountpoint /srv/command-center-data
export CC_HOST_DATA_DIR=/srv/command-center-data
docker compose -f deploy/compose.yaml up -d --build
docker compose -f deploy/compose.yaml ps
curl --fail http://127.0.0.1:8000/ready
```

Run the Compose commands only after the mount check succeeds. The bind mount refuses to invent a missing source directory, but an existing directory is not proof the cloud disk is mounted. Install a TLS reverse proxy on the same host that forwards to `127.0.0.1:8000`, or place a load balancer in front of that reverse proxy. Restrict network access appropriately; the Compose service exposes the application only on loopback. The proxy must preserve forwarding headers and support WebSockets when those routes are implemented.

Do not attach SQLite WAL to an EFS/network-file mount. EC2 + EBS is the current AWS fallback; managed container services require a separately designed durable storage/coordination solution before replacing it.

## Azure last resort

Use an Azure Linux VM with Docker Engine and Compose. Attach a managed data disk, create/mount a local filesystem at `/srv/command-center-data`, and configure persistent mounting by filesystem UUID. Use the same commands and host reverse proxy as the AWS path. Verify the mount survives reboot. Microsoft's [managed-disk mounting guide](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/attach-disk-portal) describes the disk and persistent-mount configuration.

Azure Container Apps with Azure Files is not the current fallback for the SQLite WAL architecture. Its durable volume option is a network file share; see [Container Apps storage](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts). SQLite documents that [WAL does not work over network filesystems](https://sqlite.org/wal.html). Moving to Container Apps requires an external database implementation and suitable coordination, rather than changing only the volume mount.

## Environment and migration contract

| Variable | Meaning | Container / deployment default |
| --- | --- | --- |
| `PORT` | HTTP port; integer 1–65535 | 8000; Render supplies its own |
| `CC_DB_PATH` | Durable SQLite file, including WAL/SHM sidecars in the same directory | `/data/cc.db` |
| `CC_DATA_DIR` | Durable reference-file location for future reference support | `/data/ref` |
| `CC_CLOCK_MODE` | `auto`, `wall`, `anchored`, `fixed` | `auto` |
| `CC_CLOCK_FIXED` | Offset-aware fixed/anchor time, when needed | unset |
| `CC_SERVICE_DATE` | Service date used by future time-only schedule normalization | fixture default March 17, 2026; schedule normalization pending |

Never horizontally scale this in-memory/SQLite architecture. Provider changes preserve the image and API; they require a consistent database transfer and a single active writer. Export using SQLite's backup API or stop the writer and transfer a consistent database including committed WAL data. Restore and verify replay before switching traffic; retain the old host inactive until verification finishes. Database backup/restore automation is not implemented yet.

The Docker build excludes local environments, databases, caches and `.env` files. CI is configured to build the image, start it on a nondefault port, commit a synthetic consult, replace the container on the same volume, and check recovery. The same smoke script can check a disposable local deployment. A passing CI deployment probe establishes hosting compatibility for the foundation, not completion of physician detection, forecasts or production security.

## Verification performed

The Python 3.14.7 suite passes 20 tests, including real HTTP server startup on nondefault ports, synthetic ingestion, graceful SIGTERM shutdown and event recovery after replacement of the server process. The launcher uses its active Python interpreter rather than depending on a globally installed `uvicorn` executable. Render manifest paths/health configuration and Compose configuration validation pass.

The `python:3.14.7-slim` tag was verified against Docker Hub and includes Linux deployment images. The rebuilt local 3.14.7 environment also passes `pip check`.

The local Docker daemon is stopped, so an image build and container-level smoke test were not run locally. Those checks are configured in CI and still need execution. No Render, AWS or Azure deployment was performed.
