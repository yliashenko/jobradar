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
}
