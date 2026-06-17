"""Marketing skills — initial capability: Instagram post generator."""

from ...registries.skill_registry import register_skill
from ...registries.types import SkillDef

_TOOLS = ["write_file", "read_file", "run_command", "install_package", "execute_python", "save_artifact"]

register_skill(
    SkillDef(
        slug="instagram_post",
        name="Instagram Post Generator",
        description="Generate copy + a designed 1080×1080 image for an Instagram post.",
        when_to_use="create an Instagram/social post image with copy and a designed layout",
        required_tools=_TOOLS,
        instructions="""Create an Instagram post end-to-end. Work under /home/user/app/post.

1. COPY — write a punchy caption (with 3–6 relevant hashtags) and the on-image headline.
2. DESIGN — write index.html + styles for a 1080×1080 post: a strong headline, optional
   subtext/brand mark, a cohesive modern color palette, large legible type, good spacing.
   Make the root element exactly 1080×1080px.
3. RENDER to PNG with headless Chromium via Playwright in the sandbox:
   - run_command("pip install playwright -q && playwright install --with-deps chromium",
     cwd="/home/user/app/post")  # first run is slow
   - execute_python with:
       from playwright.sync_api import sync_playwright
       with sync_playwright() as p:
           b = p.chromium.launch()
           pg = b.new_page(viewport={"width":1080,"height":1080})
           pg.goto("file:///home/user/app/post/index.html")
           pg.screenshot(path="/home/user/app/post/post.png")
           b.close()
4. save_artifact("/home/user/app/post/post.png", "image") and give the user the download
   URL plus the caption text.""",
    )
)
