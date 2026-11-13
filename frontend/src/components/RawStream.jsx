import React from "react";

export default function RawStream({ events }) {
  return (
    <div className="raw" data-testid="raw-stream">
      {events.length === 0 && <p className="dim">No events yet. Same events as `main.py --json`, one JSON object per line, with the time each one happened.</p>}
      {events.map((e, i) => (
        <pre key={i} className="raw-line"><span className="ln">{String(i + 1).padStart(3, " ")}</span>{JSON.stringify(e)}</pre>
      ))}
    </div>
  );
}
