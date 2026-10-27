import { DialogButton, Focusable } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useRef, useState } from "react";

import { BindingDict, EV_RECORD, errorText, ProfileState, recordCancel, recordStart, setBinding, State } from "../api";
import { BUTTON } from "./layout";

type RecordStatus = "idle" | "recording" | "nothing";

// A key and its deep press each have a Record button. The result of a recording
// goes to the button that started it last; another one still waiting gives up.
let recordOwner = 0;
let nextPickerId = 1;

export function RecordButton(props: {
  control: string;
  profile: ProfileState;
  onChanged(s: State): void;
  onError(msg: string | null): void;
}) {
  const { control, profile, onChanged, onError } = props;
  const [record, setRecord] = useState<RecordStatus>("idle");
  const pickerId = useRef(nextPickerId++).current;

  // A new control or profile starts clean; a recording for the previous one is cancelled.
  useEffect(() => {
    setRecord("idle");
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
          onError(null);
          onChanged(s);
        })
        .catch((e) => onError(errorText(e)));
    });
    return () => {
      removeEventListener(EV_RECORD, listener);
    };
  }, [record, control, profile.id]);

  function start() {
    onError(null);
    recordOwner = pickerId;
    setRecord("recording");
    recordStart().catch((e) => {
      setRecord("idle");
      onError(errorText(e));
    });
  }

  function cancel() {
    // The backend sends nothing on cancel, so reset here.
    setRecord("idle");
    recordCancel().catch(() => undefined);
  }

  return (
    <Focusable flow-children="row" style={{ display: "flex", alignItems: "center", gap: 10 }}>
      {record === "recording" && <div style={{ fontSize: 13 }}>Press a key or combo…</div>}
      {record === "nothing" && <div style={{ fontSize: 13, opacity: 0.7 }}>Nothing recorded</div>}
      {record === "recording" ? (
        <DialogButton style={BUTTON} onClick={cancel}>
          Cancel
        </DialogButton>
      ) : (
        <DialogButton style={BUTTON} onClick={start}>
          Record
        </DialogButton>
      )}
    </Focusable>
  );
}
