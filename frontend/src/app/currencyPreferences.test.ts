import { beforeEach, describe, expect, test } from "vitest";

import { currencyLabel, getCurrencies, isSupportedCurrency, saveCurrencyPreferences } from "./currencyPreferences";

describe("currency preferences", () => {
  beforeEach(() => window.localStorage.clear());

  test("accepts ISO currencies outside the former handwritten shortlist", () => {
    expect(isSupportedCurrency("kzt")).toBe(true);
    expect(isSupportedCurrency("ABC")).toBe(false);
  });

  test("drops invalid persisted currency codes", () => {
    window.localStorage.setItem("subscription-manager-currencies", JSON.stringify(["USD", "ABC", "KZT"]));
    expect(getCurrencies()).toEqual(["USD", "KZT"]);
  });

  test("formats a Chinese name, region, and symbol", () => {
    expect(currencyLabel("USD")).toContain("USD · 美元（美国）· $");
  });

  test("saves valid preferences", () => {
    saveCurrencyPreferences(["CNY", "KZT"], "KZT");
    expect(getCurrencies()).toEqual(["CNY", "KZT"]);
  });
});
