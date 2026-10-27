import { DialogButton, Focusable, SliderField } from "@decky/ui";
import { useEffect, useRef, useState } from "react";

import { ProfileState, setActuation, setAllActuation, State } from "../api";
import { errorText } from "../Panel";

const DEBOUNCE_MS = 300;

// Slider steps of 0.1 arrive as floats like 2.6000000000000005.
const tenth = (v: number) => Math.round(v * 10) / 10;
const mmText = (v: number) => `${v.toFixed(1)} mm`;

// One pending write at a time; a new value replaces it. flush() sends it now,
// so moving to another key or profile doesn't drop the last change.
function useDebounce() {
  const pending = useRef<{ timer: number; run(): void } | null>(null);
  const flush = () => {
    const p = pending.current;
    if (p === null) return;
    window.clearTimeout(p.timer);
    pending.current = null;
    p.run();
  };
  const schedule = (run: () => void) => {
    if (pending.current !== null) window.clearTimeout(pending.current.timer);
    const timer = window.setTimeout(() => {
      pending.current = null;
      run();
    }, DEBOUNCE_MS);
    pending.current = { timer, run };
  };
  return { schedule, flush, isPending: () => pending.current !== null };
}

export function ActuationSettings(props: { control: string; state: State; profile: ProfileState; onChanged(s: State): void }) {
  const { control, state, profile, onChanged } = props;
  const { default_mm, min_mm, max_mm } = state.actuation;
  const [draft, setDraft] = useState<number | null>(null);
  const [all, setAll] = useState(default_mm);
  const [error, setError] = useState<string | null>(null);
  const debounce = useDebounce();

  useEffect(() => {
    setDraft(null);
    setError(null);
    return debounce.flush;
  }, [control, profile.id]);

  const value = draft ?? profile.actuation[control] ?? default_mm;

  function change(v: number) {
    const mm = tenth(v);
    const profileId = profile.id;
    setDraft(mm);
    debounce.schedule(() => {
      setActuation(profileId, control, mm)
        .then((s) => {
          setError(null);
          onChanged(s);
          if (!debounce.isPending()) setDraft(null);
        })
        .catch((e) => {
          setError(errorText(e));
          setDraft(null);
        });
    });
  }

  function applyAll() {
    setAllActuation(profile.id, all)
      .then((s) => {
        setError(null);
        onChanged(s);
      })
      .catch((e) => setError(errorText(e)));
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 12 }}>
      <SliderField label={`Actuation: ${mmText(value)}`} value={value} min={min_mm} max={max_mm} step={0.1} onChange={change} />
      <Focusable style={{ display: "flex", alignItems: "center", gap: 8 }} flow-children="row">
        <div style={{ flex: 1, minWidth: 0 }}>
          <SliderField label={`All keys: ${mmText(all)}`} value={all} min={min_mm} max={max_mm} step={0.1} onChange={(v) => setAll(tenth(v))} />
        </div>
        <DialogButton style={{ width: "auto", minWidth: 0, padding: "6px 10px", fontSize: 13 }} onClick={applyAll}>
          Apply to all keys
        </DialogButton>
      </Focusable>
      {state.actuation.status !== "on" && <div style={{ opacity: 0.7 }}>Applies only with Adjustable actuation on.</div>}
      {error && <div style={{ color: "#e05050" }}>{error}</div>}
    </div>
  );
}
