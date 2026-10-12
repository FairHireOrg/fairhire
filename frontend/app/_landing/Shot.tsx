"use client";
import { useLayoutEffect, useRef, useState } from "react";
import { ArrowArcLeft, ArrowArcRight, Plus } from "@phosphor-icons/react";
import { DEMO_DOC, DEMO_SCORED } from "../_lib/demo";
import { ThemeToggle } from "../_shared/ThemeToggle";
import { ChecksPanel } from "../_editor/Review";
import { ResumePage } from "../_editor/Page";
import "../_editor/editor.css";

const W = 1200;
const H = 800;

/** Scales a fixed-size layout down to the width available, never up. */
function ScaleToFit({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = () => setScale(Math.min(1, el.clientWidth / W));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} className="lp-fit" style={{ height: H * scale }}>
      <div style={{ width: W, height: H, transform: `scale(${scale})`, transformOrigin: "top left" }}>{children}</div>
    </div>
  );
}

const noop = () => {};

/**
 * A live, non-interactive copy of the editor, rendered from the same components with a fixed sample.
 * It is inert, so it can't be focused or tabbed into, and hidden from assistive tech.
 */
export function EditorShot() {
  return (
    <div className="lp-shot" aria-hidden="true">
      <ScaleToFit>
        <div className="ed lp-shot-app" inert>
          <header className="ed-bar">
            <span className="wordmark"><span className="wordmark-mark">F</span><span className="bar-brand">FairHire</span></span>
            <span className="bar-file">jordan-lee-resume.pdf</span>
            <span className="bar-spacer" />
            <ThemeToggle />
            <span className="btn btn-primary btn-sm">Export</span>
            <span className="btn btn-quiet btn-sm">Start over</span>
          </header>
          <div className="ed-main">
            <section className="ed-canvas">
              <div className="ed-toolbar">
                <span className="icon-btn"><ArrowArcLeft size={17} /></span>
                <span className="icon-btn"><ArrowArcRight size={17} /></span>
                <span className="tb-sep" />
                <span className="btn btn-sm btn-quiet"><Plus size={13} weight="bold" /> Add section</span>
              </div>
              <div className="ed-scroll">
                <ResumePage doc={DEMO_DOC} update={noop} issues={{ "demo-e2": "medium" }} />
              </div>
            </section>
            <aside className="ed-review">
              <div className="seg seg-tabs">
                <span className="seg-on">Checks<span className="count">3</span></span>
                <span>What parsers see</span>
              </div>
              <div className="review-body">
                <ChecksPanel scored={DEMO_SCORED} original={null} scoring={false} onJump={noop} />
              </div>
            </aside>
          </div>
        </div>
      </ScaleToFit>
    </div>
  );
}
