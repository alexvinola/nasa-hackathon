/**
 * The cut-offs that turn MediaPipe's blendshape scores into "eyes closed" and "mouth open". One place, because the
 * worker that counts closed eyes, the overlay that colours them and the AI cross-check must all mean the same thing.
 * Yawns are not counted from these: the worker uses the detector calibrated on YawDD (./yawn).
 * Team placeholders until G2 calibrates them (goals/SCOPE-fatigue.md).
 */
export const BLINK = 0.5; // eyeBlink score above which an eye counts as closed
export const MOUTH_OPEN = 0.5; // jawOpen score above which the overlay and the AI check call the mouth open
