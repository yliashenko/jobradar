import { spawn, type ChildProcess } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

const REPO_ROOT = resolve(__dirname, '..', '..');

// Pin the interpreter instead of bare `python3`: across CLI, IDE and CI the name
// resolves to different interpreters and the server dies on a missing Flask.
// Order: explicit override → project venv → PATH.
export const PYTHON =
  process.env.E2E_PYTHON ||
  (existsSync(join(REPO_ROOT, '.venv', 'bin', 'python3'))
    ? join(REPO_ROOT, '.venv', 'bin', 'python3')
    : 'python3');

/** Run a Python script under JOBRADAR_HOME; resolves on exit 0, rejects otherwise. */
export function runPython(script: string, home: string): Promise<void> {
  return new Promise((resolvePromise, reject) => {
    const p = spawn(PYTHON, [script], {
      cwd: REPO_ROOT,
      env: { ...process.env, JOBRADAR_HOME: home },
      stdio: ['ignore', 'ignore', 'pipe'],
    });
    let stderr = '';
    p.stderr?.on('data', (d) => (stderr += d));
    p.on('close', (code) =>
      code === 0 ? resolvePromise() : reject(new Error(`${script} exited ${code}:\n${stderr}`)),
    );
    p.on('error', reject);
  });
}

/** Run one synchronous scan (`python -m jobradar run`) under JOBRADAR_HOME.
 * Synchronous by design: the pipeline finishes before the test asserts, so run
 * tests need no polling and don't race the per-test reset (unlike the async
 * POST /run button, which OPS tests cover for its 303 contract). */
export function runScan(home: string): Promise<void> {
  return new Promise((resolvePromise, reject) => {
    const p = spawn(PYTHON, ['-m', 'jobradar', 'run'], {
      cwd: REPO_ROOT,
      env: { ...process.env, JOBRADAR_HOME: home },
      stdio: ['ignore', 'ignore', 'pipe'],
    });
    let stderr = '';
    p.stderr?.on('data', (d) => (stderr += d));
    p.on('close', (code) =>
      code === 0 ? resolvePromise() : reject(new Error(`scan exited ${code}:\n${stderr}`)),
    );
    p.on('error', reject);
  });
}

/** Spawn `python -m jobradar serve` for the given home and port. */
export function spawnServer(home: string, port: number): ChildProcess {
  return spawn(
    PYTHON,
    ['-m', 'jobradar', 'serve', '--port', String(port), '--host', '127.0.0.1'],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, JOBRADAR_HOME: home },
      stdio: ['ignore', 'ignore', 'pipe'],
    },
  );
}

/** Poll a health URL until it responds, or throw after 20s. */
export async function waitForHealth(healthUrl: string, errTail: () => string): Promise<void> {
  const deadline = Date.now() + 20_000;
  let lastErr = '';
  while (Date.now() < deadline) {
    try {
      const res = await fetch(healthUrl);
      if (res.ok) return;
    } catch (e) {
      lastErr = String(e);
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`Server did not come up at ${healthUrl}. Last: ${lastErr}\nstderr:\n${errTail()}`);
}

/** Resolve when the process exits, or after timeoutMs. */
export function onceExit(proc: ChildProcess, timeoutMs: number): Promise<void> {
  return new Promise((r) => {
    const t = setTimeout(r, timeoutMs);
    proc.on('exit', () => {
      clearTimeout(t);
      r();
    });
  });
}
