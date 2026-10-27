import { DialogButton, Focusable, TextField } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { CSSProperties, useEffect, useRef, useState } from "react";

import { BindingDict, EV_RECORD, errorText, recordCancel, ProfileState, recordStart, setBinding, setBindingText, State } from "../api";
import { isMoreKey, isSteamPick, QUICK_PICKS } from "./quickPicks";

type RecordStatus = "idle" | "recording" | "nothing";

// A key and its deep press each have a picker. The result of a recording goes
// to the picker that started it last; another one still waiting gives up.
let recordOwner = 0;
let nextPickerId = 1;

const pickStyle: CSSProperties = { minWidth: 0, width: "auto", padding: "6px 10px", margin: 0, fontSize: 13 };

export function BindingPicker(props: { control: string; state: State; profile: ProfileState; onChanged(s: State): void }) {
  const { control, state, profile, onChanged } = props;
  const [record, setRecord] = useState<RecordStatus>("idle");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [moreKeys, setMoreKeys] = useState(false);
  const pickerId = useRef(nextPickerId++).current;

  // A new control or profile starts clean; a recording for the previous one is cancelled.
  useEffect(() => {
    setRecord("idle");
    setText("");
    setError(null);
    return () => {
      recordCancel().catch(() => undefined);
    };
  }, [control, profile.id]);

  useEffect(() => {
    if (record !== "recording") return;
    const listener = addEventListener<[BindingDict | null]>(EV_RECORD, (binding) => {
      if (recordOwner !== pickerId) {
        setRecord("idle");
        return;
      }
      if (binding === null) {
        setRecord("nothing");
        return;
      }
      setRecord("idle");
      setBinding(profile.id, control, binding)
        .then((s) => {
          setError(null);
          onChanged(s);
        })
        .catch((e) => setError(errorText(e)));
    });
    return () => {
      removeEventListener(EV_RECORD, listener);
    };
  }, [record, control, profile.id]);

  function applyText(value: string) {
    setBindingText(profile.id, control, value)
      .then((r) => {
        setError(r.ok ? null : r.error);
        onChanged(r.state);
      })
      .catch((e) => setError(errorText(e)));
  }

  function startRecording() {
    setError(null);
    recordOwner = pickerId;
    setRecord("recording");
    recordStart().catch((e) => {
      setRecord("idle");
      setError(errorText(e));
    });
  }

  function cancelRecording() {
    // The backend sends nothing on cancel, so reset here.
    setRecord("idle");
    recordCancel().catch(() => undefined);
  }

  const steamOff = state.steam_mode === "disabled";
  const picks = QUICK_PICKS.filter((p) => !(steamOff && isSteamPick(p)) && (moreKeys || !isMoreKey(p)));
  const factory = profile.bindings[control]?.factory;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Focusable style={{ display: "flex", flexWrap: "wrap", gap: 6 }} flow-children="row">
        {picks.map((p) => (
          <DialogButton key={p.text} style={pickStyle} onClick={() => applyText(p.text)}>
            {p.label}
          </DialogButton>
        ))}
        <DialogButton style={pickStyle} onClick={() => setMoreKeys(!moreKeys)}>
          {moreKeys ? "Fewer keys" : "More keys…"}
        </DialogButton>
        {factory && (
          <DialogButton style={pickStyle} onClick={() => applyText(factory)}>
            Factory default ({factory})
          </DialogButton>
        )}
      </Focusable>
      {steamOff && <div style={{ opacity: 0.7 }}>Steam menu shortcuts don't work while streaming on this setup.</div>}

      <Focusable style={{ display: "flex", gap: 8, alignItems: "center" }} flow-children="row">
        {record === "recording" ? (
          <>
            <div style={{ flex: 1 }}>Press a key or combo…</div>
            <DialogButton style={pickStyle} onClick={cancelRecording}>
              Cancel
            </DialogButton>
          </>
        ) : (
          <>
            <DialogButton style={pickStyle} onClick={startRecording}>
              Record
            </DialogButton>
            {record === "nothing" && <div style={{ opacity: 0.7 }}>Nothing recorded</div>}
          </>
        )}
      </Focusable>

      <div>
        <TextField label="Type a binding" value={text} onChange={(e) => setText(e.target.value)} />
        <div style={{ fontSize: 12, opacity: 0.7, marginTop: 4 }}>
          Examples: Ctrl+C · hold:W+A · A, B, C · steam:menu · disable
        </div>
        <DialogButton style={{ ...pickStyle, marginTop: 8 }} onClick={() => applyText(text)}>
          Apply
        </DialogButton>
        {error && <div style={{ color: "#e05050", marginTop: 6 }}>{error}</div>}
      </div>
    </div>
  );
}
