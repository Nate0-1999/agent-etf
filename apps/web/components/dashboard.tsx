import type { StrategyRow } from "../lib/types";

const rows: StrategyRow[] = [
  { id: "heavy-metal-v1", name: "Heavy Metals Equal Weight", status: "draft", ytd: 0.0 },
  { id: "gold-baseline", name: "Gold Baseline", status: "active", ytd: 0.12 },
  { id: "sp500-baseline", name: "S&P 500 Baseline", status: "active", ytd: 0.08 },
];

export function Dashboard() {
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "2rem 1rem" }}>
      <h1 style={{ fontSize: "2.2rem", marginBottom: "0.25rem" }}>agent-etf</h1>
      <p style={{ marginTop: 0 }}>Paper-first strategy generator with strict approval gates.</p>
      <section style={{ background: "var(--card)", borderRadius: 16, padding: "1rem" }}>
        <h2>Strategy Stable</h2>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th align="left">Strategy</th>
              <th align="left">Status</th>
              <th align="right">YTD</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{row.status}</td>
                <td align="right">{(row.ytd * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
