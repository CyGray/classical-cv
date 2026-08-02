import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { StatusView } from "@/components/StatusView";
import { manifest } from "@/lib/manifest";

export const metadata: Metadata = {
  title: "Study status · LS-Face Dashboard",
};

export default function StatusPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Flagship view"
        title="Study status"
        description={
          <>
            Every run leg, the master checklist, and how each paper section tracks the
            data on disk. Hand-maintained in{" "}
            <code className="rounded bg-elevated px-1 py-0.5 text-sm">study_status.yml</code>,
            last updated {manifest.study_status.updated ?? "unknown"}.
          </>
        }
      />
      <StatusView />
    </div>
  );
}
