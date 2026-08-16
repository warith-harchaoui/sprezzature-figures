# The Ralph loop

Ralph is Studio's editing copilot: you describe a change in plain language
("make the bars orange", "sort by value"), and instead of guessing at
pixels, Ralph turns that sentence into a small, typed edit to the chart's
*plan*, the same structured description (kind, bound columns, style
options) a human would fill in by clicking dropdowns. Nothing touches the
rendered image directly; every change re-renders the chart from that plan,
so the same plan always produces the same output. In `assisted`/`autopilot`
mode, Ralph then looks at the rendered result with a vision-language model,
a model trained to describe and judge images (a VLM, as distinct from the
text-only LLM that reads your message), and decides whether it needs
another pass, the same way you would glance at a chart before shipping it.

Say a user types "make the bars orange." The loop that follows is:

```
user message
  -> structured interpretation      (assistant.edit.propose_edit -> EditProposal)
  -> validation                     (core.validate_operation, per operation)
  -> plan modification              (ralph.apply.apply_operations)
  -> render                         (core.rendering.render_figure_to_project)
  -> inspection                     (ralph.critic.request_critique, assisted/autopilot only)
  -> structured critique            (VisualCritique)
  -> safe repair, maybe             (ralph.repair.apply_safe_repairs)
  -> re-render
```

"Make the bars orange" becomes an `EditProposal` naming a `StyleOptions`
change, gets checked against the rules below, is applied to the
`FigurePlan` as one typed `FigureOperation`
(`sprezzature_figures.studio.ralph.apply`), and the chart is re-rendered
from that updated plan, never patched in place.

## Modes (`RalphMode`)

| Mode | Applies the explicit request | Renders | Inspects (VLM) | Auto-repairs |
|---|---|---|---|---|
| `manual` | yes (auto-approved ops only) | yes | no | no |
| `assisted` | yes | yes | yes | one pass |
| `autopilot` | yes | yes | yes | up to `MAX_AUTO_REPAIRS = 2` passes |

## What Ralph may fix on its own (`policy.is_safe_repair`)

Cosmetic, meaning-preserving changes only: `StyleOptions.width`/`height`,
`font_scale`, `legend_position`, `label_rotation`, `show_grid`,
`show_labels`, `accessibility_mode`; `SetOutputSize`; adding an annotation.
Nothing here can change what the data says.

## What always needs your confirmation (`policy.requires_confirmation`)

`SetFigureKind`, `AddFilter`, `RemoveFilter`, `AggregateRows`,
`LimitCategories`, `CalculateColumn`, `BindColumn`, `UnbindColumn`: anything
that reshapes what's shown. This is checked **independent of** whatever the
model's own `EditProposal.requires_confirmation` flag says: a model that
forgets to flag a risky edit doesn't get to skip the check.

When an operation needs confirmation, it's returned in
`RalphResult.pending_confirmation` instead of being applied. The chat panel
shows an accept/cancel prompt; nothing in that list touches the plan until
you accept it.

## What Ralph never does

Modify a value, invent data, replace a missing value without an explicit
rule, silently hide a category, deceptively truncate an axis, present a
correlation as causation, or report a render as correct when it failed.
The last one is enforced structurally: `render_figure_to_project()` raises
if no output file is produced, so a failed render never reaches the
critique step in the first place: there's no "satisfied" verdict to give
it by mistake.

## Stopping criteria (autopilot)

`ralph.stopping.should_stop()` checks, in order:

1. verdict is `"satisfied"`
2. no `"high"`/`"critical"` severity issues remain
3. this round's issue signatures are identical to the previous round's
4. no remaining safe repair passes policy + validation
5. `MAX_AUTO_REPAIRS` (2) repair rounds already applied this session
6. the total critique score regressed vs. the previous round

**Simplification, documented rather than silently assumed**: an issue
"signature" is `category:severity:normalized_message`. The build plan also
mentions an "approximate zone," but `VisualIssue` has no bounding-box
field yet; that needs grounded VLM output, which isn't wired up.

## When the model fails

The two model-facing steps, interpreting the request and inspecting the render,
are wrapped so a live model failing never crashes the turn. If the text model
can't produce a valid `EditProposal` (empty or malformed JSON, a timeout, an
unreachable backend), the current figure still renders unchanged and the reason
is recorded in `RalphResult.notes`. If the vision model can't produce a valid
`VisualCritique`, the figure still renders and the loop stops with reason
`critique_unavailable`, again with an explanatory note. A figure is never
declared satisfied on the back of a failed inspection. This is what lets Studio
stay usable against a small or flaky local model: a dropped operation or a
missed critique degrades to a note, not an exception.

## Context sent to the vision model

Exactly: the rendered PNG, the figure kind, bound roles, title/subtitle,
canvas dimensions, a column-level statistical summary, the transformations
applied, and the previous critique if one exists
(`ralph.critic.critique_prompt`). Never the raw dataset; see
[DATA_PRIVACY.md](DATA_PRIVACY.md).
