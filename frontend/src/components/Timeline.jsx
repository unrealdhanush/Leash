import React, { useEffect, useRef } from "react";
import { chapterFor } from "../chapters.js";
import { slug } from "../format.js";
import EventView from "./EventView.jsx";

export default function Timeline({ scenes, run }) {
  const end = useRef(null);
  const count = scenes.reduce((n, s) => n + s.items.length + 1, 0);
  useEffect(() => {
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 120;
    if (nearBottom && run.status === "running") end.current?.scrollIntoView({ block: "end" });
  }, [count, run.status]);

  if (!scenes.length) {
    return (
      <div className="empty" data-testid="timeline-empty">
        <h2>The agent is picking this up…</h2>
        <p>Each step appears here the moment it happens.</p>
      </div>
    );
  }
  return (
    <div className="timeline" data-testid="timeline">
      {scenes.map((scene, i) => {
        const chapter = chapterFor(scene.key);
        return (
          <article className="scene" key={i} id={`chapter-${scene.key}`} data-chapter={scene.key} data-testid={`scene-${slug(scene.title)}`}>
            <header className="scene-head">
              <span className="node mono">{chapter?.n ?? "·"}</span>
              <h2 className="scene-title" data-testid={`chapter-title-${scene.key}`}>{chapter?.title ?? scene.title}</h2>
              {chapter && <p className="scene-why">{chapter.why}</p>}
              {chapter && <p className="scene-orig mono" data-testid={`scene-original-${scene.key}`}>{scene.title}</p>}
            </header>
            <div className="scene-body">
              {scene.items.map((e) => <EventView key={e._i} e={e} />)}
            </div>
          </article>
        );
      })}
      {run.status === "running" && <div className="working" data-testid="run-working"><span className="dot" />agent working…</div>}
      {run.status === "waiting_approval" && <div className="working waiting" data-testid="run-waiting"><span className="dot" />waiting for your answer in the approval panel</div>}
      <div ref={end} />
    </div>
  );
}
