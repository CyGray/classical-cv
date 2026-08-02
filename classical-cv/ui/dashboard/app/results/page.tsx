import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { ResultsView } from "@/components/ResultsView";

export const metadata: Metadata = {
  title: "Results · LS-Face Dashboard",
};

export default function ResultsPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Findings"
        title="Results"
        description="Every statistical test the study runs — independence, Yule's Q, Wilson intervals, McNemar, and the rest — with what it measured, what it's compared against, and what it means. Transcribed from the paper's own §4, not re-derived."
      />
      <ResultsView />
    </div>
  );
}
