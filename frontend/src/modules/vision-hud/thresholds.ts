/**
 * The cut-offs that turn MediaPipe's blendshape scores into "eyes closed" and "mouth open". One place, because the
 * worker that counts them, the overlay that colours them and the AI cross-check must all mean the same thing.
 * Team placeholders until G2 calibrates them (goals/SCOPE-fatigue.md).
 */
export const BLINK = 0.5; // eyeBlink score above which an eye counts as closed
export const MOUTH_OPEN = 0.5; // jawOpen score above which the mouth counts as open
export const YAWN_MS = 1000; // the mouth must stay open this long to count as a yawn rather than speech
