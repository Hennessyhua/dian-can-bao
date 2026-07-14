# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

## Durable product decisions

- Visual source: the third generated concept selected on 2026-07-14, with pale mint surfaces, editorial Chinese typography, cobalt primary actions, coral metadata, and generous whitespace.
- Keep the home screen simple and mobile-first.
- Do not show a budget control or price filter.
- The only public location labels are `家（徐汇电影华苑）` and `新天地（徕卡办公室）`; never render a raw delivery address.
- `帮我选一个` and `换一个` are the same random action. Render one control only: use the initial label before a result and `换一个` after a result.
- The site is deployed as a static GitHub Pages app. Private scraped data stays outside the published artifact.
