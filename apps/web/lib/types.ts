export type StrategyRow = {
  id: string;
  name: string;
  status: "draft" | "active" | "paused";
  ytd: number;
};
