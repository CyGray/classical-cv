import type { Metadata } from "next";
import { manifest } from "@/lib/manifest";
import { PageHeader } from "@/components/ui";
import { FiguresGallery } from "@/components/FiguresGallery";

export const metadata: Metadata = {
  title: "Figures · LS-Face Dashboard",
};

export default function FiguresPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Gallery"
        title="Figures"
        description="Every tracked figure across benchmarks, independence tests, and the two presentation decks. Click any figure to enlarge."
      />
      <FiguresGallery figures={manifest.figures} />
    </div>
  );
}
