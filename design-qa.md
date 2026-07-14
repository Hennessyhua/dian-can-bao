# Design QA

- Source visual truth: selected concept 3 from the design exploration
- Implementation screenshot: local QA asset `design-qa-assets/implementation-home-390x844.png` (not published)
- Combined comparison: local QA asset `design-qa-assets/source-vs-implementation.png` (not published)
- Annotation before/after comparison: local QA asset `design-qa-assets/annotation-before-after.png` (not published)
- Viewport: `390 × 844`
- State: home location selected, real sanitized recommendation loaded

## Full-view comparison evidence

The combined comparison shows the same pale-mint and white page structure, editorial serif headlines, green location treatment, coral date metadata, cobalt primary action, black secondary action, and three-item bottom navigation. The implementation intentionally removes the mock's non-functional menu and its duplicate large random button. Per the user's selected refinement, one random control remains and changes from `帮我选一个` to `换一个` after a result exists.

## Focused region comparison evidence

A separate crop was not needed because the combined 804 × 892 comparison keeps the header, both location controls, recommendation typography, actions, and bottom navigation readable. DOM checks separately verified control names, selected state, tab content, and the single-random-control constraint.

## Required fidelity surfaces

- Fonts and typography: Songti-style display typography and sans-serif control text reproduce the source hierarchy. Long real dish names wrap without clipping.
- Spacing and layout rhythm: header, location block, recommendation surface, actions, and bottom navigation preserve the source proportions at 390 × 844 with no horizontal overflow.
- Colors and visual tokens: pale mint, white, ink black, muted green, coral, and cobalt map closely to the source.
- Image quality and asset fidelity: the selected concept has no required raster imagery. Standard UI icons use Phosphor Icons; no emoji, custom SVG, or placeholder art is used.
- Copy and content: location labels, recommendation metadata, `换一个`, `就吃这个`, statistics, and history copy match the approved product decisions. Raw addresses never appear.

## Interaction verification

- Page content and both location labels rendered.
- Exactly one random control rendered.
- Random action changed the recommendation.
- `就吃这个` recorded a decision and displayed confirmation.
- Office location displayed the correct no-data state.
- More-filter controls rendered with accessible names.
- Statistics and history tabs opened successfully.
- No Vite error overlay or captured console error.
- Viewport was 390 × 844 with a 390px document width and no horizontal overflow.

## Comparison history

### Iteration 1

- Earlier P0 finding: a non-food accessory (`一次性餐具`) could be selected as a meal.
- Fix: the public-data sanitizer now removes tableware, packaging, medicine, test-kit, and similar non-food entries; orders with no remaining food items are excluded.
- Post-fix evidence: the public dataset contains 156 recommendable orders, the unit test passes, and the final browser screenshot shows a food recommendation.

### Iteration 2

- Earlier P2 evidence issue: one post-interaction Chrome capture contained compositor artifacts.
- Fix: the verification flow now reloads into a stable home state before the final capture.
- Post-fix evidence: the final implementation screenshot and combined comparison render cleanly.

### Iteration 3 — browser annotations

- Earlier P2 density issue: the two location options were stacked and occupied too much of the first viewport.
- Fix: the location radiogroup now uses two equal-width columns, compact icons, tighter padding, and a shorter section rhythm while preserving the full labels, order counts, selected state, and 44px+ touch targets.
- Earlier P1 content issue: raw dish names could expose marketing prefixes and operational notes, for example `【销量TOP】霸气嫩牛套餐（菜品不支持更换/包含米饭x1）`.
- Fix: the public-data generator removes bracketed marketing labels, bracketed specifications, leading decoration, and common marketing prefixes before data reaches recommendations, history, or statistics. Private raw orders remain unchanged.
- Post-fix evidence: `annotation-before-after.png` shows the compact two-column location layout and a clean recommendation name. The target example now publishes as `霸气嫩牛套餐`; five data tests pass.

## Findings

No actionable P0, P1, or P2 mismatch remains after the annotation update.

## Follow-up polish

- P3: `更多筛选` sits just below the first viewport for some long real dish names. This preserves the primary location and decision actions above the fold and is acceptable for the simplified product direction.

final result: passed
