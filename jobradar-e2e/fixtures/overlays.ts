import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';

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
