import React, { useEffect, useState } from "react";
import { CHAPTERS } from "../chapters.js";
import { ACTIVE } from "../format.js";

const LABEL = {
  done: "done",
  current: "happening now",
  waiting: "waiting for you",
  stopped: "stopped here",
  upcoming: "up next",
  skipped: "not needed",
  unreached: "not reached",
};

export default function SceneRail({ scenes, run, onJump, notes, onNotes }) {
  const [viewing, setViewing] = useState(null);
  const live = ACTIVE.includes(run.status);
  const last = scenes.length ? CHAPTERS.findIndex((c) => c.key === scenes[scenes.length - 1].key) : -1;

  const stateOf = (chapter, i) => {
    if (!scenes.some((s) => s.key === chapter.key)) {
      if (i < last) return "skipped";
      return live ? "upcoming" : "unreached";
    }
    if (i !== last) return "done";
    if (live) return run.status === "waiting_approval" ? "waiting" : "current";
    return run.status === "done" ? "done" : "stopped";
  };

  useEffect(() => {
    const onScroll = () => {
      let key = null;
      document.querySelectorAll("[data-chapter]").forEach((el) => {
        if (el.getBoundingClientRect().top <= 180) key = el.dataset.chapter;
      });
      setViewing(key);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [scenes.length]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
      if (e.key === "n" && onNotes) onNotes();
      const chapter = CHAPTERS.find((c) => c.n === e.key);
      if (chapter && scenes.some((s) => s.key === chapter.key)) onJump(chapter.key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scenes.length, onJump, onNotes]);

  return (
    <nav className="rail" data-testid="scene-rail" aria-label="Chapters">
      <p className="rail-head">Chapters <span className="mono">press 0–8</span></p>
      <ol className="rail-list">
        {CHAPTERS.map((chapter, i) => {
          const state = stateOf(chapter, i);
          const scene = scenes.find((s) => s.key === chapter.key);
          const flagged = scene?.items.some((e) => (e.event === "charge" || e.event === "checkout") && !e.as_expected);
          return (
            <li key={chapter.key}>
              <button
                className={`rail-item ${state} ${viewing === chapter.key ? "viewing" : ""}`}
                disabled={!scene}
                onClick={() => onJump(chapter.key)}
                data-testid={`jump-${chapter.key}`}
                data-state={state}
              >
                <span className="rail-n mono">{chapter.n}</span>
                <span className="rail-text">
                  <span className="rail-title">{chapter.short}</span>
                  <span className="rail-state" data-testid={`jump-${chapter.key}-state`}>{flagged ? "unexpected result" : LABEL[state]}</span>
                </span>
                {flagged && <span className="rail-flag" />}
              </button>
            </li>
          );
        })}
      </ol>
      {onNotes && (
        <label className="switch rail-notes" data-testid="presenter-notes-toggle">
          <input type="checkbox" checked={notes} onChange={onNotes} data-testid="presenter-notes-input" />
          <span className="track"><span className="thumb" /></span>
          <span className="switch-label">Presenter notes<small>what to say at each chapter · press N</small></span>
        </label>
      )}
    </nav>
  );
}
