/** Single source for the UI's stable selectors (`data-testid` + a few classes).
 * Page objects and specs both reference this, so a markup change is one edit. */
export const sel = {
  card: '[data-testid="job-card"]',
  tagAny: '[data-testid="tag"]',
  scoreOpen: '[data-testid="score-open"]',
  runbox: 'form.runbox',
  jobCardOf: (hash: string) => `[data-testid="job-card"][data-hash="${hash}"]`,
  hiringCardOf: (hash: string) => `[data-testid="hiring-card"][data-hash="${hash}"]`,
  statusBtn: (status: string) => `[data-testid="status-btn"][data-status="${status}"]`,
  tag: (term: string) => `[data-testid="tag"][data-tag="${term}"]`,
  scoreModal: (hash: string) => `#score-${hash}[data-testid="score-modal"]`,
  pager: '[data-testid="pager"]',
  pagerPrev: '[data-testid="pager-prev"]',
  pagerNext: '[data-testid="pager-next"]',
  counts: '.tabrow .counts',
  // The tag picker: a closed <details> whose body is fetched on first open.
  tagPicker: 'details[data-pick="tags"]',
  tagPanelSlot: '[data-testid="tags-panel"]',
  tagPanel: '[data-testid="tags-panel"] form.pick-panel',
  tagPickSearch: '[data-testid="tags-panel"] .picksearch',
  tagPickRow: '[data-testid="tags-panel"] .pickrow',
  tagPickApply: '[data-testid="tags-panel"] button.apply',
  tagPickBox: (term: string) => `[data-testid="tags-panel"] input[name="tech"][value="${term}"]`,
} as const;
