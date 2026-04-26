# RHK UI Design Spec (v2.0)

## Design Principles
- Calm clinical workspace: minimal visual noise, high readability, generous whitespace.
- Single-source styling: all core values come from design tokens (color, spacing, radius, shadow, type).
- Hierarchy by typography and spacing first; color as secondary signal.
- Consistent interaction language across all controls (hover, focus, pressed, disabled).
- Safety-first legibility: strong contrast for body text, explicit state colors for warnings/errors.
- Dense information, low cognitive load: cards/sections structure complex medical input clearly.
- Motion is subtle and purposeful; never blocks reading or data entry.
- Accessibility baseline: keyboard-visible focus states and no color-only affordances.

## Typography Scale
- Font family: `"Avenir Next", "SF Pro Text", "Segoe UI Variable", "Noto Sans", sans-serif`
- `text-xs`: 12px / 16px, weight 500
- `text-sm`: 13px / 18px, weight 500
- `text-md`: 14px / 20px, weight 500
- `text-lg`: 16px / 24px, weight 600
- `text-xl`: 20px / 28px, weight 700
- `title`: 26px / 32px, weight 760
- Label weight: 620
- Tab/section heading weight: 680-720

## Spacing Scale
- Base unit: 4px
- Scale: `4, 8, 12, 16, 24, 32, 48`
- Component paddings:
- Inputs/buttons: 10-12px horizontal, 8-10px vertical
- Cards: 16-20px
- Section header + body rhythm: 12px + 14-16px

## Color Palette
- Background: `#f4f6f8`
- Surface primary: `#ffffff`
- Surface secondary: `#f8fafc`
- Text primary: `#0f172a`
- Text secondary: `#334155`
- Text tertiary: `#64748b`
- Accent: `#0a6fd9`
- Accent subtle: `rgba(10,111,217,0.10)`
- Border subtle: `rgba(15,23,42,0.10)`
- Border strong: `rgba(15,23,42,0.18)`
- Success: `#15803d`
- Warning: `#b45309`
- Error: `#b91c1c`
- Info: `#1d4ed8`

## Component Standards
- Buttons:
- Same radius family, consistent heights, clear primary vs secondary.
- Hover lifts minimally; active state removes lift.
- Disabled lowers contrast and removes shadow.
- Inputs/Select/Textareas:
- Surface on white, subtle border, strong focus ring + border change.
- Error/safety marker states keep readable text and avoid over-saturated fills.
- Cards/Sections:
- Soft border + subtle shadow, no heavy gradients.
- Header strip communicates section identity; body stays clean white.
- Tables:
- Light header row, 1px separators, sticky readability with restrained contrast.
- Modals/Overlays:
- Surface-first, clear border, no dense decoration.
- Toasts/Feedback:
- Compact, semantic color accents, no blocking animation.
- Navigation (Tabs):
- Segmented-pill tabs with clear selected state and keyboard focus.
- Sticky behavior stays visually quiet and does not occlude content.

## Motion Rules
- Durations:
- Micro interactions: 120-180ms
- View/card entry: 220-320ms
- Easing: `cubic-bezier(0.22, 0.61, 0.36, 1)`
- Allowed:
- Hover/focus/pressed feedback
- Subtle first-load fade/translate on major shells/cards
- Not allowed:
- Infinite pulse/spinner-like decoration outside explicit loading indicators
- Large transforms that shift layout unexpectedly
- Reduced motion:
- Respect `prefers-reduced-motion: reduce` by removing non-essential animations.

## Screen Migration Scope (Top 3)
- `1. Klinik & Labor`: cleaner section headers, improved card rhythm, form density normalized.
- `2. Bildgebung & Echo/CMR`: same structural language; consistent accordion/input treatment.
- `3. Lungenfunktion & CPET`: unified module/card styling with calmer visual hierarchy.

## Dark Mode
- Not enabled in this iteration because the app currently enforces light mode at runtime.
- Token structure is prepared so a dark token set can be added without component rewrites.
