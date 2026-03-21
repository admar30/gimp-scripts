# Guidecut UI Theme Specification

Status: Draft v0.3  
Date: 2026-03-21

## 1. Purpose
Define a visual/theme system for the Guidecut UI that improves readability, hierarchy, and interaction clarity while staying lightweight for `tkinter`.

## 2. UX Goals
1. Make primary actions obvious (`Run`, `Open Folder`, validation states).
2. Improve scanability of the form and status output.
3. Keep the UI professional and neutral for long-running utility use.
4. Maintain high contrast and keyboard-first usability.

## 3. Theme Strategy
- Base on `ttk` style overrides (no custom widget framework).
- Support `light` first; add optional `dark` extension later.
- Centralize colors, spacing, and type in a token map.
- Visual direction for this pass: slightly darker overall with a teal-forward accent palette.

## 4. Design Tokens (Light Theme)
## 4.1 Color Tokens
- `bg.app`: `#DCE8EA`
- `bg.panel`: `#EAF2F3`
- `bg.input`: `#F2F8F8`
- `bg.tooltip`: `#D6F0EE`
- `text.primary`: `#16363B`
- `text.secondary`: `#2F5A60`
- `text.inverse`: `#FFFFFF`
- `border.default`: `#8DA8AE`
- `border.focus`: `#0F8F84`
- `state.success`: `#0C7A56`
- `state.warning`: `#9A5A0A`
- `state.error`: `#A22A2A`
- `action.primary`: `#0F766E`
- `action.primary.hover`: `#0B5E57`
- `action.secondary`: `#245A61`
- `action.secondary.hover`: `#1B464C`

## 4.2 Spacing Tokens
- `space.xs`: `4`
- `space.sm`: `8`
- `space.md`: `12`
- `space.lg`: `16`
- `space.xl`: `24`

## 4.3 Radius Tokens
- `radius.sm`: `8` (input fields and dropdown)
- `radius.md`: `10` (optional larger controls)

## 4.4 Typography Tokens
- Font family: platform-default sans (`Segoe UI` on Windows, `SF Pro`/system on macOS).
- `font.body`: 10-11 pt
- `font.label`: 10-11 pt semibold
- `font.status`: monospaced (`Consolas`/`Menlo`) 9-10 pt
- `font.help`: 9-10 pt

## 5. Component Styling
## 5.1 Window and Panels
- App root uses `bg.app`.
- Main content frame uses `bg.panel`.
- Use subtle border/padding separation around status output.

## 5.2 Inputs
- Entry and combobox background `bg.input`.
- Entry and combobox should use rounded corners (`radius.sm`).
- Focus ring/border uses `border.focus`.
- Invalid input adds red border + optional short inline message.

## 5.3 Buttons
- Primary button: `Run`
  - Fill: `action.primary`
  - Text: `text.inverse`
  - Hover: `action.primary.hover`
- Secondary button: `Open Folder`, `Browse...`, `Browse Output...`
  - Fill: neutral (`bg.panel`)
  - Border: `border.default`
  - Hover: soft tint.

## 5.4 Tooltip
- Use `bg.tooltip`, thin border `border.default`, and `font.help`.
- Content uses 3 short lines:
  - selected format
  - tile/page count
  - A4 size multiple

## 5.5 Status Output
- Background: very light teal-neutral (`#EAF3F4`).
- Stdout text uses `text.primary`.
- Stderr text uses `state.error`.
- Prefix stderr lines with `ERROR:` (already implemented).

## 6. Interaction States
- Hover: non-primary controls use subtle tint/border shift.
- Focus: visible focus indicator on all tabbable controls.
- Disabled: reduce contrast and block pointer feedback.
- Running state:
  - Disable `Run`.
  - Keep browse/open controls active where safe.

## 7. Layout and Sizing Rules
- Minimum width: `760px` (current baseline).
- Maintain form column alignment: labels left, inputs stretch.
- Usage instruction block stays above input field with muted text color.
- Keep vertical rhythm with `space.sm`/`space.md`.

## 8. Accessibility Requirements
- Contrast target: WCAG AA for text and controls.
- Tooltip details must be reachable via keyboard focus, not hover-only.
- Preserve tab order:
  - input -> browse -> format -> info -> output toggle -> output field -> browse output -> open folder -> run -> status.

## 9. Implementation Plan (Tkinter)
1. Add `theme.py` with token dictionary + style factory.
2. Configure `ttk.Style()` at startup (`clam` base recommended for reliable styling).
3. Apply named styles:
  - `Primary.TButton`
  - `Secondary.TButton`
  - `Help.TLabel`
  - `Status.TFrame`
4. Style `ScrolledText` manually via widget config for background/foreground.
5. Keep all colors/types centralized to avoid scattered literals.

## 10. Acceptance Criteria
1. UI has clearly distinct primary and secondary actions.
2. Focus and error states are visually obvious.
3. Tooltip and status text are readable and consistent.
4. Usage instructions are visually secondary but clear.
5. Theme values come from centralized tokens.
