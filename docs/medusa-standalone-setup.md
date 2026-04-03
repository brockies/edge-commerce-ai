# Standalone Medusa Setup on Windows

This repo expects Medusa to run as a separate service on `http://127.0.0.1:9000`.

## What this project needs from Medusa

- A standalone Medusa backend running locally.
- An admin user you can log in with.
- A publishable API key attached to at least one sales channel.

Without the publishable key, this app's calls to `/store/products` will fail.

## Recommended local layout

Keep Medusa in a sibling directory so you can reuse it with other projects:

```text
C:\Users\s.brockie\projects\
  edge-commerce-ai\
  medusa-store\
```

## Machine status checked on 2026-04-02

- `node` is installed: `v22.14.0`
- `npm` is installed: `10.9.2`
- `git` is installed
- Docker CLI is installed, but the Docker daemon was not reachable during setup
- Windows Python is not usable yet through `py` on this machine

The Medusa setup can proceed independently, but this repo's Python backend will still need Python fixed before the full app can run.

## 1. Start PostgreSQL for Medusa

If you want a quick local database, start Docker Desktop and create a PostgreSQL container:

```powershell
docker run --name medusa-postgres `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=medusa-store `
  -p 5432:5432 `
  -d postgres:16
```

If you use a different password, port, or database name, carry that through to the `--db-url` value in the next step.

## 2. Scaffold Medusa in its own directory

From anywhere, run:

```powershell
npx create-medusa-app@latest medusa-store `
  --no-browser `
  --directory-path C:\Users\s.brockie\projects `
  --db-url postgres://postgres:postgres@127.0.0.1:5432/medusa-store
```

This creates `C:\Users\s.brockie\projects\medusa-store`.

When prompted about the optional Next.js starter storefront, choose `N` unless you also want Medusa's sample storefront installed in a second directory.

If you want to create the project first and wire the database later, use `--skip-db` instead of `--db-url ...`.

If you scaffold with `--skip-db`, add the database URL to `C:\Users\s.brockie\projects\medusa-store\.env` before the first start:

```env
DATABASE_URL=postgres://postgres:postgres@127.0.0.1:5432/medusa-store
```

## 3. Run Medusa

```powershell
cd C:\Users\s.brockie\projects\medusa-store
npm run dev
```

The Medusa admin and backend should then be available on `http://127.0.0.1:9000`.

## 4. Create the publishable API key

If the installer did not create an admin user for you, create one from the Medusa project directory:

```powershell
cd C:\Users\s.brockie\projects\medusa-store
npx medusa user -e admin@example.com -p supersecret
```

Then in Medusa Admin:

1. Create a publishable API key.
2. Attach at least one sales channel to it.
3. Copy the key token.

You can also do this through the Admin API, but the dashboard is usually quickest for local setup.

## 5. Wire this repo to the standalone Medusa instance

Copy [backend/.env.example](/C:/Users/s.brockie/projects/edge-commerce-ai/backend/.env.example) to `backend/.env`, then fill in the values:

```env
MEDUSA_URL=http://127.0.0.1:9000
MEDUSA_PUBLISHABLE_KEY=pk_...
MEDUSA_ADMIN_EMAIL=admin@example.com
MEDUSA_ADMIN_PASSWORD=supersecret
OLLAMA_URL=http://127.0.0.1:11434
DEFAULT_MODEL=deepseek-r1:7b
DB_URL=postgresql://medusa-store:medusa-store@127.0.0.1:5434/medusa-store
```

Notes:

- `MEDUSA_URL` points at the standalone Medusa service.
- `MEDUSA_PUBLISHABLE_KEY` is required for `/store/products`.
- `MEDUSA_ADMIN_EMAIL` and `MEDUSA_ADMIN_PASSWORD` are used by `backend/add_products.py`.
- `DB_URL` above is for this repo's pgvector database, not Medusa's own PostgreSQL database.

## 6. Seed and run this repo after Python is fixed

Once `python` works on this machine:

```powershell
cd C:\Users\s.brockie\projects\edge-commerce-ai\backend
python add_products.py
python embed_products.py
```

Then run the backend and frontend as normal.

## Troubleshooting

### `connect ECONNREFUSED ::1:5432`

Use `127.0.0.1` explicitly in the database URL instead of relying on `localhost`, and make sure the PostgreSQL container is exposing port `5432`.

### Docker command cannot connect

Start Docker Desktop, then retry `docker ps`. If it still fails, run the terminal elevated or check whether the Docker Engine service is running.

### `py` fails on Windows

This machine currently points `py` at a blocked Store Python path. The quickest fix is usually one of these:

1. Install Python from python.org and enable `Add python.exe to PATH`.
2. Disable the Windows App Installer Python aliases, then reinstall Python.
3. Verify with `python --version` before running this repo's backend scripts.
