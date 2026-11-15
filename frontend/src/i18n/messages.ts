import app from "./messages/app";
import debug from "./messages/debug";
import guides from "./messages/guides";
import habits from "./messages/habits";
import hud from "./messages/hud";
import relax from "./messages/relax";
import selfReport from "./messages/selfReport";
import vision from "./messages/vision";
import voice from "./messages/voice";

/** Every message of the front, in both languages. Each slice owns the keys of one part of the UI. */
const slices = [app, debug, guides, habits, hud, relax, selfReport, vision, voice];
type Dict = typeof app.es & typeof debug.es & typeof guides.es & typeof habits.es & typeof hud.es & typeof relax.es & typeof selfReport.es & typeof vision.es & typeof voice.es;
export type Key = keyof Dict;
export const messages = {
  es: Object.assign({}, ...slices.map((slice) => slice.es)) as Record<Key, string>,
  en: Object.assign({}, ...slices.map((slice) => slice.en)) as Record<Key, string>,
};
