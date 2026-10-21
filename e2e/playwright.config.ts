import path from "node:path";
import { defineConfig } from "@playwright/test";

/** E2E smoke suite drives the REAL production shape: backend API + built SPA
 * served together by FastAPI on a single port (see backend/app/main.py).
 *
 * Run from the repo root or the e2e dir:  npm test
 *
 * Ordering matters (Playwright starts the webServer BEFORE globalSetup):
 * the webServer command therefore runs backend/e2e_bootstrap.py (fresh
 * clinic_e2e database + catalog + login) before uvicorn boots.
 */
const IS_WIN = process.platform === "win32";

export const REPO_ROOT = path.resolve(__dirname, "..");
export const BACKEND_DIR = path.join(REPO_ROOT, "backend");
export const PY = IS_WIN
  ? path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
  : path.join(REPO_ROOT, ".venv", "bin", "python");

export const PORT = Number(process.env.E2E_PORT ?? 8001);
export const BASE_URL = `http://127.0.0.1:${PORT}`;
export const DB_URL = process.env.E2E_DATABASE_URL
  ?? "postgresql+psycopg://postgres@127.0.0.1:5432/clinic_e2e";

/** Local sandbox credentials for the e2e run only (never production). */
export const E2E_USER = process.env.E2E_USER ?? "owner";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "E2e-Pass-2026";

export const AUTH_STATE = path.join(__dirname, ".auth", "state.json");

/** Real signed license for the fresh e2e database (gitignored, vendor key). */
export const LICENSE_FILE = path.join(__dirname, ".licence.lic");

export default defineConfig({
  testDir: __dirname,
  timeout: 45_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: "auth.setup.spec.ts" },
    {
      name: "smoke",
      testMatch: "smoke.spec.ts",
      dependencies: ["setup"],
      use: { storageState: AUTH_STATE },
    },
  ],
  webServer: {
    command: `"${PY}" "${path.join(BACKEND_DIR, "e2e_bootstrap.py")}" && "${PY}" -m uvicorn app.main:app --app-dir "${BACKEND_DIR}" --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE_URL}/api/health`,
    reuseExistingServer: false,
    timeout: 90_000,
    env: { ...process.env, CLINIC_DATABASE_URL: DB_URL, CLINIC_LICENSE_FILE: LICENSE_FILE },
  },
});
