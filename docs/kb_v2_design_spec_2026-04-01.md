# KB v2 Design Spec

## Goal

Build a new knowledge-base workspace from scratch.

This is not a refactor of the current `WebKbPage`.

Target product shape:
- folder-first knowledge library
- policy-first access control
- file inheritance by default
- file override as a rare exception
- client-bot coverage as a first-class concept

## Product Principles

1. Folders are the main policy boundary.
2. Files inherit access unless there is an explicit exception.
3. Users should think in policies, not ACL rows.
4. Access changes must show impact before save.
5. Client-bot visibility must be visible in the main workflow.

## Interaction Model

Main user questions:
1. Where does this material live?
2. Who can search over it?
3. Does it inherit access or override it?
4. What will change if I save this policy?

## Screen Architecture

Three-column workspace:

1. `Library`
- left rail
- folder tree
- upload
- create folder
- structure-first navigation

2. `Materials`
- central workspace
- search
- filters
- coverage strip
- file list
- bulk actions

3. `Inspector`
- right rail
- `Overview`
- `Access`
- impact and warnings

## Default Information Architecture

Top-level library nodes:
- `All materials`
- `Shared`
- `Departments`
- `Clients`

This gives the product a default mental model instead of an empty uncontrolled tree.

## Main Screen

Expected behavior:
- left side shows the library map
- center shows materials for the selected node
- right side stays empty until a folder or file is selected

Key central elements:
- page header
- single main search
- compact filters
- compact coverage strip
- file list with:
  - name
  - path
  - status
  - access
  - inheritance
  - actions

## Folder Overview

Inspector in `Overview` mode for a folder must show:
- title
- full path
- materials count in subtree
- access summary
- client-bot coverage
- one strong CTA: `Configure access`

Folder is the main place to configure access.

## Folder Access Mode

Folder access must be preset-driven.

Primary policy cards:
- `Shared with staff`
- `Only department`
- `Only clients`
- `Only client group`
- `Staff and clients`
- `Custom`

Rules:
- presets first
- group picker appears only when needed
- impact card appears before save
- low-level ACL editor is hidden under `Custom` or advanced mode

## File Access Mode

File access must be inheritance-first.

Primary states:
1. `Inherited from folder`
2. `Exception`

Primary actions:
- `Keep inherited`
- `Create exception`

Only after selecting exception:
- show policy presets
- allow `Custom`

## Bulk Access Mode

Bulk access must be guided, not raw.

Required elements:
- selected files count
- policy presets
- impact preview
- advanced mode hidden by default

## Onboarding

### First Open Modal

3-step modal with media slot for GIF or short video:

1. How the library works
- folders define default access
- files inherit by default

2. How client-bot access works
- client bot searches only over allowed materials
- safest place to open access is the folder

3. How to avoid access chaos
- start with presets
- use file exceptions rarely
- use custom rules only when presets do not fit

### First Access Edit

Compact modal:
- choose a policy first
- custom rules are for rare exceptions

### First Client Policy

Inline hint:
- these materials will become searchable for the client bot

### First Bulk Change

Confirm dialog:
- how many files will open for clients
- how many will close

## Visual Direction

Not a generic CRM admin and not a pure Google Drive clone.

Direction:
- light knowledge workspace
- calm neutral background
- white working surfaces
- stronger typography hierarchy
- fewer random cards
- inspector as a serious tool, not a narrow sidebar leftover

## UI Foundation

Chosen frontend foundation:
- `Radix UI`
- `Tailwind`
- `class-variance-authority`
- `tailwind-merge`
- `lucide-react`

Base components to build around:
- `Panel`
- `WorkspaceSplit`
- `InspectorPanel`
- `Button`
- `Badge`
- `SegmentedControl`

## Rollout Strategy

1. Do not continue polishing the current `WebKbPage`.
2. Build `KB v2` as a separate route and surface.
3. Reuse only:
- backend APIs
- ACL/runtime logic
- data loaders
- coverage logic

4. Do not reuse:
- old page composition
- old inspector composition
- old access editor structure

## Implementation Order

1. Layout shell
2. Left rail
3. Workspace header and coverage strip
4. File list
5. Inspector overview
6. Folder access mode
7. File exception mode
8. Bulk access mode
9. Onboarding
10. Polish

## Explicit Freeze

Freeze the current KB UI except for critical bugs.

All further KB UX work should move into `KB v2`.
