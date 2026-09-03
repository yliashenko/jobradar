/** jobradar webui routes. Single source, so a path change lives in one place. */
export const Routes = {
  health: '/health',
  feed: '/',
  status: '/status',
  run: '/run',
  profile: '/profile',
  settings: '/settings',
  tags: '/tags',
  stats: '/stats',
  runs: '/runs',
  calendar: '/calendar',
  company: '/company',
} as const;
