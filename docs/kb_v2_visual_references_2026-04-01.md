# KB v2 Visual References

## Goal

Fix the visual and interaction direction for `KB v2` before implementation.

This document is not about copying one product.
It defines what to borrow, what to reject, and what to combine.

## Recommended Product Pattern

Use a hybrid:
- Drive-like folder navigation
- Dropbox-like group/folder permission model
- Confluence-like inheritance and restriction logic
- modern inspector-based workspace layout

Do not build:
- a pure Google Drive clone
- a wiki-first Confluence clone
- a generic admin table screen

## Reference 1: Dropbox team folders

Source:
- https://help.dropbox.com/organize/team-folders
- https://help.dropbox.com/teams-admins/admin/centralize-data-team-folders

What to borrow:
- folder as the main permission boundary
- groups as the main permission principal
- restricted folder inside a wider shared space
- team folder as the hub of content for a team

Why it matters:
- our KB permissions model should be folder-first
- department and client-group access should feel natural

What not to copy:
- raw file-manager look
- minimal semantic explanation around retrieval and bot access

## Reference 2: Confluence page restrictions

Source:
- https://confluence.atlassian.com/doc/permissions-overview-139414.html
- https://confluence.atlassian.com/display/CONF717/Page%2BRestrictions

What to borrow:
- clear distinction between inherited and explicit restrictions
- group-based restrictions
- separate visibility of restriction state
- parent restrictions affecting child content

Why it matters:
- file override must be visibly exceptional
- inheritance must be explicit in UI

What not to copy:
- page-first wiki structure
- restriction flow hidden behind small top-level icons

## Reference 3: Google Drive shared drives

Source:
- https://support.google.com/drive/answer/7286514
- https://support.google.com/drive/answer/7166529
- https://support.google.com/drive/answer/2494822

What to borrow:
- clean tree navigation
- simple central file list
- strong mental model around shared folder inheritance
- guidance that access is usually managed at folder level

Why it matters:
- users already understand this model
- it reduces cognitive load for material management

What not to copy:
- weak support for knowledge semantics
- no first-class concept of retrieval coverage or bot visibility

## Reference 4: Notion sidebar

Source:
- https://www.notion.com/help/guides/navigating-with-the-sidebar

What to borrow:
- sidebar as a navigation hub
- visible structure sections
- calm workspace feeling

Why it matters:
- the left rail should feel like a library map, not a raw tree widget

What not to copy:
- document-centric workspace as the primary model
- private/shared/teamspace semantics directly

## Reference 5: Figma Dev Mode

Source:
- https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode
- https://help.figma.com/hc/en-us/articles/15023152204951-Navigate-designs-in-Dev-Mode
- https://www.figma.com/dev-mode/

What to borrow:
- split workspace with strong side rails
- clear inspect panel
- side-by-side operational work and inspection

Why it matters:
- our inspector should feel like a real work tool
- not like a narrow leftover sidebar

What not to copy:
- design-file specific metaphors
- overly tool-like developer UI details

## Best-Practice Conclusions

### 1. Folder-first policy

Borrowed from Dropbox and Drive.

Decision:
- folders define default access
- files inherit by default
- file exceptions stay secondary

### 2. Explicit inheritance

Borrowed from Confluence.

Decision:
- every file must visibly show:
  - inherited
  - exception
- every folder must show whether it has explicit policy

### 3. Groups over individuals

Borrowed from Dropbox and Confluence.

Decision:
- main presets should target:
  - all staff
  - selected department
  - all clients
  - selected client group
- individual user rules stay advanced mode

### 4. Inspector-first operations

Borrowed from Figma Dev Mode.

Decision:
- the right side is a serious inspector
- `Overview` and `Access` live there
- access change flows stay contextual

### 5. Coverage as first-class product feedback

This is our own product requirement.

Decision:
- KB UI must show:
  - ready materials
  - client-visible materials
  - group-only materials
  - closed materials
- changes must preview impact before save

## Moodboard Direction

### Tone
- light
- calm
- deliberate
- structured
- knowledge-work, not CRM

### Surfaces
- warm neutral page background
- white panels
- soft borders
- fewer giant rounded cards
- stronger separation between columns

### Color roles
- blue: primary actions
- green/teal: client-visible states
- amber: warnings and impact
- muted red/rose: restricted or dangerous actions
- quiet slate neutrals: metadata and structure

### Typography
- stronger hierarchy than current UI
- fewer tiny low-contrast labels
- inspector content should read like a document, not a form dump

## UI Direction to Reject

Do not continue with:
- current blue-heavy admin look
- same old KB page geometry
- giant summary cards stacked in a narrow sidebar
- showing low-level ACL rows too early
- mixing content management and access management in one visual layer

## Final Direction

`KB v2` should look like:
- a modern knowledge workspace
- with a file library in the center
- a structural library map on the left
- and an inspector-driven policy tool on the right

In short:
- Drive for structure
- Dropbox for group access logic
- Confluence for inheritance discipline
- Figma-style inspector for operations
