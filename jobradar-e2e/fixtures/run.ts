import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

export interface FixtureJob {
  source?: string;
  url?: string;
  title: string;
  company?: string;
  location?: string;
  salary?: string;
  description?: string;
}

// Point a triggered run at a fixture source + the stub LLM by patching the worker's
// config.json. `sources.fixture` replaces the whole network (the product already
// supports it); the scorer routes to the OpenAI-compatible stub. resetState
// restores config.json before the next test, so this stays isolated.
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
  cfg.scorer = { enabled: true, provider: 'openai', base_url: llmUrl, api_key: 'test', model: 'stub' };
  // load_config requires telegram creds; the stub scores below threshold so the
  // pipeline never reaches the notify line — these dummies are never used to send.
  cfg.telegram = { bot_token: 'stub', chat_id: 'stub' };
  Object.assign(cfg, extra); // e.g. { l0: { exclude_title: [...] } }
  await writeFile(join(home, 'config.json'), JSON.stringify(cfg, null, 2));

  // The scorer needs a profile to score against; without one it errors and leaves
  // the row unscored (and score-None would reach the notify line). resetState
  // deletes profile.json before each test, so this is isolated.
  await writeFile(
    join(home, 'profile.json'),
    JSON.stringify({ cv_text: 'QA Automation Engineer — Playwright, pytest.', notes: 'QA.' }),
  );
}
