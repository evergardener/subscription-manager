const currencyNames = new Intl.DisplayNames(["zh-CN"], { type: "currency" });

export function Money({ amount, currency }: { amount: string; currency: string }) {
  const value = Number(amount);
  return <span title={currencyNames.of(currency) ?? currency}>{new Intl.NumberFormat("zh-CN", { style: "currency", currency, maximumFractionDigits: 2 }).format(value)} <small>{currency}</small></span>;
}
