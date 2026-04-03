# KB v2 Layout Tokens

## Goal

Fix layout and UI token rules for `KB v2` before implementation.

These tokens are specific to the new KB workspace and should not inherit the current page geometry by default.

## Layout Grid

### Page
- width: `100%`
- target minimum width: `1280px`
- page padding:
  - desktop: `24px`
  - narrow desktop: `20px`

### Columns
- left rail: `296px`
- center workspace: `minmax(640px, 1fr)`
- inspector: `420px`

### Gaps
- column gap: `20px`
- section gap inside panels: `20px`
- compact controls gap: `12px`

### Responsive rule
- inspector should not shrink below `380px`
- under that threshold, inspector should switch to drawer / overlay mode

## Surface Tokens

### Page background
- `#F5F7FA`

### Panel background
- `#FFFFFF`

### Border color
- `#E5EAF2`

### Shadows
- very soft
- border-led surfaces, not heavy floating cards

### Radius
- large panels: `20px`
- small controls: `12px`
- pills / badges: `999px`

## Typography Tokens

### Page title
- size: `28px`
- weight: `700`
- line-height: `1.15`

### Section title
- size: `18px`
- weight: `600`

### Body
- size: `14-15px`
- weight: `400-500`

### Meta label
- size: `12-13px`
- muted color

### Numeric stats
- size: `24px`
- weight: `700`

## Color Roles

### Text
- primary: `#0F172A`
- secondary: `#516074`
- muted: `#7B8797`

### Primary actions
- fill: `#1D78D6`

### Staff access
- slate / blue tint

### Client-visible
- teal / green tint

### Warning / impact
- amber tint

### Danger
- rose / red tint

## Control Tokens

### Buttons
- standard height: `40px`
- compact height: `32px`
- horizontal padding: `14-16px`

### Inputs
- standard input height: `40px`
- search input height: `44px`

### Rows
- file row height: `68-76px`
- folder row height: `40-44px`

### Badges
- height: `24px`
- horizontal padding: `10px`
- inter-badge gap: `6px`

## Structural Rules

### Left Rail
Should feel like a library map.

Contains:
- upload
- new folder
- fixed roots
- folder tree

### Center Workspace
Should feel like the operating surface.

Contains:
- header
- search and filters
- coverage strip
- materials list

### Inspector
Should feel like a decision surface.

Contains:
- selected object summary
- mode switch
  - `Overview`
  - `Access`
- current working panel

## Access UI Rules

### Folder access
- presets first
- group picker second
- impact third
- save footer
- advanced rules collapsed

### File access
- inheritance card first
- explicit choice:
  - keep inherited
  - create exception
- only then presets

### Bulk access
- selection summary first
- presets second
- impact third
- advanced rules collapsed

## Onboarding Tokens

### Modal
- width: `880-960px`
- two-column structure:
  - text
  - media

### Media slot
- rounded panel
- aspect ratio near `16:10`
- supports:
  - GIF
  - short MP4
  - short WebM

### Hint cards
- pale background
- icon + short copy
- not tooltip-only

## Responsive Rules

### `>= 1440px`
- full three-column layout

### `1280px - 1439px`
- full three-column layout
- slightly tighter gaps

### `1024px - 1279px`
- left rail narrower
- inspector can move to slide-over mode

### `< 1024px`
- stacked fallback
- tree
- list
- drawer inspector

## Core UX Rule

The layout must make these truths obvious without extra explanation:

1. folder defines policy
2. file inherits by default
3. client-bot coverage matters
4. access changes have visible impact
