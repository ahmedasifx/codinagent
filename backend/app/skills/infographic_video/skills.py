"""Infographic Video skills (Remotion).

Six granular, reusable skills plus one composite skill that orchestrates the full
pipeline. The agent selects the composite skill; the granular skills are registered
for composition/reuse (and listed as `sub_skills`).
"""

from ...registries.skill_registry import register_skill
from ...registries.types import SkillDef

_FILE_TOOLS = ["write_file", "read_file", "list_files", "run_command", "install_package"]
_RENDER_TOOLS = _FILE_TOOLS + ["render_remotion"]

register_skill(
    SkillDef(
        slug="storyboard_generation",
        name="Storyboard Generation",
        description="Turn a prompt into a structured storyboard JSON.",
        when_to_use="plan the narrative/scenes of an infographic video before building it",
        required_tools=["write_file"],
        instructions="""Produce a storyboard as JSON and write it to {project}/storyboard.json:
{ "title": str, "fps": 30, "width": 1920, "height": 1080,
  "scenes": [ { "id": "s1", "duration_s": 4, "narration": str, "visual": str, "data": {...} } ] }
Keep 4–7 scenes. `visual` describes the on-screen layout/animation; `data` holds any
numbers/labels to animate (counts, bars, percentages).""",
    )
)

register_skill(
    SkillDef(
        slug="scene_definition",
        name="Scene Definition",
        description="Expand storyboard scenes into concrete component specs.",
        when_to_use="convert a storyboard into per-scene layout/animation specs",
        required_tools=["read_file", "write_file"],
        instructions="""Read storyboard.json and expand each scene into a concrete spec:
layout regions, text, colors (consistent palette), entry/exit transitions, and the
frame ranges each element animates over (derive from duration_s * fps).""",
    )
)

register_skill(
    SkillDef(
        slug="remotion_component_generation",
        name="Remotion Component Generation",
        description="Scaffold the Remotion project + scene components.",
        when_to_use="write the Remotion React/TSX project for the storyboard",
        required_tools=_FILE_TOOLS,
        instructions="""Scaffold a Remotion project under {project}:
- package.json with deps: remotion, @remotion/cli, react, react-dom (and devDeps:
  typescript, @types/react). Add script "render": "remotion render".
- tsconfig.json (jsx: react-jsx, esModuleInterop, skipLibCheck).
- src/index.ts → import {registerRoot} from 'remotion'; import {RemotionRoot} from './Root'; registerRoot(RemotionRoot).
- src/Root.tsx → export RemotionRoot with one <Composition id="Main" component={Main}
  durationInFrames={total} fps={fps} width={width} height={height} />.
- src/Main.tsx → a <Series> (or <Sequence>) chaining one component per scene; use
  useCurrentFrame, interpolate, spring, AbsoluteFill from 'remotion' for animations.
- One component file per scene under src/scenes/.
Then run_command("npm install", cwd={project}) — this is slow, be patient.

## Remotion correctness rules (avoid blank/invisible output)
- useCurrentFrame() is <Sequence>-LOCAL: base interpolate() ranges on local frames and
  always clamp ({extrapolateLeft:'clamp', extrapolateRight:'clamp'}). Never leave an
  element at opacity 0 / off-canvas for the whole clip.
- Any CSS-3D: keep rotateX/rotateY small (±15°), never ~±90°; set explicit perspective and
  transformOrigin; give 3D elements a solid background and fixed size so they can't
  collapse to a sliver.
- Fonts: if using @remotion/google-fonts, await readiness (waitUntilDone() /
  delayRender→continueRender) or text won't render.
- Don't cover content with full-screen opaque overlays; keep z-order sane.
- Verify with `npx remotion still <comp> out/_t.png --frame=N` at a few frames and confirm
  the subject + text are visible BEFORE the full render.""",
    )
)

register_skill(
    SkillDef(
        slug="voiceover",
        name="Voiceover",
        description="Generate narration audio per scene (optional).",
        when_to_use="add spoken narration to the video",
        required_tools=["tts", "write_file"],
        instructions="""Optional. For each scene's narration call tts(text, out_path=
"{project}/public/audio/<scene_id>.mp3"). If TTS is not configured, skip audio and
render a silent video. Reference audio in components with <Audio src={staticFile(...)}>.""",
    )
)

register_skill(
    SkillDef(
        slug="subtitle_generation",
        name="Subtitle Generation",
        description="Generate captions/subtitles from narration.",
        when_to_use="add on-screen captions/subtitles",
        required_tools=["write_file"],
        instructions="""Generate captions from each scene's narration with timings derived
from scene durations. Render them as animated text in the scene components (preferred)
or write a .srt under {project}/public/.""",
    )
)

register_skill(
    SkillDef(
        slug="video_rendering",
        name="Video Rendering",
        description="Render the Remotion composition to mp4.",
        when_to_use="produce the final downloadable video file",
        required_tools=["render_remotion", "list_files"],
        instructions="""Render with render_remotion(project_dir={project},
composition_id="Main"). On failure, read the logs, fix the components, and retry.
Report the download URL to the user.""",
    )
)

# ── Composite (entry) skill ──
register_skill(
    SkillDef(
        slug="create_infographic_video",
        name="Create Infographic Video",
        description="End-to-end infographic video generation with Remotion.",
        when_to_use="any request to create/generate an infographic or animated explainer video",
        required_tools=_RENDER_TOOLS + ["tts"],
        sub_skills=[
            "storyboard_generation",
            "scene_definition",
            "remotion_component_generation",
            "voiceover",
            "subtitle_generation",
            "video_rendering",
        ],
        instructions="""Build an infographic video end-to-end with Remotion. Use the
project directory /home/user/app/video. Execute the pipeline in order:

1. STORYBOARD — write storyboard.json (title, fps=30, width=1920, height=1080,
   4–7 scenes each with id, duration_s, narration, visual, data).
2. SCENES — expand each scene into a concrete spec (layout, palette, transitions,
   frame ranges = duration_s * fps).
3. COMPONENTS — scaffold the Remotion project: package.json (remotion, @remotion/cli,
   react, react-dom), tsconfig.json, src/index.ts (registerRoot), src/Root.tsx (one
   <Composition id="Main" .../>), src/Main.tsx (chain scenes with <Series>), and one
   component per scene under src/scenes/. Animate with useCurrentFrame/interpolate/
   spring/AbsoluteFill. Then run_command("npm install", cwd="/home/user/app/video").
4. VOICEOVER (optional) — tts() per scene into public/audio/; skip if not configured.
5. SUBTITLES — animate captions in components from each scene's narration.
6. RENDER — render_remotion(project_dir="/home/user/app/video", composition_id="Main").
   Fix any render errors from the logs and retry until it succeeds.

Finish by giving the user the download URL. Keep the design clean and modern: bold
type, a consistent color palette, smooth easing, and readable data viz.""",
    )
)
