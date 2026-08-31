import { test } from '@playwright/test';

export function step(title?: string) {
  return function <This, Args extends unknown[], Return>(
    target: (this: This, ...args: Args) => Promise<Return>,
    context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => Promise<Return>>,
  ) {
    return function (this: This, ...args: Args): Promise<Return> {
      const owner = (this as { constructor?: { name?: string } })?.constructor?.name ?? 'step';
      const name = title ?? `${owner}.${String(context.name)}`;
      return test.step(name, async () => target.call(this, ...args));
    };
  };
}
