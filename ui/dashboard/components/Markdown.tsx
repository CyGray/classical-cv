import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Server component — renders trusted in-repo markdown (docs/paper). GFM tables/strike
// enabled; no raw HTML pass-through (react-markdown ignores HTML by default, which is
// the safe choice). Internal doc cross-links stay as-is; they resolve when the linked
// doc is also in the viewer.
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-doc">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
