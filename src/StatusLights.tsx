// The keypad's three profile status lights, top first, in their real colours.
export const LED_COLOURS = ["#ffb02e", "#5cff3b", "#2ec5ff"];
export const LED_UNLIT = "#2a3038";

export function StatusLights({ leds, size = 8 }: { leds: readonly boolean[]; size?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: size / 3, flexShrink: 0 }}>
      {LED_COLOURS.map((colour, i) => (
        <div
          key={colour}
          style={{ width: size, height: size, borderRadius: "50%", background: leds[i] ? colour : LED_UNLIT }}
        />
      ))}
    </div>
  );
}
