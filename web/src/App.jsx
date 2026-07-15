import { useEffect, useMemo, useState } from "react";
import {
  ChartBar,
  ClockCounterClockwise,
  House,
  MapPin,
  Shuffle,
  SlidersHorizontal,
} from "@phosphor-icons/react";
import { buildCandidates, chooseRandom, toggleFilter } from "./recommendations.js";

const DEFAULT_LOCATIONS = [
  { code: "home_xuhui", label: "家（徐汇电影华苑）", shortLabel: "家 · 电影华苑" },
  { code: "office_xintiandi", label: "新天地（徕卡办公室）", shortLabel: "新天地 · 徕卡" },
];

const STORAGE_KEYS = {
  location: "dian-can-bao.location",
  mealPeriod: "dian-can-bao.meal-period",
};

const MEAL_PERIODS = [
  { id: "breakfast", label: "早饭" },
  { id: "lunch", label: "午饭" },
  { id: "dinner", label: "晚饭" },
];

function defaultMealPeriod() {
  const stored = localStorage.getItem(STORAGE_KEYS.mealPeriod);
  if (stored === "all" || MEAL_PERIODS.some((period) => period.id === stored)) return stored;
  const hour = new Date().getHours();
  if (hour < 10) return "breakfast";
  if (hour < 15) return "lunch";
  return "dinner";
}

function defaultLocation() {
  const stored = localStorage.getItem(STORAGE_KEYS.location);
  return ["all", ...DEFAULT_LOCATIONS.map((location) => location.code)].includes(stored)
    ? stored
    : "home_xuhui";
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

function MealPeriodSelector({ selected, onSelect }) {
  return (
    <div className="meal-period-list" role="group" aria-label="用餐时段，可再次点击取消筛选">
      {MEAL_PERIODS.map((period) => (
        <button
          key={period.id}
          type="button"
          aria-pressed={selected === period.id}
          className={`filter-card${selected === period.id ? " is-selected" : ""}`}
          onClick={() => onSelect(period.id)}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}

function LocationSelector({ locations, selected, onSelect, orderCounts, mealPeriod, onMealPeriod }) {
  return (
    <section className="location-section" aria-label="推荐条件">
      <h2 className="filter-heading">啥时候吃呀？</h2>
      <MealPeriodSelector selected={mealPeriod} onSelect={onMealPeriod} />
      <h2 className="filter-heading">在哪吃饭呀？</h2>
      <div className="location-list" role="group" aria-label="用餐地点，可再次点击取消筛选">
        {locations.map((location) => {
          const isSelected = selected === location.code;
          return (
            <button
              key={location.code}
              type="button"
              className={`filter-card location-option${isSelected ? " is-selected" : ""}`}
              aria-pressed={isSelected}
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

function Recommendation({ result, loading, onRandom }) {
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

      <div className="action-row single-action">
        <button
          type="button"
          className="button button-secondary"
          onClick={onRandom}
          disabled={loading || !result}
        >
          <Shuffle aria-hidden="true" />
          换一个
        </button>
      </div>
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

function HistoryView({ orders }) {
  return (
    <section className="secondary-view" aria-labelledby="history-heading">
      <p className="eyebrow">最近吃过</p>
      <h2 id="history-heading">不用靠记忆。</h2>
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
  const [selectedLocation, setSelectedLocation] = useState(defaultLocation);
  const [mealPeriod, setMealPeriod] = useState(defaultMealPeriod);
  const [restaurant, setRestaurant] = useState("all");
  const [months, setMonths] = useState("all");
  const [result, setResult] = useState(null);

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

  const restaurants = useMemo(() => [...new Set(dataset.orders
    .filter((order) => selectedLocation === "all" || order.locationCode === selectedLocation)
    .filter((order) => mealPeriod === "all" || order.items.some((item) => item.mealPeriod === mealPeriod))
    .map((order) => order.restaurant))].sort((a, b) => a.localeCompare(b, "zh-CN")), [dataset.orders, selectedLocation, mealPeriod]);
  const candidates = useMemo(() => buildCandidates(dataset.orders, selectedLocation, mealPeriod, restaurant, months), [dataset.orders, selectedLocation, mealPeriod, restaurant, months]);
  const orderCounts = useMemo(() => dataset.orders.reduce((counts, order) => {
    if (mealPeriod !== "all" && !order.items.some((item) => item.mealPeriod === mealPeriod)) return counts;
    return { ...counts, [order.locationCode]: (counts[order.locationCode] || 0) + 1 };
  }, {}), [dataset.orders, mealPeriod]);

  useEffect(() => {
    if (!loading) setResult(chooseRandom(candidates, null));
  }, [loading, selectedLocation, mealPeriod, restaurant, months, candidates]);

  function handleLocation(code) {
    const next = toggleFilter(selectedLocation, code);
    setSelectedLocation(next);
    setRestaurant("all");
    localStorage.setItem(STORAGE_KEYS.location, next);
  }

  function handleMealPeriod(period) {
    const next = toggleFilter(mealPeriod, period);
    setMealPeriod(next);
    setRestaurant("all");
    localStorage.setItem(STORAGE_KEYS.mealPeriod, next);
  }

  function handleRandom() {
    setResult((current) => chooseRandom(candidates, current));
  }

  const locations = dataset.locations.map((location) => ({
    ...location,
    shortLabel: location.shortLabel || location.label?.replace("（", " · ").replace("）", ""),
  }));

  return (
    <div className="mobile-prototype">
      <main className="app-content">
        <header className="app-header">
          <h1>今天吃什么？</h1>
          <p>点中哪个吃哪个</p>
        </header>
        {loadError ? <div className="error-banner" role="alert">{loadError}</div> : null}
        {activeTab === "home" && (
          <>
            <LocationSelector locations={locations} selected={selectedLocation} onSelect={handleLocation} orderCounts={orderCounts} mealPeriod={mealPeriod} onMealPeriod={handleMealPeriod} />
            <Recommendation result={result} loading={loading} onRandom={handleRandom} />
            <MoreFilters restaurants={restaurants} restaurant={restaurant} months={months} onRestaurant={setRestaurant} onMonths={setMonths} />
          </>
        )}
        {activeTab === "stats" && <StatsView orders={dataset.orders} />}
        {activeTab === "history" && <HistoryView orders={dataset.orders} />}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  );
}
