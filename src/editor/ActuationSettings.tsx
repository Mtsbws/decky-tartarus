import { DialogButton, Focusable, SliderField, ToggleField } from "@decky/ui";
import { useEffect, useRef, useState } from "react";

import { ProfileState, setActuation, setAllActuation, setSecondary, State } from "../api";
import { errorText } from "../Panel";
import { BindingPicker } from "./BindingPicker";

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
  const { default_mm, min_mm, max_mm, min_gap_mm } = state.actuation;
  const [draft, setDraft] = useState<number | null>(null);
  const [draftB, setDraftB] = useState<number | null>(null);
  const [all, setAll] = useState(default_mm);
  const [error, setError] = useState<string | null>(null);
  const debounce = useDebounce();
  const debounceB = useDebounce();

  useEffect(() => {
    setDraft(null);
    setDraftB(null);
    setError(null);
    return () => {
      debounce.flush();
      debounceB.flush();
    };
  }, [control, profile.id]);

  const value = draft ?? profile.actuation[control] ?? default_mm;
  const secondary = profile.secondary[control];
  const valueB = draftB ?? secondary?.actuation ?? max_mm;
  const minB = Math.min(tenth(value + min_gap_mm), max_mm);

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

  // Off removes B with its binding; on starts it at the deepest point, unbound.
  function toggleSecondary(on: boolean) {
    setSecondary(profile.id, control, on ? max_mm : null)
      .then((s) => {
        setError(null);
        onChanged(s);
      })
      .catch((e) => setError(errorText(e)));
  }

  function changeB(v: number) {
    const mm = tenth(v);
    const profileId = profile.id;
    setDraftB(mm);
    debounceB.schedule(() => {
      setSecondary(profileId, control, mm)
        .then((s) => {
          setError(null);
          onChanged(s);
          if (!debounceB.isPending()) setDraftB(null);
        })
        .catch((e) => {
          setError(errorText(e));
          setDraftB(null);
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
      <ToggleField label="Secondary function" checked={secondary !== undefined} onChange={toggleSecondary} />
      {secondary && (
        <>
          <h3 style={{ margin: "8px 0" }}>Deep press: {secondary.label}</h3>
          <BindingPicker control={control + ".b"} state={state} profile={profile} onChanged={onChanged} />
          <SliderField label={`Deep press actuation: ${mmText(valueB)}`} value={valueB} min={minB} max={max_mm} step={0.1} onChange={changeB} />
        </>
      )}
      {state.actuation.status !== "on" && <div style={{ opacity: 0.7 }}>Applies only with Adjustable actuation on.</div>}
      {error && <div style={{ color: "#e05050" }}>{error}</div>}
    </div>
  );
}
