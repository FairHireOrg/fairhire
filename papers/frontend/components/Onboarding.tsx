"use client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from "react";
const KEY = "fairhire:onboarding:v1";
const STEPS = [
    { target: "jd", title: "Start with the job description", body: "Optional — used only to surface keyword relevance. Paste it if you want that check, or leave it empty to score parsability alone." },
    { target: "resume", title: "Add the resume", body: "Choose upload or paste. Only the selected input mode is used for analysis." },
    { target: "submit", title: "Run the parsability check", body: "Choose Check parsability. The tutorial will continue when your result is ready." },
    { target: "summary", title: "Understand the result", body: "The ATS score measures how cleanly a system reads your resume — contact, headings, roles, education and keywords. The job description never affects it." },
];
export default function Onboarding({ replay, ready }: {
    replay: number;
    ready: boolean;
}) {
    const [step, setStep] = useState(-1);
    const card = useRef<HTMLDivElement>(null);
    const previousFocus = useRef<HTMLElement | null>(null);
    useEffect(() => {
        const frame = requestAnimationFrame(() => {
            let completed = false;
            try {
                completed = localStorage.getItem(KEY) === "complete";
            }
            catch { }
            if (replay || !completed) {
                previousFocus.current = document.activeElement as HTMLElement;
                setStep(0);
            }
        });
        return () => cancelAnimationFrame(frame);
    }, [replay]);
    useEffect(() => {
        if (step !== 2 || !ready)
            return;
        const frame = requestAnimationFrame(() => setStep(3));
        return () => cancelAnimationFrame(frame);
    }, [step, ready]);
    useEffect(() => {
        if (step < 0)
            return;
        const target = document.querySelector<HTMLElement>('[data-tour="' + STEPS[step].target + '"]');
        target?.classList.add("tour-target");
        target?.scrollIntoView({ behavior: "instant", block: "center" });
        card.current?.focus();
        const close = () => { try {
            localStorage.setItem(KEY, "complete");
        }
        catch { } setStep(-1); previousFocus.current?.focus(); };
        const keydown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                event.preventDefault();
                close();
            }
            if (event.key !== "Tab")
                return;
            const selector = 'button:not(:disabled), textarea:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]';
            const elements = [...(target?.querySelectorAll<HTMLElement>(selector) ?? []), ...(card.current?.querySelectorAll<HTMLElement>(selector) ?? [])].filter(el => el.getClientRects().length);
            const index = elements.indexOf(document.activeElement as HTMLElement);
            event.preventDefault();
            elements[(index + (event.shiftKey ? -1 : 1) + elements.length) % elements.length]?.focus();
        };
        document.addEventListener("keydown", keydown);
        return () => { target?.classList.remove("tour-target"); document.removeEventListener("keydown", keydown); };
    }, [step]);
    function finish() { try {
        localStorage.setItem(KEY, "complete");
    }
    catch { } setStep(-1); previousFocus.current?.focus(); }
    if (step < 0)
        return null;
    return <><div className="tour-backdrop" aria-hidden="true"/><Card ref={card} className="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-body" tabIndex={-1}>
    <span className="caption" aria-live="polite">Getting started · {step + 1} of 5</span><h2 id="tour-title">{STEPS[step].title}</h2><p id="tour-body">{STEPS[step].body}</p>
    <div className="tour-actions"><Button className="text-button" onClick={finish} variant="ghost">Skip tutorial</Button><div><Button className="button secondary" disabled={step === 0} onClick={() => setStep(step - 1)} variant="outline">Back</Button><Button className="button primary" disabled={step === 2 && !ready} onClick={() => step === STEPS.length - 1 ? finish() : setStep(step + 1)} variant="default">{step === STEPS.length - 1 ? "Finish" : step === 2 ? "Waiting for results" : "Next"}</Button></div></div>
  </Card></>;
}
