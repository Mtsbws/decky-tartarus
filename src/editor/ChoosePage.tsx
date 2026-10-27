import { DialogButton, Focusable, TextField } from "@decky/ui";
import { CSSProperties, useEffect, useState } from "react";

import { BindingDict, errorText, ProfileState, setBindingText, State } from "../api";
import { Card } from "./Card";
import { CATEGORIES, Category, MODIFIERS } from "./categories";
import { controlTitle } from "./Keypad";
import { baseControl, bindingOf, HYPERSHIFT_KEYS } from "./layers";
import { BUTTON, ERROR, PICK } from "./layout";
import { SubPage } from "./SubPage";

const GREEN = "#3d8b2f";
const on = (style: CSSProperties, active: boolean): CSSProperties =>
  active ? { ...style, background: GREEN, color: "#fff" } : style;
const CATEGORY: CSSProperties = { ...PICK, height: 34, minHeight: 0, padding: "0 14px", fontSize: 14, textAlign: "left" };

type Choice = { category: string; key: string | null; mods: string[] };

// Opens on the current binding when it's one key, maybe with modifiers, a Steam action or Disable.
function choiceFor(b: BindingDict | undefined): Choice {
  if (b?.type === "hypershift") return { category: "hypershift", key: null, mods: [] };
  if (b?.type === "disable") return { category: "disable", key: null, mods: [] };
  if (b?.type === "steam") return { category: "steam", key: `steam:${b.action}`, mods: [] };
  const keys = b?.keys ?? [];
  const key = keys[keys.length - 1];
  const mods = keys.slice(0, -1);
  const category = key && b?.type !== "combo" && mods.every((m) => MODIFIERS.includes(m)) && CATEGORIES.find((c) => c.picks.some((p) => p.text === key));
  if (!category) return { category: "letters", key: null, mods: [] };
  return { category: category.id, key, mods };
}

export function ChoosePage(props: {
  control: string;
  state: State;
  profile: ProfileState;
  onChanged(s: State): void;
  onDone(): void;
}) {
  const { control, state, profile, onChanged, onDone } = props;
  const current = bindingOf(profile, control);
  const key = baseControl(control);
  const secondaryFn = control.endsWith(".b");
  const onHypershift = control.split(".").includes("h");
  const [choice, setChoice] = useState<Choice>(() => choiceFor(current));
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setChoice(choiceFor(current));
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

  const category = CATEGORIES.find((c) => c.id === choice.category) as Category;
  const toggleMod = (m: string) =>
    setChoice({ ...choice, mods: choice.mods.includes(m) ? choice.mods.filter((x) => x !== m) : [...choice.mods, m] });
  // Ctrl+Shift+C, in Synapse's modifier order; a modifier picked as the key isn't added twice.
  const mods = category.modifiers ? MODIFIERS.filter((m) => choice.mods.includes(m) && m !== choice.key) : [];
  const result = choice.key === null ? null : [...mods, choice.key].join("+");
  const resultLabel = choice.key === null ? "pick a key" : [...mods, category.picks.find((p) => p.text === choice.key)?.label].join(" + ");
  const title = secondaryFn
    ? `Secondary function for ${controlTitle(key)}${onHypershift ? " (Hypershift)" : ""}`
    : `${onHypershift ? "Hypershift binding" : "Binding"} for ${controlTitle(key)}`;
  // Only a plain key on the standard layer can become the Hypershift key.
  const categories = CATEGORIES.filter((c) => c.id !== "hypershift" || HYPERSHIFT_KEYS.includes(control));
  const otherKey = profile.hypershift.key !== null && profile.hypershift.key !== control ? profile.hypershift.key : null;

  let body;
  if (category.id === "type") {
    body = (
      <Focusable flow-children="column" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ fontSize: 13, opacity: 0.7 }}>For macros, held combos and anything not in the lists.</div>
        <TextField value={text} onChange={(e) => setText(e.target.value)} />
        <div style={{ fontSize: 12, opacity: 0.7 }}>Examples: Ctrl+C · hold:W+A · A, B, C · steam:menu · disable</div>
        <DialogButton style={{ ...BUTTON, alignSelf: "flex-start" }} disabled={text.trim() === ""} onClick={() => apply(text)}>
          Apply
        </DialogButton>
      </Focusable>
    );
  } else if (category.id === "disable") {
    body = (
      <Focusable flow-children="column" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div>
          {controlTitle(key)} does nothing {onHypershift && !secondaryFn ? "while Hypershift is held." : "when pressed."}
        </div>
        <DialogButton style={{ ...BUTTON, alignSelf: "flex-start" }} onClick={() => apply("disable")}>
          Disable
        </DialogButton>
      </Focusable>
    );
  } else if (category.id === "hypershift") {
    const factory = otherKey === null ? undefined : profile.bindings[otherKey]?.factory;
    body = (
      <Focusable flow-children="column" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div>Hold {controlTitle(key)} to switch the other controls to their Hypershift bindings.</div>
        {otherKey !== null && (
          <div style={{ fontSize: 13, opacity: 0.7 }}>
            {controlTitle(otherKey)} goes back to its factory default{factory ? ` (${factory})` : ""}.
          </div>
        )}
        <DialogButton style={{ ...BUTTON, alignSelf: "flex-start" }} onClick={() => apply("hypershift")}>
          Apply
        </DialogButton>
      </Focusable>
    );
  } else if (category.id === "steam" && state.steam_mode === "disabled") {
    body = <div style={{ fontSize: 13, opacity: 0.7 }}>Steam menu shortcuts don't work while streaming on this setup.</div>;
  } else {
    body = (
      <Focusable flow-children="column" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* No flow-children on a wrapped row: the D-pad moves through it by position. */}
        <Focusable style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {category.picks.map((p) => (
            <DialogButton
              key={p.text}
              style={on({ ...PICK, minWidth: 44, fontSize: 15 }, choice.key === p.text)}
              onClick={() => setChoice({ ...choice, key: p.text })}
            >
              {p.label}
            </DialogButton>
          ))}
        </Focusable>
        {category.modifiers && (
          <Focusable flow-children="row" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ fontSize: 13, opacity: 0.7, marginRight: 4 }}>Include modifiers</div>
            {MODIFIERS.map((m) => (
              <DialogButton key={m} style={on(PICK, choice.mods.includes(m))} onClick={() => toggleMod(m)}>
                {choice.mods.includes(m) ? `✓ ${m}` : m}
              </DialogButton>
            ))}
          </Focusable>
        )}
        <Focusable flow-children="row" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ flex: 1 }}>
            Result: <b>{resultLabel}</b>
          </div>
          <DialogButton style={BUTTON} disabled={result === null} onClick={() => result && apply(result)}>
            Apply
          </DialogButton>
        </Focusable>
      </Focusable>
    );
  }

  return (
    <SubPage title={title} onBack={onDone}>
      <Focusable flow-children="row" style={{ display: "flex", gap: 12, alignItems: "flex-start", minHeight: 0 }}>
        <Focusable flow-children="column" style={{ width: 190, flexShrink: 0, display: "flex", flexDirection: "column", gap: 4 }}>
          {categories.map((c) => (
            <DialogButton
              key={c.id}
              style={on(CATEGORY, c.id === category.id)}
              onClick={() => setChoice({ category: c.id, key: null, mods: choice.mods })}
            >
              {c.label}
            </DialogButton>
          ))}
        </Focusable>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Card title={category.label}>
            {body}
            {error && <div style={{ color: ERROR, marginTop: 8 }}>{error}</div>}
          </Card>
        </div>
      </Focusable>
    </SubPage>
  );
}
