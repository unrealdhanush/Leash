import React, { useEffect, useRef } from "react";
import { groupScenes, slug } from "../format.js";
import EventView from "./EventView.jsx";

export default function Timeline({ events, run }) {
  const end = useRef(null);
  useEffect(() => {
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 400;
    if (nearBottom) end.current?.scrollIntoView({ block: "end" });
  }, [events.length]);

  if (!events.length) {
    return (
      <div className="empty" data-testid="timeline-empty">
        <h2>{run ? "Starting the run…" : "No run yet"}</h2>
        <p>
          Start a run to walk through all eight scenes against the live sandbox: the agent reads a vendor quote,
          policy code decides, and a virtual card enforces the decision.
        </p>
      </div>
    );
  }
  const scenes = groupScenes(events);
  return (
    <div className="timeline" data-testid="timeline">
      {scenes.map((scene, i) => (
        <article className="scene" key={i} data-testid={`scene-${slug(scene.title)}`}>
          <h2 className="scene-title"><span className="node" />{scene.title}</h2>
          <div className="scene-body">
            {scene.items.map((e) => <EventView key={e._i} e={e} />)}
          </div>
        </article>
      ))}
      {run?.status === "running" && <div className="working" data-testid="run-working"><span className="dot" />agent working…</div>}
      <div ref={end} />
    </div>
  );
}
