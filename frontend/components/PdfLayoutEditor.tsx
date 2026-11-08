"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { pdfLayoutText, type PdfTextPage } from "@/lib/pdf-layout";
import type { PdfEdits } from "@/lib/resume-source";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";
import type { TextItem } from "pdfjs-dist/types/src/display/api";
import "./pdf-layout.css";

type TextBox = { key: string; text: string; x: number; y: number; width: number; height: number; angle: number; font: string; background: string; color: string; textWidth: number };
type PageLayout = { width: number; height: number; boxes: TextBox[] };

function sampleColors(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, ratio: number) {
  const left = Math.max(0, Math.floor((x - 1) * ratio));
  const top = Math.max(0, Math.floor((y - 1) * ratio));
  const w = Math.max(1, Math.min(context.canvas.width - left, Math.ceil((width + 2) * ratio)));
  const h = Math.max(1, Math.min(context.canvas.height - top, Math.ceil((height + 2) * ratio)));
  if (left >= context.canvas.width || top >= context.canvas.height) return { background: "white", color: "black" };
  const pixels = context.getImageData(left, top, w, h).data;
  const counts = new Map<string, number>();
  for (let i = 0; i < pixels.length; i += 4) {
    const key = `${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const background = [...counts].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "255,255,255";
  const bg = background.split(",").map(Number);
  const ink = [...counts].filter(([, count]) => count > 1).sort((a, b) => {
    const distance = (v: string) => v.split(",").reduce((sum, n, i) => sum + (Number(n) - bg[i]) ** 2, 0);
    return distance(b[0]) - distance(a[0]);
  })[0]?.[0] ?? "0,0,0";
  return { background: `rgb(${background})`, color: `rgb(${ink})` };
}

function PdfPage({ page, scale, edits, disabled, onEdit, onText }: {
  page: PDFPageProxy; scale: number; edits: PdfEdits; disabled: boolean;
  onEdit: (key: string, value: string) => void;
  onText: (page: PdfTextPage) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [layout, setLayout] = useState<PageLayout | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let cancelled = false;
    let render: ReturnType<PDFPageProxy["render"]> | undefined;
    async function draw() {
      const pdfjs = await import("pdfjs-dist");
      const viewport = page.getViewport({ scale });
      const ratio = window.devicePixelRatio || 1;
      canvas!.width = Math.ceil(viewport.width * ratio);
      canvas!.height = Math.ceil(viewport.height * ratio);
      const context = canvas!.getContext("2d", { willReadFrequently: true });
      if (!context || cancelled) return;
      render = page.render({ canvas: canvas!, canvasContext: context, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] });
      await render.promise;
      const text = await page.getTextContent();
      const items = text.items.filter((item): item is TextItem => "str" in item);
      const measure = document.createElement("canvas").getContext("2d")!;
      const boxes = items.flatMap((item, index): TextBox[] => {
        if (!item.str.trim()) return [];
        const matrix = pdfjs.Util.transform(viewport.transform, item.transform);
        const height = Math.hypot(matrix[2], matrix[3]);
        if (!height) return [];
        const style = text.styles[item.fontName];
        const font = page.commonObjs.get(item.fontName) as { loadedName?: string; ascent?: number };
        const family = font.loadedName ? `"${font.loadedName}", ${style.fontFamily}` : style.fontFamily;
        const angle = Math.atan2(matrix[1], matrix[0]) + (style.vertical ? Math.PI / 2 : 0);
        const ascent = (style.ascent ?? font.ascent ?? 0.8) * height;
        const x = matrix[4] + ascent * Math.sin(angle);
        const y = matrix[5] - ascent * Math.cos(angle);
        const width = (style.vertical ? item.height : item.width) * scale;
        measure.font = `${height}px ${family}`;
        return [{ key: `${page.pageNumber}:${index}`, text: item.str, x, y, width: Math.max(width, 1), height, angle, font: family,
          textWidth: measure.measureText(item.str).width || width,
          ...sampleColors(context, x, y, width, height, ratio) }];
      });
      if (!cancelled) { setLayout({ width: viewport.width, height: viewport.height, boxes }); onText({ pageNumber: page.pageNumber, items }); }
    }
    draw().catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load PDF"); });
    return () => { cancelled = true; render?.cancel(); };
  }, [page, scale, onText]);

  const viewport = page.getViewport({ scale });
  return <div className="pdf-original-page" data-page-number={page.pageNumber} style={{ width: viewport.width, height: viewport.height }}>
    <canvas ref={canvasRef} aria-hidden="true" />
    {error && <Alert variant="destructive">{error}</Alert>}
    {layout?.boxes.map(box => {
      const value = edits[box.key] ?? box.text;
      const changed = value !== box.text;
      let textWidth = box.textWidth;
      if (changed) {
        const measure = document.createElement("canvas").getContext("2d")!;
        measure.font = `${box.height}px ${box.font}`;
        textWidth = measure.measureText(value).width;
      }
      const stretch = box.width / (textWidth || box.width);
      const style = {
        left: box.x, top: box.y, width: box.width / stretch, height: box.height,
        fontFamily: box.font, fontSize: box.height, lineHeight: `${box.height}px`,
        transform: `rotate(${box.angle}rad) scaleX(${stretch})`,
        "--pdf-background": box.background, "--pdf-ink": box.color,
      } as CSSProperties;
      return <Input key={box.key} className="pdf-text-box" data-text-key={box.key} data-edited={changed} aria-label={`Page ${page.pageNumber}: ${box.text}`} disabled={disabled}
        value={value} style={style} spellCheck={false} autoComplete="off" onChange={event => onEdit(box.key, event.target.value)} />;
    })}
  </div>;
}

export default function PdfLayoutEditor({ file, onTextExtracted, onChange, initialEdits = {}, disabled = false }: {
  file: File; onTextExtracted: (text: string) => void;
  onChange?: (text: string, edits: PdfEdits) => void; initialEdits?: PdfEdits; disabled?: boolean;
}) {
  const [pages, setPages] = useState<PDFPageProxy[]>([]);
  const [zoom, setZoom] = useState(1);
  const [fitScale, setFitScale] = useState(1);
  const [edits, setEdits] = useState<PdfEdits>(initialEdits);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const hostRef = useRef<HTMLDivElement>(null);
  const textPages = useRef(new Map<number, PdfTextPage>());
  const editsRef = useRef(edits);
  const callbacks = useRef({ onTextExtracted, onChange });
  useEffect(() => { callbacks.current = { onTextExtracted, onChange }; }, [onTextExtracted, onChange]);
  useEffect(() => {
    let cancelled = false;
    let pdf: PDFDocumentProxy | undefined;
    let task: ReturnType<typeof import("pdfjs-dist")["getDocument"]> | undefined;
    const frame = requestAnimationFrame(() => { setLoading(true); setError(""); setPages([]); setEdits(initialEdits); editsRef.current = initialEdits; textPages.current.clear(); });
    async function load() {
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = "/pdfjs/pdf.worker.min.mjs";
      const bytes = await file.arrayBuffer();
      if (cancelled) return;
      task = pdfjs.getDocument({ data: bytes, standardFontDataUrl: "/pdfjs/standard_fonts/", cMapUrl: "/pdfjs/cmaps/", cMapPacked: true, wasmUrl: "/pdfjs/wasm/" });
      pdf = await task.promise;
      const result = await Promise.all(Array.from({ length: pdf.numPages }, (_, i) => pdf!.getPage(i + 1)));
      if (!cancelled) { setPages(result); setLoading(false); }
    }
    load().catch(e => { if (!cancelled) { setError(e instanceof Error ? e.message : "Failed to load PDF"); setLoading(false); } });
    return () => { cancelled = true; cancelAnimationFrame(frame); void task?.destroy(); };
    // The source identity controls initial edits; a keystroke must never reload the PDF.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);
  useEffect(() => {
    const host = hostRef.current;
    if (!host || !pages.length) return;
    const observer = new ResizeObserver(([entry]) => {
      const widest = Math.max(...pages.map(page => page.getViewport({ scale: 1 }).width));
      setFitScale(Math.min(1.5, Math.max(0.1, (entry.contentRect.width - 32) / widest)));
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [pages]);

  const onText = useCallback((page: PdfTextPage) => {
    textPages.current.set(page.pageNumber, page);
    if (textPages.current.size === pages.length) {
      callbacks.current.onTextExtracted(pdfLayoutText([...textPages.current.values()].sort((a, b) => a.pageNumber - b.pageNumber), editsRef.current));
    }
  }, [pages.length]);
  const edit = useCallback((key: string, value: string) => {
    const next = { ...editsRef.current, [key]: value };
    editsRef.current = next;
    setEdits(next);
    const text = pdfLayoutText([...textPages.current.values()].sort((a, b) => a.pageNumber - b.pageNumber), next);
    callbacks.current.onTextExtracted(text);
    callbacks.current.onChange?.(text, next);
  }, []);

  return <Card className="pdf-layout-editor">
    <div className="pdf-toolbar">
      <Label>Zoom<Slider aria-label="Zoom" className="w-40" min={0.5} max={3} step={0.1} value={[zoom]} onValueChange={value => setZoom(value[0])} /></Label>
      <span className="muted small">{pages.length} page{pages.length !== 1 ? "s" : ""}</span>
    </div>
    <div className="pdf-original-pages" ref={hostRef}>
      {loading && <div className="pdf-loading"><Skeleton className="h-96 w-full" /><p>Rendering PDF pages...</p></div>}
      {error && <Alert variant="destructive">{error}</Alert>}
      {pages.map(page => <PdfPage key={page.pageNumber} page={page} scale={fitScale * zoom} edits={edits} disabled={disabled} onEdit={edit} onText={onText} />)}
    </div>
    <p className="muted small px-4">Click any text to edit in place. Layout is preserved exactly as the original PDF.</p>
  </Card>;
}
