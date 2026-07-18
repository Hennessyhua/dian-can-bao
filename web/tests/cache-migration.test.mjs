import assert from "node:assert/strict";
import test from "node:test";
import { clearLegacyOfflineState, resolveAppScope } from "../src/cache-migration.js";

test("relative build base resolves to this GitHub Pages project only", () => {
  assert.equal(
    resolveAppScope("./", "https://hennessyhua.github.io/dian-can-bao/?v=current"),
    "https://hennessyhua.github.io/dian-can-bao/",
  );
});

test("legacy service worker and app caches are removed without touching other sites", async () => {
  const unregistered = [];
  const deleted = [];
  const serviceWorkerContainer = {
    async getRegistrations() {
      return [
        { scope: "https://example.test/dian-can-bao/", unregister: async () => { unregistered.push("app"); return true; } },
        { scope: "https://example.test/other/", unregister: async () => { unregistered.push("other"); return true; } },
      ];
    },
  };
  const cacheStorage = {
    async keys() { return ["dian-can-bao-v1", "unrelated-cache"]; },
    async delete(name) { deleted.push(name); return true; },
  };

  const result = await clearLegacyOfflineState({
    serviceWorkerContainer,
    cacheStorage,
    scopeUrl: "https://example.test/dian-can-bao/",
  });

  assert.deepEqual(unregistered, ["app"]);
  assert.deepEqual(deleted, ["dian-can-bao-v1"]);
  assert.deepEqual(result, { changed: true, removedRegistrations: 1, removedCaches: 1 });
});

test("clean clients do not trigger a reload migration", async () => {
  const result = await clearLegacyOfflineState({
    serviceWorkerContainer: { getRegistrations: async () => [] },
    cacheStorage: { keys: async () => [] },
    scopeUrl: "https://example.test/dian-can-bao/",
  });
  assert.equal(result.changed, false);
});

test("a cache recreated by an in-flight legacy request is removable on the next load", async () => {
  const cacheNames = new Set(["dian-can-bao-v1"]);
  const cacheStorage = {
    async keys() { return [...cacheNames]; },
    async delete(name) { return cacheNames.delete(name); },
  };

  const result = await clearLegacyOfflineState({
    serviceWorkerContainer: { getRegistrations: async () => [] },
    cacheStorage,
    scopeUrl: "https://example.test/dian-can-bao/",
  });

  assert.equal(result.changed, true);
  assert.deepEqual([...cacheNames], []);
});
