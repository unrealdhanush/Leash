import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

// Polls the backend run and accumulates its event stream.
export function useRun() {
  const [run, setRun] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const count = useRef(0);
  const runId = useRef(null);

  const absorb = useCallback((snap, reset) => {
    if (!snap) return;
    if (reset) {
      count.current = 0;
      runId.current = snap.id;
      setEvents([]);
    }
    if (snap.events.length) {
      count.current = snap.after + snap.events.length;
      setEvents((prev) => (reset ? snap.events : [...prev, ...snap.events]));
    }
    setRun(snap);
  }, []);

  useEffect(() => {
    api.latest().then((snap) => absorb(snap, true)).catch((e) => setError(e.message));
  }, [absorb]);

  useEffect(() => {
    const active = run && (run.status === "running" || run.status === "waiting_approval");
    if (!active) return;
    const t = setInterval(async () => {
      try {
        const snap = await api.poll(runId.current, count.current);
        if (snap.id === runId.current) absorb(snap, false);
      } catch (e) {
        setError(e.message);
      }
    }, 700);
    return () => clearInterval(t);
  }, [run?.status, absorb]);

  const start = async (auto) => {
    setError(null);
    try {
      absorb(await api.start(auto), true);
    } catch (e) {
      setError(e.message);
    }
  };

  const decide = async (approved) => {
    try {
      await api.decide(runId.current, approved);
      setRun((r) => ({ ...r, pending: null, status: "running" }));
    } catch (e) {
      setError(e.message);
    }
  };

  return { run, events, error, start, decide };
}
