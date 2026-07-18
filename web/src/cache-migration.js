const LEGACY_CACHE_PREFIX = "dian-can-bao-";

export async function clearLegacyOfflineState({
  serviceWorkerContainer,
  cacheStorage,
  scopeUrl,
}) {
  let removedRegistrations = 0;
  let removedCaches = 0;

  if (serviceWorkerContainer?.getRegistrations) {
    const registrations = await serviceWorkerContainer.getRegistrations();
    const matching = registrations.filter((registration) => registration.scope.startsWith(scopeUrl));
    const results = await Promise.all(matching.map((registration) => registration.unregister()));
    removedRegistrations = results.filter(Boolean).length;
  }

  if (cacheStorage?.keys) {
    const cacheNames = await cacheStorage.keys();
    const matching = cacheNames.filter((name) => name.startsWith(LEGACY_CACHE_PREFIX));
    const results = await Promise.all(matching.map((name) => cacheStorage.delete(name)));
    removedCaches = results.filter(Boolean).length;
  }

  return {
    changed: removedRegistrations > 0 || removedCaches > 0,
    removedRegistrations,
    removedCaches,
  };
}
