import { clear, createStore, get, set } from "idb-keyval";

const store = createStore("hermes-business-cache", "responses");
const cacheablePrefixes = [
  "/api/v1/subscriptions",
  "/api/v1/events/upcoming",
  "/api/v1/analytics/summary",
];

export function isCacheable(path: string) {
  return cacheablePrefixes.some((prefix) => path.startsWith(prefix));
}

export function cacheEnabled() {
  try {
    return localStorage.getItem("hermes-persistent-cache") !== "false";
  } catch {
    return false;
  }
}

export async function readBusinessCache<T>(path: string): Promise<T | undefined> {
  if (!cacheEnabled() || !isCacheable(path)) return undefined;
  try {
    return await get<T>(path, store);
  } catch {
    return undefined;
  }
}

export async function writeBusinessCache(path: string, value: unknown) {
  if (!cacheEnabled() || !isCacheable(path)) return;
  try {
    await set(path, value, store);
  } catch {
    // A private browser context may disable IndexedDB; online reads must still work.
  }
}

export async function clearBusinessCache() {
  try {
    await clear(store);
  } catch {
    // Clearing an unavailable cache is already equivalent to an empty cache.
  }
}
