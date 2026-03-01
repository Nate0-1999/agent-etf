type Props = { params: { id: string } };

export default function StrategyPage({ params }: Props) {
  return (
    <main style={{ maxWidth: 800, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>Strategy {params.id}</h1>
      <p>Approval history, benchmark comparison, and rebalance controls live here.</p>
    </main>
  );
}
