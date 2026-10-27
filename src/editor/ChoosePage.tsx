import { DialogButton, Focusable, TextField } from "@decky/ui";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { errorText, ProfileState, setBindingText, State } from "../api";
import { Card } from "./Card";
import { controlTitle } from "./Keypad";
import { BUTTON, ERROR, PICK } from "./layout";
import { isMoreKey, isSteamPick, QuickPick, QUICK_PICKS } from "./quickPicks";
import { SubPage } from "./SubPage";

// No flow-children on a wrapped row: the D-pad moves through it by position.
function Picks({ picks, onPick, children }: { picks: QuickPick[]; onPick(text: string): void; children?: ReactNode }) {
  return (
    <Focusable style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {picks.map((p) => (
        <DialogButton key={p.text} style={PICK} onClick={() => onPick(p.text)}>
          {p.label}
        </DialogButton>
      ))}
      {children}
    </Focusable>
  );
}

export function ChoosePage(props: {
  control: string;
  state: State;
  profile: ProfileState;
  onChanged(s: State): void;
  onDone(): void;
}) {
  const { control, state, profile, onChanged, onDone } = props;
  const [text, setText] = useState("");
  const [moreKeys, setMoreKeys] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText("");
    setError(null);
  }, [control, profile.id]);

  function apply(value: string) {
    setBindingText(profile.id, control, value)
      .then((r) => {
        onChanged(r.state);
        if (r.ok) onDone();
        else setError(r.error);
      })
      .catch((e) => setError(errorText(e)));
  }

  const keyPicks = QUICK_PICKS.filter((p) => !isSteamPick(p) && (moreKeys || !isMoreKey(p)));
  const steamPicks = QUICK_PICKS.filter(isSteamPick);
  const title = control.endsWith(".b")
    ? `Deep press for ${controlTitle(control.slice(0, -2))}`
    : `Binding for ${controlTitle(control)}`;

  return (
    <SubPage title={title} onBack={onDone}>
      <Focusable flow-children="row" style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <Focusable flow-children="column" style={{ flex: 3, display: "flex", flexDirection: "column", gap: 10 }}>
          <Card title="Keys">
            <Picks picks={keyPicks} onPick={apply}>
              <DialogButton style={PICK} onClick={() => setMoreKeys(!moreKeys)}>
                {moreKeys ? "Fewer keys" : "More keys…"}
              </DialogButton>
            </Picks>
          </Card>
          <Card title="Steam">
            {state.steam_mode === "disabled" ? (
              <div style={{ fontSize: 13, opacity: 0.7 }}>Steam menu shortcuts don't work while streaming on this setup.</div>
            ) : (
              <Picks picks={steamPicks} onPick={apply} />
            )}
          </Card>
        </Focusable>
        <div style={{ flex: 2 }}>
          <Card title="Type a binding">
            <Focusable flow-children="column" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <TextField value={text} onChange={(e) => setText(e.target.value)} />
              <div style={{ fontSize: 12, opacity: 0.7 }}>Examples: Ctrl+C · hold:W+A · A, B, C · steam:menu · disable</div>
              <DialogButton style={{ ...BUTTON, alignSelf: "flex-start" }} disabled={text.trim() === ""} onClick={() => apply(text)}>
                Apply
              </DialogButton>
            </Focusable>
          </Card>
        </div>
      </Focusable>
      {error && <div style={{ color: ERROR }}>{error}</div>}
    </SubPage>
  );
}
