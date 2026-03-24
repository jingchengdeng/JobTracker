import { vi } from "vitest";

/**
 * Creates a chainable mock that mimics drizzle's query builder.
 * Every method returns the same chain object, so calls like
 * db.select().from().where().get() all work.
 *
 * - .get() returns null by default
 * - .all() returns [] by default
 * - .then() makes the chain awaitable (for `await query` usage)
 *
 * Use _setResolveData() to control what `await query` returns.
 */
export function createMockDb() {
  let _resolveData: unknown = [];

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
    "$dynamic",
  ];

  for (const m of methods) {
    chain[m] = vi.fn(() => chain);
  }

  chain.get = vi.fn(() => null);
  chain.all = vi.fn(() => []);
  chain.then = vi.fn((resolve: (v: unknown) => unknown) => resolve(_resolveData));
  chain._setResolveData = (data: unknown) => {
    _resolveData = data;
  };

  return chain;
}

/**
 * Standard vi.mock factory for @/db. Use with:
 *   vi.mock("@/db", mockDbModule);
 */
export function mockDbModule() {
  return { db: createMockDb() };
}
