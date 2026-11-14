# PULSAR brand

**PULSAR**: Personal Unit for Learning, Support, Assistance & Reminders.
Tagline: *Meet P.U.L.S.A.R., your personal health companion in space.*

| File | Use |
|---|---|
| `pulsar-intro.html` | Opening film (41 s, dramatization), followed by a scrollable crew journey and pitch landing page. Open it in a browser and press Play (sound is synthesised in the page, no audio files). Space pauses, ← → seek 5 s, `M` mutes, `F` fullscreen, `R` restarts while viewing the film. Single file, mascot embedded, works offline (without network the fonts fall back to the system ones). To get a video of the opening, record the screen while it plays. |
| `pulsar-mascot.png` | Mascot, original render (1536×1024, navy backdrop). |
| `pulsar-mascot.webp` | Same render, compressed (68 KB) for the web. |

## Presenting the journey

After the film, choose **Follow the crew journey**; **Skip film** opens it directly.
Use the **EN / ES** selector at the top right to switch the entire presentation,
including the opening captions, player controls, accessibility labels and journey.
Spanish is the default; the browser remembers the last selection when storage is
available. Open with `?lang=en` or `?lang=es` to select a language explicitly.
Switching language preserves playback position and the selected journey step.
Chapter navigation follows the fictional engineer Alex through the problem, an interactive
Notice → Check → Support walkthrough, the system design, and the prototype's scope.
The walkthrough uses illustrative inputs and copy, not a live camera, reaction-time test, or rules engine.
Its three tabs also support arrow keys, Home, and End. Replay links restart the opening film.

Chapter labels suggest a 2:45 pitch including the opening: problem (0:41–1:00), journey
(1:00–1:55), design (1:55–2:25), and scope/closing (2:25–2:45). Navigation is manual;
there is no automatic timer after the film. Local processing and privacy are presented as
design intentions, without implying measured accuracy or spaceflight validation.

## GitHub Pages

The presentation was previously hosted separately in
[`alejandrogiga/pulsar-presentation`](https://github.com/alejandrogiga/pulsar-presentation)
at <https://alejandrogiga.github.io/pulsar-presentation/>. At the owner's request,
Pages was disabled and the hosting repository made private. It contains only
the standalone page, published as `index.html`, and hosting documentation.

Keep updates local unless publication is explicitly requested again. This project
remains the source of the presentation; the hosting repository does not contain
the rest of the project. The original project repository is still public.

## Palette

| Token | Hex | Where it comes from |
|---|---|---|
| Space | `#050e2f` | The render's backdrop |
| Space lift | `#0d1a44` | Glow behind the mascot |
| Pulse | `#5ef2ec` | Visor face and heartbeat |
| Orbit | `#9a8cff` | Orbit ring |
| Shell | `#eef1fb` | Mascot body |

Type: Unbounded (display), Manrope (body), JetBrains Mono (labels).
