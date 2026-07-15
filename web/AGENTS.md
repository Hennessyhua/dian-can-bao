# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

## Durable product decisions

- Visual source: the third generated concept selected on 2026-07-14, with pale mint surfaces, editorial Chinese typography, cobalt primary actions, coral metadata, and generous whitespace.
- Keep the home screen simple and mobile-first.
- Do not show a budget control or price filter.
- Keep full public location labels as `家（徐汇电影华苑）` and `新天地（徕卡办公室）`, but display the compact filter labels `家 · 电影华苑` and `新天地 · 徕卡`; never render a raw delivery address.
- `帮我选一个` and `换一个` are the same random action. Render one control only and always label it `换一个`.
- The compact scrollable title is one line only: `今天吃什么？`; do not pin it above the content.
- Show the muted slogan `点中哪个吃哪个` below the title.
- The home screen filters by `早饭` / `午饭` / `晚饭` before location. Do not restore the confirm/`就吃这个` action.
- Use `啥时候吃呀？` and `在哪吃饭呀？` as the two filter subtitles. All five filter cards share the same fixed height, radius, border, hover, active, and low-saturation green selected state.
- Clicking an already selected meal-period or location card clears that dimension to `all`; no card is highlighted while the dimension is cleared.
- Use one global Songti-style font stack across titles, controls, metadata, navigation, statistics, and history; do not mix serif and sans-serif families.
- Recommendations must come only from archived independent meal items; never recommend rice, condiments, flavors, sides, gifts, tableware, medicine, retail goods, or other auxiliary entries.
- Random candidates are unique by canonical `dishId`; repeated orders, dates, branches, and reviewed aliases of the same dish must not produce duplicate choices.
- The site is deployed as a static GitHub Pages app. Private scraped data stays outside the published artifact.
