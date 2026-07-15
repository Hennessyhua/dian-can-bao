export function candidateKey(candidate) {
  return candidate ? candidate.dishId || candidate.name : "";
}

export function toggleFilter(current, selected) {
  return current === selected ? "all" : selected;
}

export function chooseRandom(candidates, current) {
  if (!candidates.length) return null;
  if (candidates.length === 1) return candidates[0];
  const alternatives = candidates.filter((item) => candidateKey(item) !== candidateKey(current));
  return alternatives[Math.floor(Math.random() * alternatives.length)];
}

export function buildCandidates(orders, locationCode, mealPeriod, restaurant, months) {
  const cutoff = months === "all" ? null : new Date();
  if (cutoff) cutoff.setMonth(cutoff.getMonth() - Number(months));

  const matchedOrders = orders
    .filter((order) => locationCode === "all" || order.locationCode === locationCode)
    .filter((order) => restaurant === "all" || order.restaurant === restaurant)
    .filter((order) => !cutoff || new Date(`${order.date}T00:00:00`) >= cutoff);

  const grouped = new Map();
  matchedOrders.forEach((order) => {
    order.items.filter((item) => mealPeriod === "all" || item.mealPeriod === mealPeriod).forEach((item) => {
      const dishId = item.dishId || item.name;
      const current = grouped.get(dishId);
      const restaurants = new Set(current?.restaurants || []);
      restaurants.add(order.restaurant);
      const candidate = {
        dishId,
        name: item.name,
        quantity: item.quantity,
        restaurant: order.restaurant,
        date: order.date,
        total: order.total,
        locationCode: order.locationCode,
        locationLabel: order.locationLabel,
        mealPeriod: item.mealPeriod,
        orderCount: (current?.orderCount || 0) + 1,
        restaurants,
      };
      if (!current || order.date > current.date) {
        grouped.set(dishId, candidate);
      } else {
        current.orderCount = candidate.orderCount;
        current.restaurants = restaurants;
      }
    });
  });

  return [...grouped.values()].map((candidate) => ({
    ...candidate,
    restaurants: [...candidate.restaurants].sort((a, b) => a.localeCompare(b, "zh-CN")),
  }));
}
