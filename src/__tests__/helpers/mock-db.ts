import { vi } from "vitest";

/**
 * Creates a chainable mock that mimics drizzle's async query builder.
 * Every method returns the same chain object, so calls like
 * db.select().from().where() all work.
 *
 * Awaiting the chain pops the next result from the queue (default: []).
 * Use _queueResult() to push results in the order they'll be consumed.
 */
export function createMockDb() {
  const _resultQueue: unknown[] = [];

  const chain: Record<string, any> = {};
  const methods = [
    "select",
    "selectDistinct",
    "from",
    "where",
    "orderBy",
    "groupBy",
    "insert",
    "update",
    "delete",
    "set",
    "values",
    "returning",
    "limit",
    "$dynamic",
  ];

  for (const m of methods) {
    chain[m] = vi.fn(() => chain);
  }

  // Makes the chain awaitable — pops next result from the queue
  chain.then = vi.fn(
    (onFulfilled?: (value: unknown) => unknown, onRejected?: (reason: unknown) => unknown) => {
      const data = _resultQueue.length > 0 ? _resultQueue.shift() : [];
      return Promise.resolve(data).then(onFulfilled, onRejected);
    }
  );

  // Async transaction passes chain as tx and returns callback result
  chain.transaction = vi.fn(async (fn: (tx: any) => Promise<unknown>) => {
    return await fn(chain);
  });

  // Push results that will be returned by sequential awaits
  chain._queueResult = (...results: unknown[]) => {
    _resultQueue.push(...results);
  };

  chain._clearQueue = () => {
    _resultQueue.length = 0;
  };

  return chain;
}
