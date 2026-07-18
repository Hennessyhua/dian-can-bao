// 迁移用 Service Worker：撤销早期版本的离线缓存。
// 旧实现会在任意资源请求失败时返回 index.html，可能让 JS/JSON 收到错误 MIME，
// 并让 Android 长期停留在旧界面。此文件保留在原 URL，以便已注册的客户端升级后自清理。
const LEGACY_CACHE_PREFIX = "dian-can-bao-";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter((name) => name.startsWith(LEGACY_CACHE_PREFIX))
        .map((name) => caches.delete(name)),
    );

    await self.registration.unregister();
    await self.clients.claim();

    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    await Promise.all(windows.map((client) => (
      typeof client.navigate === "function" ? client.navigate(client.url) : undefined
    )));
  })());
});
