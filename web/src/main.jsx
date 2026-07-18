import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import { clearLegacyOfflineState, resolveAppScope } from "./cache-migration.js";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

const CACHE_RESET_KEY = "dian-can-bao.cache-reset.v2";

if (import.meta.env.PROD && ("serviceWorker" in navigator || "caches" in window)) {
  window.addEventListener("load", () => {
    if (sessionStorage.getItem(CACHE_RESET_KEY)) return;

    const scopeUrl = resolveAppScope(import.meta.env.BASE_URL, document.baseURI);
    clearLegacyOfflineState({
      serviceWorkerContainer: navigator.serviceWorker,
      cacheStorage: window.caches,
      scopeUrl,
    })
      .then(({ changed }) => {
        if (!changed) return;
        sessionStorage.setItem(CACHE_RESET_KEY, "done");
        window.location.reload();
      })
      .catch((error) => {
        console.warn("旧版离线缓存清理失败", error);
      });
  });
}
