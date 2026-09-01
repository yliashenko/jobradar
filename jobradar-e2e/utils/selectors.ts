/** Single source for the UI's stable selectors (`data-testid` + a few classes).
 * Page objects and specs both reference this, so a markup change is one edit. */
export const sel = {
  card: '[data-testid="job-card"]',
  cardOf: (hash: string) => `[data-testid="job-card"][data-hash="${hash}"]`,
  statusBtn: (status: string) => `[data-testid="status-btn"][data-status="${status}"]`,
  tag: (term: string) => `[data-testid="tag"][data-tag="${term}"]`,
  tagAny: '[data-testid="tag"]',
  scoreOpen: '[data-testid="score-open"]',
  scoreModal: (hash: string) => `#score-${hash}[data-testid="score-modal"]`,
  runbox: 'form.runbox',
} as const;
