import { useEffect, useState } from "react";
import { api } from "./api.js";
import { ACTIVE } from "./format.js";

// Loads one run and, while it is live, receives its events over a server-sent event stream.
export function useRun(id) {
  const [run, setRun] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let source;
    let gone = false;
    setRun(null);
    setEvents([]);
    setError(null);

    const refresh = () =>
      api.run(id).then((snap) => {
        if (gone) return;
        setRun(snap);
        setEvents(snap.events);
      });

    api.run(id).then((snap) => {
      if (gone) return;
      setRun(snap);
      setEvents(snap.events);
      if (!ACTIVE.includes(snap.status)) return;

      let count = snap.events.length;
      source = new EventSource(api.streamUrl(id, count));
      source.addEventListener("leash", (m) => {
        const n = Number(m.lastEventId);
        if (n !== count + 1) return;
        count = n;
        const event = JSON.parse(m.data);
        setEvents((prev) => [...prev, event]);
      });
      source.addEventListener("state", (m) => {
        const state = JSON.parse(m.data);
        setRun((r) => ({ ...r, ...state }));
        if (!ACTIVE.includes(state.status)) {
          source.close();
          refresh();
        }
      });
      source.onerror = () => {
        if (source.readyState === EventSource.CLOSED) refresh().catch((e) => setError(e.message));
      };
    }).catch((e) => setError(e.message === "run not found" ? "This purchase does not exist." : e.message));

    return () => {
      gone = true;
      source?.close();
    };
  }, [id]);

  const decide = async (approved, digest, note) => {
    try {
      await api.decide(id, approved, digest, note);
      setRun((r) => ({ ...r, pending: null }));
    } catch (e) {
      setError(e.message);
    }
  };

  return { run, events, error, decide };
}
