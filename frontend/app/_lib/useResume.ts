"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { importFile, importText, scoreDocument } from "./api";
import { emptyDoc } from "./doc";
import type { Ats, Imported, ResumeDoc, Scored } from "./types";

const KEY = "fairhire:draft:v2";
type Draft = {
  doc: ResumeDoc;
  original: Ats | null;
  originalText: string;
  filename: string;
  notes: string[];
};

function load(): Draft | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch { return null; }
}
function save(d: Draft | null) {
  try { d ? localStorage.setItem(KEY, JSON.stringify(d)) : localStorage.removeItem(KEY); } catch { /* private mode */ }
}

const HISTORY_GAP = 800;
const HISTORY_MAX = 100;

export type Status = "loading" | "empty" | "importing" | "ready";

/**
 * Single source of truth for the editor.
 *
 * `doc` is the only thing the user edits. Scoring is a pure function of `doc`
 * computed by the server, re-requested (debounced) after each change, so the
 * checks on screen always describe the document on screen.
 */
export function useResume() {
  const [status, setStatus] = useState<Status>("loading");
  const [doc, setDoc] = useState<ResumeDoc>(emptyDoc);
  const [scored, setScored] = useState<Scored | null>(null);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState<Omit<Draft, "doc">>({ original: null, originalText: "", filename: "", notes: [] });
  const seq = useRef(0);
  const cache = useRef(new Map<string, Scored>());

  // Undo history. Edits within HISTORY_GAP ms collapse into one step, so typing a sentence is one undo.
  const docRef = useRef<ResumeDoc>(doc);
  const past = useRef<ResumeDoc[]>([]);
  const future = useRef<ResumeDoc[]>([]);
  const lastEdit = useRef(0);
  const [depth, setDepth] = useState({ undo: 0, redo: 0 });
  const replaceDoc = useCallback((next: ResumeDoc, keepHistory = false) => {
    docRef.current = next;
    if (!keepHistory) { past.current = []; future.current = []; lastEdit.current = 0; }
    setDoc(next);
    setDepth({ undo: past.current.length, redo: future.current.length });
  }, []);

  // Restore the draft after mount (localStorage is not available during SSR).
  useEffect(() => {
    const d = load();
    if (d?.doc) {
      replaceDoc(d.doc);
      setMeta({ original: d.original, originalText: d.originalText, filename: d.filename, notes: d.notes ?? [] });
      setStatus("ready");
    } else setStatus("empty");
  }, [replaceDoc]);

  // Persist.
  useEffect(() => {
    if (status === "ready") save({ doc, ...meta });
  }, [doc, meta, status]);

  // Re-score after edits. Deterministic server-side, so identical docs are cached.
  useEffect(() => {
    if (status !== "ready") return;
    const key = JSON.stringify(doc);
    const hit = cache.current.get(key);
    if (hit) { setScored(hit); setScoring(false); return; }
    const mine = ++seq.current;
    const ctl = new AbortController();
    setScoring(true);
    const t = setTimeout(async () => {
      try {
        const res = await scoreDocument(doc, ctl.signal);
        if (mine !== seq.current) return;
        cache.current.set(key, res);
        setScored(res);
        setError("");
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        if (mine === seq.current) setError(e instanceof Error ? e.message : "Could not check the resume.");
      } finally {
        if (mine === seq.current) setScoring(false);
      }
    }, 350);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [doc, status]);

  const adopt = useCallback((res: Imported) => {
    cache.current.set(JSON.stringify(res.document), res);
    replaceDoc(res.document);
    setScored(res);
    setMeta({ original: res.original, originalText: res.original_text, filename: res.source.filename, notes: res.source.notes });
    setError("");
    setStatus("ready");
  }, [replaceDoc]);

  const run = useCallback(async (job: () => Promise<Imported>) => {
    setStatus("importing");
    setError("");
    try { adopt(await job()); }
    catch (e) {
      setError(e instanceof Error ? e.message : "Could not read this resume.");
      setStatus(prev => (prev === "importing" ? "empty" : prev));
    }
  }, [adopt]);

  const fromFile = useCallback((f: File) => run(() => importFile(f)), [run]);
  const fromText = useCallback((t: string) => run(() => importText(t)), [run]);
  const startBlank = useCallback(() => {
    replaceDoc(emptyDoc()); setScored(null);
    setMeta({ original: null, originalText: "", filename: "", notes: [] });
    setError(""); setStatus("ready");
  }, [replaceDoc]);
  const reset = useCallback(() => {
    save(null); cache.current.clear(); replaceDoc(emptyDoc()); setScored(null); setError("");
    setMeta({ original: null, originalText: "", filename: "", notes: [] }); setStatus("empty");
  }, [replaceDoc]);

  const update = useCallback((fn: (d: ResumeDoc) => ResumeDoc) => {
    const prev = docRef.current;
    const next = fn(prev);
    if (next === prev) return;
    const now = Date.now();
    if (!past.current.length || now - lastEdit.current > HISTORY_GAP) {
      past.current.push(prev);
      if (past.current.length > HISTORY_MAX) past.current.shift();
    }
    future.current = [];
    lastEdit.current = now;
    replaceDoc(next, true);
  }, [replaceDoc]);

  const undo = useCallback(() => {
    const prev = past.current.pop();
    if (!prev) return;
    future.current.push(docRef.current);
    lastEdit.current = 0;
    replaceDoc(prev, true);
  }, [replaceDoc]);

  const redo = useCallback(() => {
    const next = future.current.pop();
    if (!next) return;
    past.current.push(docRef.current);
    lastEdit.current = 0;
    replaceDoc(next, true);
  }, [replaceDoc]);

  return useMemo(() => ({
    status, doc, update, undo, redo, canUndo: depth.undo > 0, canRedo: depth.redo > 0,
    scored, scoring, error, setError, meta, fromFile, fromText, startBlank, reset,
  }), [status, doc, update, undo, redo, depth, scored, scoring, error, meta, fromFile, fromText, startBlank, reset]);
}
