"""Mobile app demo video skills (Remotion).

Specialised for app demos: a phone-frame mockup, designed app screens, and
tap/swipe/scroll transitions, rendered portrait (9:16). Reuses the same Remotion
render pipeline (render_remotion) as the infographic video agent, plus the granular
remotion skills as sub-skills for composition.
"""

from ...registries.skill_registry import register_skill
from ...registries.types import SkillDef

_TOOLS = [
    "write_file", "read_file", "list_files",
    "run_command", "install_package", "render_remotion", "tts",
]

register_skill(
    SkillDef(
        slug="app_screen_design",
        name="App Screen Design",
        description="Design individual mobile app screens as React components.",
        when_to_use="design the in-app screens shown in a mobile demo",
        required_tools=["write_file", "read_file"],
        instructions="""Design each app screen as a self-contained React component sized to
the device viewport (e.g. 1080×2160 inner, or scaled). Include a realistic status bar
(time, battery, signal), a nav/header, and clean modern content (cards, lists, buttons,
tab bar). Use a cohesive palette and real-looking copy/data — not lorem ipsum.""",
    )
)

register_skill(
    SkillDef(
        slug="mobile_app_demo",
        name="Mobile App Demo Video",
        description="End-to-end mobile app demo video with a phone frame and animated screens.",
        when_to_use="any request to create a mobile app demo / app store preview / product walkthrough video",
        required_tools=_TOOLS,
        sub_skills=[
            "storyboard_generation",
            "app_screen_design",
            "remotion_component_generation",
            "subtitle_generation",
            "video_rendering",
        ],
        instructions="""Build a mobile app demo video end-to-end with Remotion. Work under
/home/user/app/appdemo. Output is PORTRAIT 1080×1920, fps=30 (App Store / social format).

Pipeline:
1. STORYBOARD — write storyboard.json: { appName, tagline, fps:30, width:1080,
   height:1920, scenes:[ { id, duration_s, feature, narration, screen } ] }. Pick 4–6
   key features/screens that tell a coherent "what the app does" story.

2. SCREENS — design each app screen as a React component (see app_screen_design): status
   bar, header, realistic content, tab bar. Keep a consistent design system across screens.

3. DEVICE FRAME — build a reusable <PhoneFrame> component: a centered phone mockup
   (rounded corners ~48px, dark bezel, notch/dynamic-island, subtle shadow) with the
   active screen rendered INSIDE the frame via clipping. The video canvas is 1080×1920;
   the phone sits centered with padding and a tasteful background (gradient or brand color).

4. REMOTION PROJECT — scaffold under /home/user/app/appdemo:
   - package.json (remotion, @remotion/cli, react, react-dom; devDeps typescript, @types/react),
   - tsconfig.json, src/index.ts (registerRoot), src/Root.tsx with one
     <Composition id="Main" component={Main} durationInFrames={total} fps={30}
     width={1080} height={1920} />,
   - src/Main.tsx chaining scenes with <Series>, each scene = <PhoneFrame><ScreenX/></PhoneFrame>,
   - src/PhoneFrame.tsx and src/screens/*.tsx.
   Then run_command("npm install", cwd="/home/user/app/appdemo") — slow, be patient.

5. INTERACTION ANIMATIONS — make it feel alive: screen-to-screen SWIPE transitions
   (slide the inner screen with interpolate), a TAP indicator (an expanding ring at the
   tap point before a navigation), in-screen SCROLL (translateY on a list), and spring
   entrances for key UI elements. Use useCurrentFrame, interpolate, spring, AbsoluteFill.
   Add a title card (app name + tagline) at the start and an outro with App Store / Google
   Play badges + CTA.

6. CAPTIONS — overlay a short feature caption per scene (animated in), derived from each
   scene's narration.

7. VOICEOVER (optional) — if asked and TTS is configured, tts() narration per scene into
   public/audio/; otherwise render silent.

8. RENDER — first verify, then render:
   - Render STILLS at key frames and confirm the phone + a screen + text are visible and
     centered (NOT edge-on): npx remotion still {entry} Main out/_t.png --frame=N.
   - Then render_remotion(project_dir="/home/user/app/appdemo", composition_id="Main").
   - render_remotion also returns verification stills + a blank-frame warning; if it warns
     the frames look blank/static, fix the components and re-render. Give the download URL.

## Remotion correctness rules (avoid the common "blank video" failures)
- CSS-3D: keep rotateX/rotateY SMALL (±15°) — NEVER near ±90° (the phone goes edge-on and
  disappears). Set an explicit perspective (~1200px) and transformOrigin: 'center center'.
  Give the phone a fixed width/height and a solid opaque screen background so it can't
  collapse to a sliver.
- Frame model: useCurrentFrame() is <Sequence>-LOCAL. Base every interpolate() range on
  local frames, and ALWAYS pass {extrapolateLeft:'clamp', extrapolateRight:'clamp'}. Never
  leave an element stuck at opacity 0 or translated off-canvas for the whole clip.
- Fonts: load Inter via @remotion/google-fonts and await readiness (waitUntilDone(), or
  delayRender→continueRender) before relying on text, or text won't appear.
- Layering: don't cover content with a full-screen opaque scrim/vignette except the
  intended end card; keep z-index sane and the phone above the backdrop.
- Build INCREMENTALLY: get a static phone + one screen + the title visible (verify a
  still) BEFORE adding camera moves / cross-fades. Don't write all chapters blind.

Design bar: crisp, modern, App-Store-quality. Smooth easing, no janky cuts, readable text.""",
    )
)
