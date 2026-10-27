import { Tabs } from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import { useEffect, useState } from "react";

import { EV_STATE, activeProfile, errorText, getState, profileById, setDpadMode, State } from "../api";
import { LightingControls } from "../LightingControls";
import { syncLighting } from "../lighting";
import { ActuationPage } from "./ActuationPage";
import { Card } from "./Card";
import { CustomizePage } from "./CustomizePage";
import { PAGE_HEIGHT } from "./layout";
import { ProfilesPage } from "./ProfilesPage";

type Page = "customize" | "actuation" | "lighting" | "profiles";

export function Editor() {
  const [state, setState] = useState<State | null>(null);
  const [selected, setSelected] = useState<string>("k01");
  const [error, setError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("customize");

  useEffect(() => {
    getState().then((s) => {
      setState(s);
      syncLighting(s);
      setViewing((v) => v ?? s.active_profile);
    });
    const listener = addEventListener<[State]>(EV_STATE, (s) => {
      setState(s);
      syncLighting(s);
    });
    return () => {
      removeEventListener(EV_STATE, listener);
    };
  }, []);

  // Falls back to the active profile when the viewed one was deleted.
  const viewedProfile = (s: State) => (viewing !== null && profileById(s, viewing)) || activeProfile(s);

  function toggleDpad(eight: boolean) {
    if (state === null) return;
    setDpadMode(viewedProfile(state).id, eight ? "8way" : "4way")
      .then((s) => {
        setState(s);
        setError(null);
        if (!eight && /^dpad_.*_/.test(selected)) setSelected("dpad_up");
      })
      .catch((e) => setError(errorText(e)));
  }

  // The editor's error belongs to the control and profile it came from.
  function select(control: string) {
    setSelected(control);
    setError(null);
  }

  // A sub-page open on Customize closes with the profile change, which flushes its pending write.
  function switchView(id: string) {
    setViewing(id);
    setError(null);
    const p = state && profileById(state, id);
    if (p && p.dpad_mode === "4way" && /^dpad_.*_/.test(selected)) setSelected("dpad_up");
  }

  if (state === null) return <div style={{ marginTop: 40, padding: 16 }}>Loading…</div>;

  const profile = viewedProfile(state);

  // The route sits under Steam's header and above its footer, 40 px each (60 screen px on the Deck).
  return (
    <div style={{ height: "100%", padding: "40px 0", boxSizing: "border-box" }}>
      <Tabs
        activeTab={page}
        onShowTab={(id: string) => setPage(id as Page)}
        tabs={[
          {
            id: "customize",
            title: "Customize",
            content: (
              <CustomizePage
                state={state}
                profile={profile}
                selected={selected}
                error={error}
                onSelect={select}
                onView={switchView}
                onDpad={toggleDpad}
                onChanged={setState}
              />
            ),
          },
          {
            id: "actuation",
            title: "Actuation",
            content: <ActuationPage state={state} profile={profile} onView={switchView} onChanged={setState} />,
          },
          {
            id: "lighting",
            title: "Lighting",
            // As wide as the Quick Access panel's rows plus margins, so the swatches stay together.
            content: (
              <div style={{ height: PAGE_HEIGHT, maxWidth: 560 }}>
                <Card title="Lighting">
                  <LightingControls effects={state.effects} collapsible={false} />
                </Card>
              </div>
            ),
          },
          {
            id: "profiles",
            title: "Profiles",
            content: (
              <ProfilesPage
                state={state}
                viewing={profile.id}
                onEdit={(id) => {
                  switchView(id);
                  setPage("customize");
                }}
                onView={switchView}
                onChanged={setState}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
