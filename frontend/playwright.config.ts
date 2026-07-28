import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration.
 *
 * The suite drives a real backend, not a mocked one — but a backend configured
 * with the stub LLM, stub embeddings, and the in-process vector store, so it
 * needs no model server, no ChromaDB, and no network. See
 * `backend/app/infrastructure/llm/stub.py` for why those providers exist.
 *
 * That trade is deliberate and bounded: these tests prove the **wiring** —
 * uploads index, the supervisor routes, citations render, approvals pause and
 * resume — and prove nothing about answer quality, which a stub cannot have.
 *
 * Dedicated ports (not 8000/3000) so a run can never touch a developer's
 * running dev stack or its database. NEXT_PUBLIC_* is inlined at build time,
 * so the web server builds with the e2e API URL rather than reusing an
 * existing build.
 */

const API_PORT = 8100;
const WEB_PORT = 3100;
const API_URL = `http://127.0.0.1:${API_PORT}`;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

// Backend state for the run, wiped on every start so results never depend on a
// previous run. `..`-relative because the web server's cwd is `frontend/`.
const E2E_STATE = ".e2e-state";

// Set when the backend and frontend are already running on the ports above and
// should be left alone -- debugging a single spec, or a host that cannot launch
// the backend itself (it needs Python 3.11+).
const externalServers = process.env.E2E_EXTERNAL_SERVERS === "1";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.artifacts",
  // The backend is a SINGLE shared workspace with no authentication, so there
  // is no tenant boundary to isolate parallel tests behind: two specs running
  // at once would see each other's documents and tasks. Serial is correctness
  // here, not caution.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: externalServers ? undefined : [
    {
      command: [
        `rm -rf ../backend/${E2E_STATE}`,
        `mkdir -p ../backend/${E2E_STATE}`,
        `cd ../backend && alembic upgrade head`,
        `uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      ].join(" && "),
      url: `${API_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        // Zero-dependency providers: no Ollama, no Chroma, no network.
        LLM_PROVIDER: "stub",
        EMBEDDING_PROVIDER: "stub",
        VECTOR_STORE_PROVIDER: "memory",
        DATABASE_URL: `sqlite+aiosqlite:///./${E2E_STATE}/e2e.db`,
        DOCUMENTS_DIR: `./${E2E_STATE}/documents`,
        CHECKPOINT_DB_PATH: `./${E2E_STATE}/checkpoints.db`,
        STORAGE_PROVIDER: "local",
        CORS_ORIGINS: WEB_URL,
        ENVIRONMENT: "local",
        LOG_FORMAT: "console",
      },
    },
    {
      // `next.config.mjs` sets `output: "standalone"`, and `next start` does
      // NOT serve a standalone build -- it 400s on the page chunks, so pages
      // render server-side and then never hydrate. The static assets have to be
      // copied next to the standalone server exactly as the Dockerfile does,
      // which means these tests exercise the real production serving path.
      command: [
        "npm run build",
        "cp -r .next/static .next/standalone/.next/static",
        "cp -r public .next/standalone/public",
        `PORT=${WEB_PORT} node .next/standalone/server.js`,
      ].join(" && "),
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 300_000,
      stdout: "pipe",
      stderr: "pipe",
      env: { NEXT_PUBLIC_API_URL: API_URL, HOSTNAME: "127.0.0.1" },
    },
  ],
});
