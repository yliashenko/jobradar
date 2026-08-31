import { createServer, type Server } from 'node:http';

export interface StubLlm {
  url: string;
  close: () => Promise<void>;
}

// Minimal OpenAI-compatible /chat/completions stub. A triggered run's scorer POSTs
// here when the run config sets scorer.provider=openai + base_url=this. It returns
// a deterministic, **below-threshold** score (6 < notify_min_score 7), so a run
// stores and scores vacancies but never reaches the Telegram branch — the pipeline
// skips the notify line for below-threshold rows, so nothing hits the network.
// The same shape serves cover-letter generation (also an OpenAI chat call).
export async function startStubLlm(port: number): Promise<StubLlm> {
  const server: Server = createServer((req, res) => {
    let body = '';
    req.on('data', (c) => (body += String(c)));
    req.on('end', () => {
      const isCover = body.includes('cover') || body.includes('letter');
      const content = isCover
        ? JSON.stringify({
            letter: 'Dear team, stub cover letter for e2e.',
            evaluation: '**Fit:** stub evaluation.',
            traceability: '| claim | source |\n|---|---|\n| stub | facts |',
            fit_score: 6,
            band: 'AMBER',
          })
        : JSON.stringify({
            score: 6,
            band: 'stretch',
            matched: ['Playwright', 'pytest'],
            gaps: ['no commercial Python'],
            verdict: 'Stub verdict for e2e scoring.',
          });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ choices: [{ message: { content } }] }));
    });
  });
  await new Promise<void>((resolve) => server.listen(port, '127.0.0.1', () => resolve()));
  return {
    url: `http://127.0.0.1:${port}`,
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}
