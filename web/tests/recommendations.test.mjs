import assert from "node:assert/strict";
import test from "node:test";

import { buildCandidates, chooseRandom, toggleFilter } from "../src/recommendations.js";

const repeatedDishOrders = [
  {
    date: "2026-07-14",
    restaurant: "六姐光启城店",
    locationCode: "home_xuhui",
    locationLabel: "家（徐汇电影华苑）",
    total: 40,
    items: [{ name: "霸气嫩牛套餐", dishId: "same-dish", mealPeriod: "dinner", quantity: 1 }],
  },
  {
    date: "2026-06-14",
    restaurant: "六姐另一分店",
    locationCode: "home_xuhui",
    locationLabel: "家（徐汇电影华苑）",
    total: 42,
    items: [{ name: "霸气嫩牛套餐", dishId: "same-dish", mealPeriod: "dinner", quantity: 1 }],
  },
];

test("repeated dates and branches create one random candidate per dishId", () => {
  const candidates = buildCandidates(repeatedDishOrders, "home_xuhui", "dinner", "all", "all");
  assert.equal(candidates.length, 1);
  assert.equal(candidates[0].date, "2026-07-14");
  assert.equal(candidates[0].orderCount, 2);
  assert.deepEqual(candidates[0].restaurants, ["六姐光启城店", "六姐另一分店"]);
});

test("shuffle never returns the current canonical dish when alternatives exist", () => {
  const current = { dishId: "dish-a", name: "菜A" };
  const result = chooseRandom([current, { dishId: "dish-b", name: "菜B" }], current);
  assert.equal(result.dishId, "dish-b");
});

test("clicking an active filter again clears it to all", () => {
  assert.equal(toggleFilter("lunch", "lunch"), "all");
  assert.equal(toggleFilter("home_xuhui", "home_xuhui"), "all");
  assert.equal(toggleFilter("all", "dinner"), "dinner");
});

test("all values include every meal period and location", () => {
  const anotherLocation = {
    ...repeatedDishOrders[0],
    date: "2026-07-15",
    restaurant: "早餐店",
    locationCode: "office_xintiandi",
    items: [{ name: "鲜肉包", dishId: "breakfast-dish", mealPeriod: "breakfast", quantity: 1 }],
  };
  const candidates = buildCandidates([...repeatedDishOrders, anotherLocation], "all", "all", "all", "all");
  assert.deepEqual(new Set(candidates.map((item) => item.dishId)), new Set(["same-dish", "breakfast-dish"]));
});
