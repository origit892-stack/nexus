# BunkerGame Context Pack

## Purpose

This context exists to help the Nexus Understanding Model interpret
requests about BunkerGame correctly.

It is contextual knowledge, not permission to perform work.

## Project

BunkerGame is a Roblox game project containing an authored world,
terrain, bunker/environment content, reusable world assets, gameplay
systems, generated 3D content, and supporting development tooling.

The durable project workflow uses filesystem-authored content and Rojo.
Roblox Studio is used for runtime and visual verification.

## Source of Truth

Permanent authored project changes should remain represented in the
filesystem/Rojo source rather than depending only on Studio-local edits.

The Understanding Model must not assume that every historical artifact,
backup, report, screenshot, experiment, or generated intermediate file
is part of the current production game.

## Terrain Safety

The game already has terrain.

Before terrain or major world modification, create and verify a fresh
recoverable backup.

Do not perform a whole-world Terrain Clear operation unless explicitly
requested after a verified backup.

Targeted terrain changes are preferred over destructive global changes.

## Assets

Reusable game-world assets may exist as source models, generated
assets, meshes, manifests, production artifacts, Roblox asset
references, or other project representations.

A directory name alone does not prove that a production asset exists.

When identifying assets, evidence should come from actual model,
mesh, source, manifest, registry, provenance, or usage information.

Historical backups, screenshots, QA evidence, reports, temporary
experiments, reconstruction intermediates, and unrelated documentation
are not automatically current production assets.

Related variants may be grouped into families only when evidence
supports the relationship.

## Current Asset Workflow Direction

For a broad asset-review workflow, the intended sequence can include:

discovery
-> evidence-backed inventory
-> categorization
-> family grouping
-> technical and visual review
-> candidate selection
-> user review
-> verified backup
-> world placement
-> runtime/visual verification

The current user request determines which of these phases is actually
authorized now.

Do not assume later phases are authorized merely because they may be
part of a future workflow.

## 3D Toolchain

Blender and Open3D are available locally for geometry analysis,
technical QA, optimization, segmentation, mesh work, and animation
work when relevant.

Cube may participate in later mesh-generation or mesh-editing work.

The existence of these tools does not mean they should be used for
every request.

## Understanding Model Rules

The Understanding Model has no tools.

It does not inspect files.

It does not execute tasks.

It does not invent project facts.

Anything not established by:
1. the user's request, or
2. this context pack

must be represented as unknown or requiring discovery.

The Understanding Model should distinguish:
- what the user explicitly requested,
- the desired end result,
- what phase is currently requested,
- known context,
- unknown facts,
- constraints,
- allowed or forbidden mutation,
- evidence needed,
- irrelevant material,
- the recommended execution plan,
- completion criteria,
- and the expected response style.

Explicit user instructions have priority over assumptions.

## Asset and Mesh Review

When the user asks to review existing reusable content, the review may
include both logical assets and their underlying mesh representations.

The review should distinguish:

- reusable assets,
- mesh variants,
- duplicate or near-duplicate meshes,
- historical or superseded meshes,
- generated intermediate meshes,
- production-ready meshes,
- meshes currently referenced by the game,
- meshes that exist but appear unused,
- and cases where usage cannot yet be proven.

A mesh must not be judged only by filename.

Relevant mesh-quality evidence can include, when available:

- actual usage/reference evidence,
- source/provenance,
- vertex and triangle counts,
- dimensions and scale,
- topology quality,
- manifold/self-intersection information,
- UV/material readiness,
- visual appearance,
- silhouette quality,
- unnecessary geometric complexity,
- Roblox suitability,
- performance cost,
- collision suitability,
- and relation to other variants in the same family.

Open3D and Blender may be used during the technical/visual review phase
when geometry inspection is actually needed.

Do not permanently remove a mesh merely because it appears redundant.
First identify it as a removal/deprecation candidate and preserve the
evidence for user review.

When a logical asset or mesh family has more than three viable
variants, compare all viable candidates and propose the best three.

The Top 3 decision should be evidence-based and may consider:

1. visual quality,
2. geometry/topology quality,
3. Roblox runtime suitability,
4. performance efficiency,
5. distinctiveness relative to sibling variants,
6. production readiness,
7. current usage or integration quality.

If fewer than three viable variants exist, do not invent additional
ones.

Selection does not authorize deletion or world placement.

When the user requests review before world placement, the approved
sequence is:

discover
-> identify assets and meshes
-> group families/variants
-> identify duplicate/redundant candidates
-> technical QA
-> visual QA
-> rank/select candidates
-> present selections to user
-> wait for approval
-> verified backup
-> placement/distribution
-> runtime and visual verification
