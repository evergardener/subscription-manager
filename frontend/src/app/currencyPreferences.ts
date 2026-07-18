export const commonCurrencies = ["CNY", "USD", "EUR", "GBP", "JPY", "HKD"] as const;

const supportedCurrencies = new Set(Intl.supportedValuesOf("currency"));
const regionOverrides: Record<string, string> = { AED: "AE", ARS: "AR", BGN: "BG", EUR: "EU", GBP: "GB", HKD: "HK", USD: "US", XAF: "CM", XCD: "AG", XOF: "SN" };
const currencyNames = new Intl.DisplayNames(["zh-CN"], { type: "currency" });
const regionNames = new Intl.DisplayNames(["zh-CN"], { type: "region" });

const currenciesKey = "subscription-manager-currencies";
const defaultCurrencyKey = "subscription-manager-default-currency";

export function getCurrencies(): string[] {
  try {
    const saved = JSON.parse(window.localStorage.getItem(currenciesKey) ?? "null") as unknown;
    if (Array.isArray(saved)) {
      const currencies = saved.filter((value): value is string =>
        typeof value === "string" && isSupportedCurrency(value),
      );
      if (currencies.length) return [...new Set(currencies)];
    }
  } catch {
    // Fall back to the built-in common currencies when a preference is malformed.
  }
  return [...commonCurrencies];
}

export function getDefaultCurrency(currencies = getCurrencies()): string {
  const saved = window.localStorage.getItem(defaultCurrencyKey);
  return saved && currencies.includes(saved) ? saved : "CNY";
}

export function saveCurrencyPreferences(currencies: string[], defaultCurrency: string) {
  window.localStorage.setItem(currenciesKey, JSON.stringify(currencies));
  window.localStorage.setItem(defaultCurrencyKey, defaultCurrency);
}

export function isSupportedCurrency(currency: string): boolean {
  return supportedCurrencies.has(currency.trim().toUpperCase());
}

export function currencySymbol(currency: string): string {
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency, currencyDisplay: "narrowSymbol" })
    .formatToParts(0).find((part) => part.type === "currency")?.value ?? currency;
}

export function currencyLabel(currency: string): string {
  const region = regionOverrides[currency] ?? currency.slice(0, 2);
  return `${currency} · ${currencyNames.of(currency) ?? currency}（${regionNames.of(region) ?? region}）· ${currencySymbol(currency)}`;
}
