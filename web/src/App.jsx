import { useEffect, useMemo, useState } from "react";
import {
  ChartBar,
  Check,
  ClockCounterClockwise,
  House,
  MapPin,
  Shuffle,
  SlidersHorizontal,
} from "@phosphor-icons/react";

const DEFAULT_LOCATIONS = [
  { code: "home_xuhui", label: "家（徐汇电影华苑）", shortLabel: "家 · 徐汇电影华苑" },
  { code: "office_xintiandi", label: "新天地（徕卡办公室）", shortLabel: "新天地 · 徕卡办公室" },
];

const STORAGE_KEYS = {
  location: "dian-can-bao.location",
  decisions: "dian-can-bao.decisions",
};

function readStoredDecisions() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.decisions) || "[]");
  } catch {
    return [];
  }
}

function formatDate(value) {
  if (!value) return "日期未知";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return `${month}月${day}日`;
}

function formatMoney(value) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function candidateKey(candidate) {
  return candidate ? `${candidate.restaurant}::${candidate.name}::${candidate.date}` : "";
}

function chooseRandom(candidates, current) {
  if (!candidates.length) return null;
  if (candidates.length === 1) return candidates[0];
  const alternatives = candidates.filter((item) => candidateKey(item) !== candidateKey(current));
  return alternatives[Math.floor(Math.random() * alternatives.length)];
}

function buildCandidates(orders, locationCode, restaurant, months) {
  const cutoff = months === "all" ? null : new Date();
  if (cutoff) cutoff.setMonth(cutoff.getMonth() - Number(months));

  return orders
    .filter((order) => order.locationCode === locationCode)
    .filter((order) => restaurant === "all" || order.restaurant === restaurant)
    .filter((order) => !cutoff || new Date(`${order.date}T00:00:00`) >= cutoff)
    .flatMap((order) =>
      order.items.map((item) => ({
        name: item.name,
        quantity: item.quantity,
        restaurant: order.restaurant,
        date: order.date,
        total: order.total,
        locationCode: order.locationCode,
        locationLabel: order.locationLabel,
      })),
    );
}

function LocationSelector({ locations, selected, onSelect, orderCounts }) {
  return (
    <section className="location-section" aria-labelledby="location-heading">
      <h2 id="location-heading">今天在哪里吃？</h2>
      <div className="location-list" role="radiogroup" aria-label="用餐地点">
        {locations.map((location) => {
          const isSelected = selected === location.code;
          return (
            <button
              key={location.code}
              type="button"
              className={`location-option${isSelected ? " is-selected" : ""}`}
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelect(location.code)}
            >
              <span className="location-icon" aria-hidden="true"><MapPin weight={isSelected ? "fill" : "regular"} /></span>
              <span>
                <strong>{location.shortLabel}</strong>
                <small>{orderCounts[location.code] || 0} 条历史订单</small>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Recommendation({ result, loading, onRandom, onConfirm, statusMessage }) {
  return (
    <section className="recommendation" aria-labelledby="recommendation-heading" aria-busy={loading}>
      <p className="eyebrow" id="recommendation-heading">为你推荐</p>
      <div className="recommendation-live" aria-live="polite">
        {loading ? (
          <div className="state-message">正在整理你的历史菜单…</div>
        ) : result ? (
          <>
            <h3>{result.name}</h3>
            <div className="title-rule" aria-hidden="true" />
            <p className="restaurant-name">{result.restaurant}</p>
            <p className="last-ordered">上次点过 · {formatDate(result.date)}</p>
          </>
        ) : (
          <div className="state-message">
            <strong>这个地点还没有可推荐的菜</strong>
            <span>更新美团订单，或调整更多筛选后再试试。</span>
          </div>
        )}
      </div>

      <div className={`action-row${result ? "" : " single-action"}`}>
        <button type="button" className="button button-secondary" onClick={onRandom} disabled={loading}>
          <Shuffle aria-hidden="true" />
          {result ? "换一个" : "帮我选一个"}
        </button>
        {result && (
          <button type="button" className="button button-primary" onClick={onConfirm}>
            <Check aria-hidden="true" />
            就吃这个
          </button>
        )}
      </div>
      {statusMessage && <p className="confirmation" role="status">{statusMessage}</p>}
    </section>
  );
}

function MoreFilters({ restaurants, restaurant, months, onRestaurant, onMonths }) {
  return (
    <details className="more-filters">
      <summary><SlidersHorizontal aria-hidden="true" />更多筛选</summary>
      <div className="filter-fields">
        <label>
          餐厅
          <select value={restaurant} onChange={(event) => onRestaurant(event.target.value)}>
            <option value="all">全部餐厅</option>
            {restaurants.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label>
          时间范围
          <select value={months} onChange={(event) => onMonths(event.target.value)}>
            <option value="all">全部历史</option>
            <option value="1">最近 1 个月</option>
            <option value="3">最近 3 个月</option>
            <option value="6">最近 6 个月</option>
          </select>
        </label>
      </div>
    </details>
  );
}

function StatsView({ orders }) {
  const restaurantStats = useMemo(() => {
    const counts = new Map();
    orders.forEach((order) => counts.set(order.restaurant, (counts.get(order.restaurant) || 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [orders]);

  const dishStats = useMemo(() => {
    const counts = new Map();
    orders.forEach((order) => order.items.forEach((item) => counts.set(item.name, (counts.get(item.name) || 0) + item.quantity)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [orders]);

  const total = orders.reduce((sum, order) => sum + Number(order.total || 0), 0);

  return (
    <section className="secondary-view" aria-labelledby="stats-heading">
      <p className="eyebrow">你的口味档案</p>
      <h2 id="stats-heading">吃过，也算数。</h2>
      <div className="stat-summary">
        <div><strong>{orders.length}</strong><span>历史订单</span></div>
        <div><strong>{formatMoney(total)}</strong><span>累计消费</span></div>
      </div>
      <section className="ranking">
        <h3>最常点的餐厅</h3>
        <ol>{restaurantStats.map(([name, count]) => <li key={name}><span>{name}</span><strong>{count} 次</strong></li>)}</ol>
      </section>
      <section className="ranking">
        <h3>最常点的菜</h3>
        <ol>{dishStats.map(([name, count]) => <li key={name}><span>{name}</span><strong>{count} 份</strong></li>)}</ol>
      </section>
    </section>
  );
}

function HistoryView({ orders, decisions }) {
  return (
    <section className="secondary-view" aria-labelledby="history-heading">
      <p className="eyebrow">最近吃过</p>
      <h2 id="history-heading">不用靠记忆。</h2>
      {decisions.length > 0 && (
        <section className="decision-log">
          <h3>已决定</h3>
          {decisions.slice(0, 5).map((decision) => (
            <article key={decision.id}>
              <strong>{decision.name}</strong>
              <span>{decision.restaurant} · {decision.locationLabel}</span>
            </article>
          ))}
        </section>
      )}
      <div className="history-list">
        {orders.slice(0, 30).map((order, index) => (
          <article key={`${order.date}-${order.restaurant}-${index}`}>
            <div><time dateTime={order.date}>{formatDate(order.date)}</time><span>{order.locationLabel}</span></div>
            <h3>{order.restaurant}</h3>
            <p>{order.items.map((item) => `${item.name}${item.quantity > 1 ? ` ×${item.quantity}` : ""}`).join("、")}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function BottomNav({ active, onChange }) {
  const items = [
    { id: "home", label: "首页", Icon: House },
    { id: "stats", label: "统计", Icon: ChartBar },
    { id: "history", label: "历史", Icon: ClockCounterClockwise },
  ];
  return (
    <nav className="bottom-nav" aria-label="主要导航">
      {items.map(({ id, label, Icon }) => (
        <button key={id} type="button" className={active === id ? "is-active" : ""} aria-current={active === id ? "page" : undefined} onClick={() => onChange(id)}>
          <Icon weight={active === id ? "fill" : "regular"} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export function App() {
  const [dataset, setDataset] = useState({ locations: DEFAULT_LOCATIONS, orders: [] });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [activeTab, setActiveTab] = useState("home");
  const [selectedLocation, setSelectedLocation] = useState(() => localStorage.getItem(STORAGE_KEYS.location) || "home_xuhui");
  const [restaurant, setRestaurant] = useState("all");
  const [months, setMonths] = useState("all");
  const [result, setResult] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [decisions, setDecisions] = useState(readStoredDecisions);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${import.meta.env.BASE_URL}data/orders.public.json`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setDataset({
          locations: data.locations?.length ? data.locations : DEFAULT_LOCATIONS,
          orders: Array.isArray(data.orders) ? data.orders : [],
        });
        setLoading(false);
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          setLoadError("订单数据暂时没有加载成功，请刷新后重试。");
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const restaurants = useMemo(() => [...new Set(dataset.orders.filter((order) => order.locationCode === selectedLocation).map((order) => order.restaurant))].sort((a, b) => a.localeCompare(b, "zh-CN")), [dataset.orders, selectedLocation]);
  const candidates = useMemo(() => buildCandidates(dataset.orders, selectedLocation, restaurant, months), [dataset.orders, selectedLocation, restaurant, months]);
  const orderCounts = useMemo(() => dataset.orders.reduce((counts, order) => ({ ...counts, [order.locationCode]: (counts[order.locationCode] || 0) + 1 }), {}), [dataset.orders]);

  useEffect(() => {
    if (!loading) setResult(chooseRandom(candidates, null));
  }, [loading, selectedLocation, restaurant, months, candidates]);

  function handleLocation(code) {
    setSelectedLocation(code);
    setRestaurant("all");
    setStatusMessage("");
    localStorage.setItem(STORAGE_KEYS.location, code);
  }

  function handleRandom() {
    setResult((current) => chooseRandom(candidates, current));
    setStatusMessage("");
  }

  function handleConfirm() {
    if (!result) return;
    const decision = { ...result, id: crypto.randomUUID(), decidedAt: new Date().toISOString() };
    const next = [decision, ...decisions].slice(0, 100);
    setDecisions(next);
    localStorage.setItem(STORAGE_KEYS.decisions, JSON.stringify(next));
    setStatusMessage(`已记下：今天吃${result.name}`);
  }

  const locations = dataset.locations.map((location) => ({
    ...location,
    shortLabel: location.shortLabel || location.label?.replace("（", " · ").replace("）", ""),
  }));

  return (
    <div className="mobile-prototype">
      <header className="app-header">
        <div><h1>点餐宝</h1><p>30秒帮你决定吃什么</p></div>
        <span className="privacy-note">仅展示地点标签</span>
      </header>

      <main className="app-content">
        {loadError ? <div className="error-banner" role="alert">{loadError}</div> : null}
        {activeTab === "home" && (
          <>
            <LocationSelector locations={locations} selected={selectedLocation} onSelect={handleLocation} orderCounts={orderCounts} />
            <Recommendation result={result} loading={loading} onRandom={handleRandom} onConfirm={handleConfirm} statusMessage={statusMessage} />
            <MoreFilters restaurants={restaurants} restaurant={restaurant} months={months} onRestaurant={setRestaurant} onMonths={setMonths} />
          </>
        )}
        {activeTab === "stats" && <StatsView orders={dataset.orders} />}
        {activeTab === "history" && <HistoryView orders={dataset.orders} decisions={decisions} />}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  );
}
