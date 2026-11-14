/**
 * The cut-offs that turn MediaPipe's blendshape scores into "eyes closed" and "mouth open". One place, because the
 * worker that counts closed eyes, the overlay that colours them and the AI cross-check must all mean the same thing.
 * Yawns are not counted from these: the worker uses the detector calibrated on YawDD (./yawn).
 * Team placeholders until G2 calibrates them (goals/SCOPE-fatigue.md).
 */
/**
 * eyeBlink score above which an eye counts as closed, for PERCLOS, the held-closure score, the overlay and the AI
 * check. Team assumption from one person on the demo laptop (2026-11-15): looking down at the keyboard reads
 * 0.42 to 0.52 (one frame at 0.65) and closed eyes 0.77 to 0.82, so 0.5 counted typing as closed eyes. 0.65 is the
 * midpoint. The RLDD model keeps the 0.5 it was trained with (MODEL_BLINK in ./fatigueModel).
 */
export const BLINK = 0.65;
export const MOUTH_OPEN = 0.5; // jawOpen score above which the overlay and the AI check call the mouth open
