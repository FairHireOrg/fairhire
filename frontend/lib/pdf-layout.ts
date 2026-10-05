import type { TextItem } from "pdfjs-dist/types/src/display/api";
import type { PdfEdits } from "./resume-source";

export type PdfTextPage = { pageNumber: number; items: TextItem[] };

/** Keep PDF reading order, line breaks and column gaps; never reorder into a template. */
export function pdfLayoutText(pages: PdfTextPage[], edits: PdfEdits): string {
  return pages.map(page => {
    let text = "";
    let previous: TextItem | undefined;
    for (const [index, item] of page.items.entries()) {
      const value = edits[`${page.pageNumber}:${index}`] ?? item.str;
      const size = Math.hypot(item.transform[2], item.transform[3]) || 12;
      if (previous) {
        const prevSize = Math.hypot(previous.transform[2], previous.transform[3]) || size;
        const newLine = previous.hasEOL || Math.abs(item.transform[5] - previous.transform[5]) > Math.min(size, prevSize) * 0.5;
        if (newLine) text += "\n";
        else {
          const gap = item.transform[4] - (previous.transform[4] + previous.width);
          if (gap > size * 0.2) text += " ".repeat(Math.min(100, Math.max(1, Math.round(gap / (size * 0.5)))));
        }
      }
      text += value;
      previous = item;
    }
    return text.trimEnd();
  }).join("\n\n");
}
