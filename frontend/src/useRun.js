import { useEffect, useState } from "react";
import { api } from "./api.js";
import { ACTIVE } from "./format.js";

// Loads one run and, while it is live, receives its events over a server-sent event stream.
export function useRun(id) {
  const [run, setRun] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let stop;
    let gone = false;
    setRun(null);
    setEvents([]);
    setError(null);

    const refresh = () =>
      api.run(id).then((snap) => {
        if (gone) return;
        setRun(snap);
        setEvents(snap.events);
      }).catch((e) => setError(e.message));

    api.run(id).then((snap) => {
      if (gone) return;
      setRun(snap);
      setEvents(snap.events);
      if (!ACTIVE.includes(snap.status)) return;
      stop = api.stream(id, snap.events.length, {
        onEvent: (event) => setEvents((prev) => [...prev, event]),
        onState: (state) => {
          setRun((r) => ({ ...r, ...state }));
          if (!ACTIVE.includes(state.status)) refresh();
        },
        onLost: refresh,
      });
    }).catch((e) => setError(e.message === "run not found" ? "This purchase does not exist." : e.message));

    return () => {
      gone = true;
      stop?.();
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
