const currencyNames = new Intl.DisplayNames(["zh-CN"], { type: "currency" });

export function Money({ amount, currency }: { amount: string; currency: string }) {
  const value = Number(amount);
  const name = currencyNames.of(currency) ?? currency;
  return <span title={`${name} (${currency})`} aria-label={`${currency} ${amount}`}>{new Intl.NumberFormat("zh-CN", { style: "currency", currency, currencyDisplay: "narrowSymbol", maximumFractionDigits: 2 }).format(value)}</span>;
}
