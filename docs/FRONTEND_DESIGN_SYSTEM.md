# RxLogic Frontend Design System — Foundation (Task 1)

## Goal
Establish the semantic design tokens for the next UI migration without changing
existing component appearance or behaviour in this task.

## Brand palette
| Token | Hex | Intended use |
|---|---|---|
| Deep navy | `#14263D` | Primary brand surfaces, headings and navigation |
| Intelligent teal | `#087F8C` | Primary accent and interactive emphasis |
| Soft ivory | `#F7F8F6` | Warm page/background surface |
| Pale blue | `#EAF1F5` | Subtle supporting surfaces |
| Slate grey | `#667587` | Secondary text and supporting labels |
| Success | `#16845B` | Positive status |
| Warning | `#B7791F` | Caution status |
| Danger | `#C13D45` | High-priority warning |
| Info | `#3478B9` | Informational status |

Status must never be communicated by colour alone. Keep a text label, icon, or
other visible cue alongside every semantic status colour.

## Typography
- Display: Manrope, with the existing system/SF fallbacks retained.
- UI/body: Inter, with the existing system/SF fallbacks retained.
- Monospace: existing SF Mono/system fallback stack.
- Fonts are not downloaded or self-hosted in this task. If a preferred font is
  unavailable on the user's machine, the fallback stack is used.

## Motion and accessibility
- Existing Apple-style easing and reduced-motion handling are preserved.
- Existing global `:focus-visible` treatment is preserved.
- Future component work should retain keyboard access, visible focus, semantic
  HTML, and reduced-motion support.
- Do not animate critical warnings in a way that delays or obscures them.

## Compatibility policy
- Existing colour aliases (`obsidian`, `charcoal`, `ash`, `fog`, `slate`) and
  `font-clarkson` are deliberately retained. Existing components continue to
  compile and render while later tasks migrate them to semantic tokens.
- Existing API, routing, form state, and backend integration are untouched.
- The new palette is foundational only; this task does not claim that the whole
  application has already been visually migrated.

## Files changed
- `frontend/tailwind.config.js`
- `frontend/src/index.css`

## Next implementation sequence
1. Apply the semantic tokens to the app shell and navigation.
2. Redesign the landing hero and product story.
3. Upgrade the medication input workspace.
4. Upgrade plan results, warning hierarchy, explainability, and history.
5. Complete responsive, accessibility, and visual QA.
