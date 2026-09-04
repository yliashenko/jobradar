import { type APIRequestContext, type APIResponse } from '@playwright/test';

/** API-layer facade over APIRequestContext. baseURL and the token header are
 *  set on the request by the fixture, so only routes live here. */
export class JobradarApi {
  constructor(private readonly request: APIRequestContext) {}

  health(): Promise<APIResponse> {
    return this.request.get('/health');
  }

  feed(query = ''): Promise<APIResponse> {
    return this.request.get(`/${query}`);
  }

  setStatus(hash: string, status: string): Promise<APIResponse> {
    return this.request.post('/status', { form: { hash, status }, maxRedirects: 0 });
  }

  /** Arrange settings pre-state (LLM/Telegram/auto-scan) the way the Settings form
   *  would, so a test can start from a configured account without clicking through it. */
  saveSettings(form: Record<string, string>): Promise<APIResponse> {
    return this.request.post('/settings', { form: { action: 'save', ...form }, maxRedirects: 0 });
  }
}
