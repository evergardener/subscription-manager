export const commonCurrencies = ["CNY", "USD", "EUR", "GBP", "JPY", "HKD"] as const;

const currenciesKey = "subscription-manager-currencies";
const defaultCurrencyKey = "subscription-manager-default-currency";

export function getCurrencies(): string[] {
  try {
    const saved = JSON.parse(localStorage.getItem(currenciesKey) ?? "null") as unknown;
    if (Array.isArray(saved)) {
      const currencies = saved.filter((value): value is string =>
        typeof value === "string" && /^[A-Z]{3}$/.test(value),
      );
      if (currencies.length) return [...new Set(currencies)];
    }
  } catch {
    // Fall back to the built-in ISO 4217 shortlist when a preference is malformed.
  }
  return [...commonCurrencies];
}

export function getDefaultCurrency(currencies = getCurrencies()): string {
  const saved = localStorage.getItem(defaultCurrencyKey);
  return saved && currencies.includes(saved) ? saved : "CNY";
}

export function saveCurrencyPreferences(currencies: string[], defaultCurrency: string) {
  localStorage.setItem(currenciesKey, JSON.stringify(currencies));
  localStorage.setItem(defaultCurrencyKey, defaultCurrency);
}
