import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { writeProfile } from './overlays';

export interface FixtureJob {
  source?: string;
  url?: string;
  title: string;
  company?: string;
  location?: string;
  salary?: string;
  description?: string;
}

// Point a triggered run at a fixture source + the stub LLM. `sources.fixture`
// (patched into config.json) replaces the whole network; the LLM account — provider,
// base_url (the OpenAI-compatible stub) and key — lives in the profile, the product's
// single source. resetState restores config.json and drops profile.json before the
// next test, so this stays isolated.
export async function configureRun(
  home: string,
  llmUrl: string,
  jobs: FixtureJob[],
  extra: Record<string, unknown> = {},
): Promise<void> {
  const fixturePath = join(home, 'fixture.json');
  const withDefaults = jobs.map((j, i) => ({
    source: 'dou',
    url: `https://example.test/fx-${i}`,
    company: '',
    location: '',
    salary: '',
    description: '',
    ...j,
  }));
  await writeFile(fixturePath, JSON.stringify({ jobs: withDefaults }));

  const cfg = JSON.parse(await readFile(join(home, 'config.json'), 'utf-8'));
  cfg.sources = { ...(cfg.sources || {}), fixture: { enabled: true, path: fixturePath } };
  cfg.scorer = { enabled: true, model: 'stub' };
  Object.assign(cfg, extra); // e.g. { l0: { exclude_title: [...] } }
  await writeFile(join(home, 'config.json'), JSON.stringify(cfg, null, 2));

  // The account (key + OpenAI-compatible stub endpoint) and the profile to score
  // against both live in profile.json — the single source llm_settings() reads.
  // Without a profile the scorer errors and leaves the row unscored; resetState
  // deletes profile.json before each test, so this is isolated.
  await writeProfile(home, {
    cv_text: 'QA Automation Engineer — Playwright, pytest.',
    notes: 'QA.',
    api_key: 'test',
    llm_provider: 'openai',
    llm_base_url: llmUrl,
  });
}
