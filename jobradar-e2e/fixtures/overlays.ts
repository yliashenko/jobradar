import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { runPython } from './helpers';

/** Test-data files written into a worker's JOBRADAR_HOME. The same catalog DB is
 *  reused; only these files differ (an overlay). resetState clears them per test. */

/** profile.json overlay — role/skills/exclude/LLM config the run and views read. */
export function writeProfile(home: string, profile: Record<string, unknown>): Promise<void> {
  return writeFile(join(home, 'profile.json'), JSON.stringify(profile));
}

/** career-facts.md — the source facts the cover-letter generator reads. */
export function writeFacts(home: string, text: string): Promise<void> {
  return writeFile(join(home, 'career-facts.md'), text);
}


/** Insert an extra seed set into this worker's DB, on top of the catalog.
 *  For state the catalog deliberately lacks — the catalog is smaller than one
 *  feed page so other specs assert exact counts, so a pager needs bulk rows.
 *  resetState restores the pristine DB after the test, so the rows are local
 *  to it. */
export function seedSet(home: string, name: string): Promise<void> {
  return runPython(join(__dirname, 'seed.py'), home, name);
}
