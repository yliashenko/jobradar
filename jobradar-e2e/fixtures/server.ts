import { test as base, expect } from '@playwright/test';
import { mkdtemp, writeFile, rm, copyFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { JobradarApi } from '../api/jobradar-api';
import { runPython, spawnServer, waitForHealth, onceExit } from './helpers';
import { startStubLlm, type StubLlm } from './stub-llm';

const SEED_SCRIPT = join(__dirname, 'seed.py');
const TOKEN = 'e2e-secret-token';

export interface ServerInfo {
  url: string;
  token: string;
  home: string;
  /** Base URL of the per-worker stub LLM — for run tests that enable the scorer. */
  llmUrl: string;
}

interface WorkerFixtures {
  server: ServerInfo;
}

interface TestFixtures {
  api: JobradarApi;
  resetState: void;
}

// Boots an isolated jobradar per worker: its own temp home (JOBRADAR_HOME),
// config with a known token, seeded jobs.db and port. The product is untouched —
// it reads every path from JOBRADAR_HOME. This per-worker state is what makes
// parallel runs safe.
export const test = base.extend<TestFixtures, WorkerFixtures>({
  server: [
    async ({}, use, workerInfo) => {
      const home = await mkdtemp(join(tmpdir(), 'jobradar-e2e-'));

      const config = {
        notify_min_score: 7,
        webui: { host: '127.0.0.1', token: TOKEN },
        scorer: { enabled: false },
        sources: { imap: { enabled: false } },
      };
      await writeFile(join(home, 'config.json'), JSON.stringify(config, null, 2));

      // Seed through the product's own schema, then keep pristine copies of the DB
      // and config for the per-test reset below (run tests patch config.json).
      await runPython(SEED_SCRIPT, home);
      await copyFile(join(home, 'jobs.db'), join(home, 'jobs.db.template'));
      await copyFile(join(home, 'config.json'), join(home, 'config.json.template'));

      // A per-worker OpenAI-compatible stub, so run tests can enable the scorer
      // deterministically and offline (see fixtures/run.ts).
      const stub: StubLlm = await startStubLlm(8900 + workerInfo.workerIndex);

      const port = 8800 + workerInfo.workerIndex;
      const url = `http://127.0.0.1:${port}`;

      const proc = spawnServer(home, port);
      let serverErr = '';
      proc.stderr?.on('data', (d) => (serverErr = (serverErr + d).slice(-4000)));

      await waitForHealth(`${url}/health`, () => serverErr);
      await use({ url, token: TOKEN, home, llmUrl: stub.url });

      // Teardown lives beside setup and runs even after a failure — more reliable
      // than an afterEach, and scoped to the worker's lifetime.
      proc.kill('SIGTERM');
      await onceExit(proc, 3000);
      await stub.close();
      await rm(home, { recursive: true, force: true });
    },
    { scope: 'worker' },
  ],

  // Point request/page at this worker's server, so tests use relative paths.
  baseURL: async ({ server }, use) => {
    await use(server.url);
  },

  // The product is stateless (no session/cookies), so "shared auth" is a static
  // token header set once, not storageState.
  extraHTTPHeaders: async ({ server }, use) => {
    await use({ 'X-Jobradar-Token': server.token });
  },

  api: async ({ request }, use) => {
    await use(new JobradarApi(request));
  },

  // Restore per-test state on a shared worker before every test: the DB from the
  // pristine template and no saved profile. Cheap file ops, no server restart.
  resetState: [
    async ({ server }, use) => {
      await copyFile(join(server.home, 'jobs.db.template'), join(server.home, 'jobs.db'));
      await copyFile(join(server.home, 'config.json.template'), join(server.home, 'config.json'));
      await rm(join(server.home, 'profile.json'), { force: true });
      // Clear any lock a previous test's triggered run left behind, so the next
      // POST /run isn't turned away as "busy" on a shared worker.
      await rm(join(server.home, '.lock'), { recursive: true, force: true });
      await use(undefined);
    },
    { auto: true },
  ],
});

export { expect };
