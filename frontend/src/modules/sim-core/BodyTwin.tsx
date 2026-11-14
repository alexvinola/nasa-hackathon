"use client";

import { GUIDES, STATUS_COLOR, type IndicatorStatus, type ZoneStatus } from "./indicators";

const W = 304;
const H = 320;
const COLUMN = 88; // width of the label columns on each side of the body
const DX = 2; // the body is drawn 300 wide and centred between the columns

// Where each measurement is taken on the body ([x, y] in the body's own coordinates) and where its label sits (column and top).
const SITES: Record<string, { at: [number, number]; side: "left" | "right"; top: number }> = {
  "selfReport.sleepHoursLast24h": { at: [141, 27], side: "left", top: 8 },
  "selfReport.bloodPressure": { at: [112, 106], side: "left", top: 88 },
  "selfReport.glucoseMgDl": { at: [100, 198], side: "left", top: 180 },
  "selfReport.mood": { at: [159, 27], side: "right", top: 8 },
  "selfReport.bodyTempC": { at: [150, 49], side: "right", top: 62 },
  "biometrics.heartRateBpm": { at: [197, 176], side: "right", top: 158 },
};
const LABEL_H = 36;

const TINT = "rgb(94 242 236 / 0.16)";
const ZONE_FILL: Record<ZoneStatus, string> = {
  UNKNOWN: "rgb(94 242 236 / 0.18)",
  GREEN: "rgb(94 242 236 / 0.4)",
  AMBER: "#fbbf24",
  RED: "#ef4444",
};

/** One body system of the contract: its zone lights up with the engine's status for it. */
function Zone({ system, status, children }: { system: string; status: ZoneStatus; children: React.ReactNode }) {
  return (
    <g data-system={system} data-status={status} fill={ZONE_FILL[status]} stroke={ZONE_FILL[status]} className={status === "RED" ? "animate-pulse" : undefined}>
      <title>{`${system} · ${status}`}</title>
      {children}
    </g>
  );
}

/**
 * The body twin: a front view with the six body systems of the contract as zones, and one marker per health
 * indicator at the place where its measurement is taken. A click on a marker opens that indicator's guide.
 */
export function BodyTwin({
  readings,
  statuses,
  zones,
  selected,
  onSelect,
}: {
  /** Per signal: the reading with its unit, null when there is none. */
  readings: Record<string, string | null>;
  statuses: Record<string, IndicatorStatus>;
  zones: Record<string, ZoneStatus>;
  selected: string | null;
  onSelect: (signal: string) => void;
}) {
  const limbs = zones.MUSCULOSKELETAL;
  return (
    <div data-testid="body-twin" className="relative" style={{ width: W, height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="absolute inset-0" aria-hidden="true">
        <g transform={`translate(${DX} 0)`}>
          {/* Limbs are the musculoskeletal zone; drawn as capsules so the joints read where they overlap. */}
          <g data-system="MUSCULOSKELETAL" data-status={limbs} stroke={limbs === "AMBER" || limbs === "RED" ? ZONE_FILL[limbs] : TINT} strokeLinecap="round" fill="none" className={limbs === "RED" ? "animate-pulse" : undefined}>
            <title>{`MUSCULOSKELETAL · ${limbs}`}</title>
            <path d="M116 80 108 132M108 132 102 182M184 80 192 132M192 132 198 182" strokeWidth="13" />
            <path d="M101 190 100 198M199 190 200 198" strokeWidth="11" />
            <path d="M136 186 134 244M164 186 166 244" strokeWidth="17" />
            <path d="M134 244 133 298M166 244 167 298" strokeWidth="14" />
            <path d="M133 305 126 309M167 305 174 309" strokeWidth="10" />
          </g>
          <g fill={TINT} stroke="rgb(94 242 236 / 0.45)" strokeWidth="1">
            <ellipse cx="150" cy="36" rx="17" ry="21" />
            <path d="M144 55h12v12h-12z" stroke="none" />
            <path d="M120 74Q150 66 180 74L175 150 178 178Q150 188 122 178L125 150Z" />
          </g>

          <g strokeWidth="1">
            <Zone system="NERVOUS" status={zones.NERVOUS}>
              <ellipse cx="150" cy="29" rx="11" ry="9" />
              <path d="M150 38V60" fill="none" strokeWidth="2" />
            </Zone>
            <Zone system="RESPIRATORY" status={zones.RESPIRATORY}>
              <ellipse cx="138" cy="106" rx="9" ry="17" />
              <ellipse cx="162" cy="106" rx="9" ry="17" />
            </Zone>
            <Zone system="CARDIOVASCULAR" status={zones.CARDIOVASCULAR}>
              <path d="M154 104c-3-4-9-1-7 4 1 3 4 5 7 8 3-3 6-5 7-8 2-5-4-8-7-4Z" stroke="var(--color-space)" />
            </Zone>
            <Zone system="METABOLIC" status={zones.METABOLIC}>
              <ellipse cx="150" cy="144" rx="15" ry="9" />
            </Zone>
            <Zone system="IMMUNE" status={zones.IMMUNE}>
              {[[143, 63], [157, 63], [126, 88], [174, 88], [138, 176], [162, 176]].map(([cx, cy]) => (
                <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.5" />
              ))}
            </Zone>
          </g>
        </g>

        {/* Leader lines from each label to the place on the body where the measurement is taken. */}
        {GUIDES.map(({ signal }) => {
          const { at, side, top } = SITES[signal];
          const color = STATUS_COLOR[statuses[signal]];
          const on = selected === signal;
          return (
            <g key={signal} stroke={color} opacity={on || !selected ? 1 : 0.45}>
              <path d={`M${side === "left" ? COLUMN : W - COLUMN} ${top + LABEL_H / 2}L${at[0] + DX} ${at[1]}`} fill="none" strokeWidth={on ? 1.5 : 1} strokeDasharray={on ? undefined : "2 3"} />
              <circle cx={at[0] + DX} cy={at[1]} r={on ? 5 : 3.5} fill={color} stroke="var(--color-space)" />
            </g>
          );
        })}
      </svg>

      {GUIDES.map(({ signal, label }) => {
        const { side, top } = SITES[signal];
        const status = statuses[signal];
        const on = selected === signal;
        return (
          <button
            key={signal}
            type="button"
            data-indicator={signal}
            data-status={status}
            aria-pressed={on}
            title={`${label}: how to measure it`}
            onClick={() => onSelect(signal)}
            className={`absolute flex flex-col justify-center border bg-space/80 px-1.5 text-left leading-tight outline-none transition-colors hover:bg-pulse/15 focus-visible:ring-2 focus-visible:ring-pulse ${side === "left" ? "left-0 border-r-2" : "right-0 border-l-2"} ${on ? "bg-pulse/15" : ""}`}
            style={{ top, width: COLUMN, height: LABEL_H, borderColor: STATUS_COLOR[status] }}
          >
            <span className="text-[8px] uppercase tracking-[0.08em] text-shell/70">{label}</span>
            <span className="truncate text-[11px] tracking-normal" style={{ color: STATUS_COLOR[status] }}>{readings[signal] ?? "— —"}</span>
          </button>
        );
      })}
    </div>
  );
}
