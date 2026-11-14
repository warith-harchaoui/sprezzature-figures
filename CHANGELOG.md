# Changelog

## [Unreleased]

## [2.14.0] — 2026-11-14

### Changed

- **The colours come from [deraison.ai/colors](https://deraison.ai/colors/).**
  The site is the source of truth for every colour in the suite: three
  palettes with the same eleven names (Red, Orange, Yellow, Green,
  Turquoise, Blue, Purple, Pink, Brown, Black, Gray). `_style.py` carries a
  copy of the three (`_PALETTES`) and reads sprezzature-colors' copy of the
  site's files (`palette-<theme>.csv`, shipped since its 1.4.0) when it is
  installed. An older sprezzature-colors, which has only `palette.csv` and
  the colours of before, is not read: the built-in copy wins.
  - **corporate**: Apple's system colours of June 9, 2025. Red `#FF383C`,
    orange `#FF8D28`, turquoise `#00C3D0`, blue `#0088FF`, purple
    `#CB30E0`, brown `#AC7F5E`; the generators' hard-coded hues follow,
    light tints and dark-mode values included.
  - **academic**: the red is the Colour Universal Design (CUD) vermilion
    `#E73121`, pink `#FF8082`, brown `#804000`, gray `#84919E`.
  - **Teal and Mint** were two of Apple's earlier colours. Teal now reads
    as Turquoise and Mint as Green (the rule academic already followed).
    Where a figure used Mint beside Green, it takes another name: Pink for
    the flowering stage of `cycle`, Yellow for the Great Plains of
    `dependency-wheel`, Pink for France in `variwide`; `ridgeline`'s ramp
    anchor sits halfway between Turquoise and Green.
  - `qualitative_sequence` skips the neutrals by name, not by a list of
    hex codes that held for one palette only.
  - `SEMANTIC_KEYWORDS` names `Turquoise`, not `Teal`; the colour = meaning
    tables in the README, LISEZMOI and skill give names and send the reader
    to the site for the hex codes.
- The 169 example SVGs in `assets/svg-examples/` were rendered again: the
  145 that were the generator's exact output come from the new generators,
  the 24 that were not (hand-adjusted or from other data) had their palette
  codes replaced one for one, so nothing else in them moved.

### Added

- **The print theme**, `theme="print"` on every figure that takes a theme:
  the print palette of the site, checked for offset printing on coated
  paper, with the corporate typography (Roboto).
- `_style.THEMES`.

## [2.13.0] — 2026-11-13

### Fixed

- **`check` passes the demo.** `render` without `--data` stamps
  `data-demo="true"` on the SVG, and `check` no longer reports the demo's
  own captions there as leftovers (treemap, line and every kind with a demo
  subtitle were flagged).
- **`check` passes Sankey.** Node labels sit at their node's centre, which
  the data decides; they carry `data-placed="data"` and the baseline rule no
  longer reads two of them as a row that missed its line.
- **`recommend` names the chart a reader expects.** The goal is read off the
  columns when unstated, as the editor already did, and ties break toward
  familiar charts: monthly sales give `line`, a team comparison `bar`, a
  parent/name/value table `treemap`, where `ablation_matrix` came first.
- Waterfall keeps a description over a caller's data; line-multi wraps a
  long legend instead of running off the canvas; pie is no longer proposed
  for more than six slices.
- **Ralph Eyeball Loop in headless Chrome** with a throwaway profile, so it
  no longer fights the Chrome the user has open; the written PNG is the
  contract, not Chrome's exit code at shutdown.

### Changed

- **the editor uses the suite's one model, `qwen3-vl:8b`,** for text and
  vision alike, unless `BEST_LLM_TEXT` / `BEST_LLM_VISION` say otherwise; it
  used best-engine's defaults, `qwen3:8b` and `gemma3:12b`, which the rule in
  the hub's `docs/LLM_CHOICE.md` does not allow.
- **`--help` in 0.13 s, from 0.83 s.** The package's public names and the
  CLI load the catalogue on first use; a test keeps it that way.


## [2.12.0] — 2026-11-12

### Added

- **The agent skill ships inside the package.** `SKILL.md`, its
  `references/` and its trigger catalogue moved from the sprezzature hub into
  `sprezzature_figures/skill/`, and the wheel carries them, so one
  `pip install sprezzature-figures` brings all five surfaces: library, CLI
  (command-line interface, here built with Click), HTTP (HyperText Transfer
  Protocol) API (application programming interface, the FastAPI routes, with
  a Dockerfile and a `docker-compose.yml`), MCP (Model Context Protocol, the
  protocol through which AI agents call tools) and the skill. A new console
  script, `sprezzature-figures-skill`, and the same command as
  `sprezzature-figures skill`, report whether the copy an agent reads is in
  step with the package; `--install` copies it into `~/.claude/skills`
  (`--agent opencode` for `~/.opencode/skills`) and moves any previous copy
  to `skills-superseded/`; `--path` prints where pip put it.
  `sprezzature_figures.skill_path()` returns the folder. Importing the package
  does not load click. `tests/test_the_skill_ships_with_the_package.py`.

### Changed

- **the editor, reworked after driving it in a real browser.**
  - The style panel (text size, legend, grid, labels) did nothing: no
    generator takes those four options. It is replaced by an **Adjust**
    panel built from the options each chart type declares (title, subtitle,
    axis titles, palette, look, dark background, then the rest folded
    away). `editor.render_options.figure_kwargs` is now the one place a plan
    becomes `make_figure()` keywords, for the editor, Ralph's engine and the
    exported `reproduce.py`; `FigurePlan` gains an `options` field.
  - Ralph gains `set_figure_option`, which sets an option the current chart
    type declares, or `dark`. The edit prompt lists those options;
    `propose_edit` drops an option the type does not take, or a value
    outside its choices. Palette, look and dark background are safe repairs;
    a log scale, `vmin`, `vmax` and `baseline` need confirmation. A canvas
    size set by Ralph now reaches the render.
  - The canvas frames the SVG (Scalable Vector Graphics, the figure as text)
    itself, served by a `/editor-preview` route, instead of a PNG of it.
  - The export wrote a `.zip` on the server's disk and announced its path.
    A **Download** menu now hands the browser the SVG, a PNG, or the
    project archive.
  - A failed render no longer leaves the project's history pointing at an
    empty version (`IterationSlot`); undo, redo and the version counter keep
    working.
  - Default titles and axis titles come from the bound columns ("Revenue by
    country"), not from the chart type's name.
  - Sample data in one click, a five-row preview, one plain sentence per
    recommendation card, a manual chooser that starts from the chart on
    screen with its roles pre-filled, a message when the browser refuses a
    file, Ralph disabled until a chart exists, and a visible focus ring
    (it now lives in the first CSS layer, where Quasar's `no-outline` cannot
    beat it), a skip link, landmarks and a dark peer for the chat bubble.

### Documentation

- README and LISEZMOI describe the skill surface and the reworked Editor;
  they no longer say the skill lives only in the hub, that the history panel
  offers "compare" (`core.history.compare` exists, no button calls it), or
  that CI (continuous integration, the server that reruns the checks on
  every push) runs the type checks, the slow renders and the packaging test:
  CI runs ruff and the default suite on Python 3.12 and an install-and-import
  check on 3.10; the rest runs in `.githooks/pre-push`. The `--version`
  line no longer claims every console script answers it
  (`sprezzature-figures-skill` does not).
- `docs/editor/` follows the code: `SetFigureOption` and the confirmation
  rules in RALPH_LOOP.md, 16 operation kinds in LLM_SCHEMAS.md, the
  `options` field in FIGURE_PLAN.md, the preview route and `render_options`
  in ARCHITECTURE.md, the CI and the test counts in TESTING.md.
- `references/figure-catalog.md` no longer says the figures carry no script:
  by default (`mode="self-contained"`) each SVG ships a small fullscreen
  script.
- CODING.md and LANDSCAPE.md said 167 generators; there are 168.

### Fixed


- **`audit_figure`'s `rainbow-palette` no longer reads embedded images.** It
  looked for `jet`, `hsv` or `rainbow` anywhere in the SVG, base64 included,
  and the relief raster of a situation plate spelt `/HsV/`. The rule now
  reads the markup with every `data:` URI (Uniform Resource Identifier, here a `data:` address that carries a whole file inline) removed.

## [2.11.0] — 2026-11-09

### Added

- **`check_render` reports a near-miss alignment** (`baseline_near_miss`,
  warning). Labels of one size and weight, side by side, whose first
  baselines differ by more than 1.5 px but less than 0.9 of the font size were
  meant to share a row and do not: three cards whose middle subtitle fits on
  one line while its neighbours wrap to two put the middle title half a line
  low. Only first lines are compared (one `<text>` per line, or tspan lines in
  one `<text>`), and a pair is reported only with evidence of a row: the two
  blocks run to different numbers of lines, or one is aligned with a third
  label of the same role. Labels placed by their data (map cities, sankey
  nodes, packed circles) can still trip it, hence a warning.
  `tests/test_baseline_near_miss.py`.
- **`semantic_colors(labels, theme=...)` and `semantic_hue(label)`: colour =
  meaning.** A label naming a meaning, in English or French, gets the hue that
  carries it after deraison.ai/colors/academic (risque, erreur, danger to
  vermilion; confiance, fiable, sûr to blue; santé, croissance, gain to bluish
  green; ...); the rest keep the usual cycle minus the hues already taken. The
  table lives once in `scripts/_style.py` (`SEMANTIC_KEYWORDS`), and
  `cycle_hues(..., semantic=True)` uses it. Off by default: no figure's colours
  change. `tests/test_semantic_colors.py`.

### Fixed

- **Wrapping no longer moves a first line.** `flowchart`: every box of a
  left-to-right flow shares the tallest height (top to bottom, every box of a
  layer), its first line hangs from the top, and every layer's run of boxes is
  centred on one line, so a box outside any group no longer sits half a frame
  title above the boxes inside one. `treemap`: the leaves of one squarified
  strip share the smallest font any of them needed and the block height of the
  longest name, values included. `timeline`: every card shares the tallest
  card's height, so an above-spine card whose blurb wraps no longer lifts its
  year and name. `fishbone`: a wrapped cause keeps its first line on the twig.
  `bullet`: the "Bands:" lead-in shares the baseline of its legend entries.

## [2.10.1] — 2026-11-09

### Fixed

- **`flowchart`.** A non-breaking space (U+00A0) now holds a formula together
  (`_textfit.split_words`, used by `wrap_to_width`). A label of several lines
  on a returning arrow sits beside its lane instead of on it, so the arrow no
  longer runs through the text and the halo no longer reaches the boxes. Two
  groups in the same layers keep one order and their frames are pushed apart.
  A flow too long for its canvas logs a warning naming `direction="TB"`.
- **`gantt`.** The axis opens for a negative start; long task names widen the
  name column up to 40 % of the canvas, then wrap between words.
- **`line-multi`.** The plot moves right for a long y tick label, clear of the
  turned y title. New options `left_margin` and `right_margin`.
- **`facet`.** The per-panel change is no longer printed bare over caller data.
  New option `show_change`; set to `True` over caller data it reads
  "+379 first to last".

### Added

- **`check_render`.** Two rules: `axis_title_overlap` (a straight label on a
  turned axis title) and `frames_overlap` (two flowchart group frames).

## [2.10.0] — 2026-11-08

### Added

- **`flowchart`, a labelled box-and-arrow flow (168th kind).** One row per
  arrow (`source`, `target`, optional `label`, `source_group`,
  `target_group`, `back`, `dashed`). Boxes sit in layers, left to right or
  top to bottom (`direction="TB"`); an arrow that skips a layer passes
  through relay points between boxes; a returning arrow runs in its own
  lane; groups get a named frame. Box text wraps between words and never
  inside one (a typed `\n` forces a break), and the type shrinks before a
  word is ever cut. Every word drawn comes from the rows.
  `tests/test_flowchart.py`.
- **`check_render(kind=...)` reports a kind's demo text in a caller's
  render** (`demo_text`), from `make_figure.demo_texts(kind)`: the strings of
  its `DEMO_DATA`, its demo headlines and a generator's own `DEMO_TEXT`,
  minus the method's vocabulary a generator declares in `METHOD_TEXT`
  ("upper control limit", "collider · do not adjust"). `allowed_text` lets
  a caller whose data really holds a demo word say so. `sprezzature-figures
  check --kind <kind>` on the command line.
- **`check_render` reports two labels that touch** (`labels_touch`): an
  end-anchored y tick running into a centred x tick at the origin corner
  printed "-80" for "-8" and "0". Lines of one stacked list (same anchor,
  same size) are left out. It found four committed examples touching, all
  fixed (control-chart, forecast-fan, funnel-area, radial-bar).
- **`_svg.fmt_tick(v, step)`**: a tick takes the decimals of its step.
- **`gaussian-process --fit false` draws the data alone**: rows carrying only
  `y`, points joined in order, no posterior; the figure a report shows before
  any model.
- **`sprezzature-colors` is a dependency.** The accessibility levels other than
  `universal` are computed by it, and as a separate install they silently drew
  the universal palette.
- **`loss-curve` with a single curve** no longer prints "at the last epoch
  the two are 0 apart": the gap line and its sentence in the description
  need two curves.
- **`gaussian-process` draws a posterior it is given.** Rows carrying
  `mean` and `sd` on an `x` grid are drawn as given, with no fit and no
  invented sample draws; rows carrying `y` are the observations (`y` may now
  be empty on a grid row). When the grid leaves the observed range, its
  edges are ruled and the outside labelled "extrapolation". `x_label` and
  `y_label` title the axes; past 60 observations the dots shrink and drop
  their hover bubbles. The demo renders byte for byte as before.
  `tests/test_a_gaussian_process_can_be_given.py`.
- **`AXIS_ROLES`**: a generator says which role each axis and the legend
  draw (`line-multi`, `scatter`), and make_figure titles them after the
  caller's columns.

### Removed

- **Mermaid and `mmdc`, in favour of `flowchart`.** `render_diagram.py` and
  the Ralph loop now read TikZ and SVG (and the loop HTML): the Mermaid kind,
  its `.mmd` / `.mermaid` suffixes, the content sniffing, the theme directive
  and the `mmdc` tool entry are gone, along with every proposal of them in the
  docs. A `.mmd` or `.mermaid` file is refused with exit code 2 and one
  sentence naming `sprezzature-figures render flowchart`; no parser reads the
  old language. A "mermaid diagram" request routes to `flowchart` from one row
  of TRIGGERS.md. `--install-tools` no longer installs anything: its only
  automatic install was `mmdc`, so it now prints the command for each missing
  tool. `generate_flow_diagram` counts as covered by `flowchart` in
  COVERAGE.md, and the sequence diagram of `docs/editor/ARCHITECTURE.md` is a
  `flowchart` figure. `tests/test_no_mermaid.py`.

### Fixed

- **The Ralph Eyeball Loop, installed, writes under the working directory,
  really.** The 2.9.2 check took any `pyproject.toml` beside `scripts/` for a
  clone, and `dash-bootstrap-components` drops one at the top of site-packages.
  A clone is now recognised by the project name in it.
- **`redraw` accepts a kind copied with its category** (`bar (Comparison)`, the
  prompt's own line); it failed even with `--kind`.
- **Accessibility levels reach an installed `sprezzature-colors`.** Only a
  checkout or a skill folder was searched, so after `pip install
  sprezzature-colors` every level still drew the universal palette.
- **The MCP server announces its version as a version.** fastapi-mcp 0.4 passes
  the description in that slot; it now goes to `instructions`.
- **Four options the catalogue advertised did nothing on a figure.**
  `forest --subtitle` and `cycle --unit` were dropped on the demo, and
  `flowchart --direction` is now declared as the switch it is (`LR`, `TB`)
  rather than free text. `causal-dag`'s `treatment` and `outcome` name nodes
  of the given graph since they default to it; the options probe knows them
  as selectors.

- **Demo text over caller data**, found by a new behavioural test that
  renders every kind from its demo rows renamed to tokens
  (`tests/test_demo_leftovers.py`, slow): 96 of 168 kinds were clean
  before, 147 are now; the 21 left are listed with their reason as strict
  expected failures, so the list only shrinks.
  - At the door, for every kind: an axis or legend title the caller left
    unset takes the name of the column it draws, guessed only from a
    declared `AXIS_ROLES` or the plain "one category, one number" shape
    (the old guess titled a line chart's x axis after its series column);
    every other caption whose default is demo text is emptied.
  - `tree`: title, subtitle, description, column headers (`level_names`)
    and branch colours follow the data; a caller tree no longer reads
    "Supervised learning..." under FIELD / FAMILY / TASK.
  - `cycle`: draws the caller's phases (it ignored `data` and drew the
    winter-wheat year); `unit` names what a duration counts.
  - `timeline`: eras, axis span and tick step come from the rows; `planned`
    is a column; the "Flown mission" legend and the Mars note are the
    demo's only.
  - `forest`: headers, subtitle, axis, "favours" notes and the axis span
    come from the data or from options (`estimate_name`, `left_label`,
    `right_label`, `axis_title`); a recomputed diamond is named
    "inverse-variance", which is what it computes.
  - `network`, `causal-dag`, `fishbone`, `venn`, `voronoi`, `radial-bar`,
    `permutation-importance`, `scatter`: demo descriptions, defaults,
    units, tooltips and metric names stay with the demo. `causal-dag` no
    longer fails on a graph without the demo's treatment node; `bubble`,
    `radial-tree` and `voronoi` no longer crash on renamed categories.
  - `errorbar`, `strip`: ticks and values printed with `:.0f` read 0.93 as
    "1"; they now use `fmt_tick`.
  - `line-multi`: negative values were drawn below a 0-anchored axis; the
    axis now spans them, and the lowest label lifts off the origin corner.
    A wide continuous x axis gets round ticks.
  - `scatter`: eight hues before any repeat; a long title shrinks to fit.
  All demo renders are byte-identical except those whose layout the new
  rule fixed or whose tooltips now name their axes (scatter, radial-bar,
  control-chart, forecast-fan, funnel-area); those committed examples and
  the new flowchart's are regenerated.

## [2.9.2] — 2026-11-05

### Fixed

- **The Ralph Eyeball Loop, run from the wheel, writes under the working
  directory.** `python -m sprezzature_figures_scripts.ralph_eyeball_loop`
  put its PNGs, assessments and critique ledger in
  `<parent of the script>/.private/ralph-loop/`, which for an installed
  package is `site-packages/`. A clone (recognised by its `pyproject.toml`)
  still writes into its own `.private/`; anything else writes into the
  current directory's. `tests/test_the_ralph_loop_writes_beside_the_user.py`
  imports the script laid out as the wheel lays it out.

### Docs

- README and LISEZMOI say the loop also runs from the wheel, as
  `python -m sprezzature_figures_scripts.ralph_eyeball_loop`.
- README and LISEZMOI say where the loop writes, clone or wheel.
  `TRIGGERS.md` gives the `python -m sprezzature_figures_scripts.<name>`
  form of the six scripts, which the wheel carries.
- The figure "How it works" said PNG and PDF went through the renderer that
  rasterises TikZ and Mermaid. They come from the same SVG through resvg,
  in-process; JPG and HTML too. Spec edited, both figures redrawn.
- `audit_figure.py`'s docstring said it needs PyYAML and reads SVG with
  `xml.etree`. It is stdlib only and reads SVG with regular expressions.
- `PAYSAGE.md` gave web embeddability a loading of −0,308 where
  `LANDSCAPE.md` and the source (−0.3085) give −0.309.

## [2.9.1] — 2026-11-05

### Fixed

- **`sprezzature-figures`, `make-figure` and `python -m sprezzature_figures`
  answer `-V` and `--version`.** The front-door group had no version option
  at all; `sprezzature-figures` knew `--version` but not `-V`. All four console
  scripts now print `<prog>, version <v>` from the installed metadata, as
  `sprezzature-figures-mcp` already did. No sub-command uses either spelling.
- **`explain_model` has one default for how many rows it explains: 500.**
  `--n-explain` and the SHAP (SHapley Additive exPlanations, how much each input pushed one prediction up or down) / Shapash paths defaulted to 500, while
  `run_lime` fell back to 10 when `ctx` carried no `n_explain`. The command
  line always passes one, so the 10 was reached only by a library caller.
  `DEFAULT_N_EXPLAIN` now feeds the flag and every engine; a direct
  `run_lime` call without `n_explain` explains up to 500 rows, as the CLI
  always has.

## [2.9.0] — 2026-11-05

### Fixed

- **A render without `--out` no longer writes into the checkout or into
  `site-packages/`.** `make_figure()` with no `out=` and
  `sprezzature-figures render <kind>` with no `--out` reached each
  generator's own fallback, `assets/svg-examples/<kind>.svg` one level above
  `scripts/`: in a checkout that rewrote the committed example, installed it
  wrote under the interpreter. Both now write `<kind>.svg` in the current
  directory, named after the canonical kind. Running a generator script
  directly keeps its example path, which is how the examples are regenerated.
  Guarded by `tests/test_render_without_out_stays_in_cwd.py`, which also
  checks the committed `bar.svg` is not touched.

### Changed — dependencies

- `shapely` and `pyproj` leave the base dependencies and
  `scripts/requirements-dataviz.txt`. They were declared for
  `make_situation_map.py`, which moved to sprezzature-maps; nothing in the
  package, the scripts, the tools or the tests imports either one. 32 base
  dependencies become 31.
- `pydot>=3.0.1` is declared. `causal_estimate.py --dag x.dot` reads DOT
  through `networkx.nx_pydot`, and pydot only arrived because dowhy pulls
  causal-learn, which pulls it.
- The packaging test asks the installed `sprezzature-figures-mcp` for
  `--help` too, beside the three other console scripts.

### Docs

- README / LISEZMOI: `python -m sprezzature_figures` named beside the two
  console scripts; where a render goes without `--out`; `embed_fonts=False`; the role names come from `describe`, not from
  FIGURES.md, which does not list them.
- EXAMPLES.md / EXEMPLES.md: `list_kinds` imported from the package and shown with
  its real first names; the scatter roles pointed at `describe scatter`.
- The extras that no longer exist were still named in the comments of
  `requirements.txt`, `environment.yaml` and the `Dockerfile`; the dead
  commented `-e .` lines are gone. `docs/editor/` gets the editor's real
  import formats and today's test counts. French files take their
  non-breaking spaces.

## 2.8.0 (2026-11-04): a figure can now wear the host page's clothes, and click everywhere

### Added

- `python -m sprezzature_figures` runs the click group. `python -m sprezzature_figures.make_figure KIND` answered through the argparse `main` that left with the front door, and would otherwise have done nothing at all; two slow tests that used it now call `render` through the new entry point.

### Changed — one `pip install`

**Everything this package does now installs with it.** 8 extras became
**one**, and it is not a feature: `[dev]` is the test toolchain.

  The data side (networkx, scikit-learn, pandas, shapely, pyproj, pyyaml),
  the editor (the NiceGUI app and the Ralph copilot), the causal stack
  (dowhy, econml), the explainability stack (shap, shapash, timeshap, lime) and
  both surfaces all arrive with the package. This is the largest fold in the
  suite and the one most worth stating: `pip install sprezzature-figures` was
  six dependencies and could not read a spreadsheet, profile a column or draw a
  positioning map.

Measured across the suite before touching anything: **59 extras over eleven
repositories**, and **six bricks whose base was a single dependency** — so
`pip install <brick>` installed almost nothing and did almost nothing, and
choosing the right extra was a thing a reader had to know *before* the package
could do its job. Here the base goes from **6** to **32**
dependencies.

All eleven unions were dry-run resolved in a clean venv before any manifest was
edited, so this is a measured feasibility and not an optimistic one.

### Changed

**Click parses every command line of the package; argparse is gone from it.**

- `sprezzature-figures-mcp` is a Click command. Same flags (`--host`, `--port`),
  same defaults (127.0.0.1 and 8000), same environment variables
  (`SPREZZATURE_FIGURES_HOST`, `SPREZZATURE_FIGURES_PORT`), same exit code 2 on a
  usage error, and it gains `-V/--version`. `main(argv)` now returns the exit code
  in both branches of the import guard.
- The argparse `make_figure.main` and its five sub-command parsers are deleted.
  No console script had pointed at them since 2026-10-25; they survived only for
  the parity tests. Those tests now ask the Click group directly, and the
  comparison of the two parsers became one question asked of the whole
  catalogue: `render <kind> --help` names every option of every generator.
  An unknown flag is answered with `sprezzature-figures describe <kind>`, the
  spelling that exists.
- The Docker image serves the MCP endpoint. Its `CMD` was
  `uvicorn sprezzature_figures.api:app`, which never mounts `/mcp`; it is now
  `sprezzature-figures-mcp --host 0.0.0.0 --port 8000`, the same FastAPI app with
  `/mcp` beside `/health`, `/kinds` and `/render`, so one container on one port
  answers both. `docker-compose.yml` spells the command out on the `api` service.
- A guard, `tests/test_console_scripts_are_click.py`: every console script
  answers `--help` with Click's `Usage:`, and no module under
  `sprezzature_figures/` imports argparse. The standalone generator scripts in
  `scripts/` keep their argparse parsers: they are not console scripts and run
  from a downloaded skill with the standard library alone.

### Fixed — the places that encoded the extras

Install lines, error messages, docstrings, the `Dockerfile`, the CI workflow and
the README/LISEZMOI install sections all named extras that no longer exist. pip
treats an unknown extra as a **warning and exits 0**, so none of these would
have failed loudly: they would have quietly installed nothing.

The hub's `test_no_document_promises_an_extra_that_does_not_exist` found the
cross-repository ones — a document in one brick naming another brick's extra —
which no per-repository pass would have caught.

Everything here comes from one real embedding: notes-helper draws the figures of a
meeting report, and the two it had reimplemented (a speaking-time ring, a who-cuts-whom
matrix) now come from this catalogue instead. What it needed to make that possible says
more about the gap between "a figure" and "a figure inside a document" than any amount
of design thinking would have.

### Added

- **`colors=` on `speaking_time`, `interruption-matrix` and `line-multi`** (as
  `series_colors=` on the last, matching its own vocabulary): the host's
  `{name: "#RRGGBB"}` mapping. A page that already gives each speaker a colour, in its
  transcript or its legend, needs the figure to use those hues; different ones make the
  figure read as a picture borrowed from elsewhere. A name absent from the mapping keeps
  its place on the house wheel, and the accessibility levelling still runs over the result.
- **`embed_fonts=` on `make_figure`**, handled there like `dark=` rather than by each
  generator. A figure carries its own 430 kB of base64 Roboto so it renders identically
  anywhere, which is right when it travels alone and wrong when six of them are inlined
  into one page that already serves those faces: 2.5 MB of a document whose text is
  already in the right font. The block is rebuilt from `fonts` and removed by equality,
  never matched by pattern.
- **`description=` on `speaking_time` and `interruption-matrix`**, and `centre_label=` on
  the first: a screen reader should hear the figure in the language of the page it sits
  in, and the caption inside a ring should not say "total time" in the middle of a French
  report. `cutter_summary` / `target_summary` do the same for the matrix's bilan line.
- **`text_width` is public.** It is the calibrated advance table the generators lay out
  with and `check_render` measures against. A host drawing its own figures beside these
  ones has to reserve room the same way: measuring differently from the thing that checks
  you is exactly how a label ends up clipped while every check passes.
- **The width table knows what an emoji is.** Anything outside the Latin table was counted
  as 0.52 em, half a letter, so a caption built from 🔪 and 🥩 measured ~25 % short, the
  fitter reported room to spare, and the line ran off both edges. Emoji and ideographs are
  measured in a square cell, arrows and dingbats a little narrower, and the variation
  selectors that follow most emoji take no advance at all.

### Fixed

- **`check_render` reads the viewBox origin.** A viewBox may start anywhere, not only at
  `0 0`; comparing labels against `0..width` called every label on a left-shifted canvas
  clipped while it was plainly visible. `speaking_time` now uses exactly that freedom.
- **`speaking_time` grows its canvas rather than cutting long names.** A participant
  called "Général Dominique Trinquand" had the stem of their capital rendered off the
  canvas, 13 px past where the estimate said it ended. The frame now widens around the
  drawing, coordinates untouched, with clearance proportional to the label's own measured
  width, because that is how the estimator's error behaves.
- **`speaking_time` stopped printing the demo's chrome over caller data.** Its subtitle
  ("a 40-minute round table") was hardcoded inside the builder rather than being a
  parameter, so `make_figure`'s own `_without_demo_chrome` could not blank it: every
  caller got a sentence about a forty-minute round table printed over its own recording,
  whatever its real duration. Its accessible description had the same problem and was
  half-translated mid-sentence; `interruption-matrix` carried the same bilingual text and
  an unconditional "Illustrative data."

### Tried and rejected

- **A safety margin in `check_render`.** A label whose estimated box merely approaches the
  edge can still be clipped, so a margin seemed right: flat (16 px), then proportional
  (8 % of the label's width). Both accused 114 of the 343 committed examples, whose chrome
  legitimately sits flush against the edge. A check that cries wolf on a third of the
  catalogue is worse than one that misses a graze, so the rule stayed "outside the canvas"
  and the clearance is reserved by the generator laying the figure out, which knows what
  it is drawing. The reasoning is kept in the source so it is not re-tried blind.

### Docs

The documentation now says what the code does today. Every command, route and
count below was checked against the code or recounted from it.

- **Command line.** The READMEs, `EXAMPLES.md`/`EXEMPLES.md`, `FIGURES.md`,
  `TRIGGERS.md`, `docs/editor/GENERATOR_CONTRACT.md` and `LANDSCAPE.md`/`PAYSAGE.md`
  still used the argparse syntax removed on 2026-10-25 (`make-figure --list`,
  `make-figure bar --out …`, `make-figure sankey --describe`). `make-figure` is the
  same Click group as `sprezzature-figures`, so these are now `list`, `render <kind>`
  and `describe <kind>`. Three examples that failed when run were fixed: a sankey with
  three stage names for a four-stage demo, a heatmap given `--language`, which it does
  not accept, and a wordcloud fed roles it does not have.
- **Extras.** `[editor]`, `[cli]`, `[local]` and `[dataviz]` were still named in the
  docs and in several docstrings and error messages. Install is one `pip install
  sprezzature-figures`; `[dev]` is the test toolchain.
- **CI.** The READMEs and `docs/editor/TESTING.md` described macOS, Ubuntu and Windows
  runners. CI runs on Ubuntu only: the suite on 3.12 and an install check on 3.10.
- **Counts.** The catalogue has 68 categories, not 52. The README's category table
  listed `choropleth` and `situation_map`, which live in sprezzature-maps, and missed 43
  kinds; it is now built from `figures.json`. The READMEs now say which number they
  mean: 167 in the catalogue, 160 in the web gallery.
- **TRIGGERS.md.** The generalisation comes first and routes on the closed vocabulary
  (four request shapes, nine goals, the catalogue). A table lists every tool and the
  request it answers, and the surface table gives the CLI name, MCP tool name
  (`operation_id`) and HTTP route for each job. `health` was missing. The five glyph
  maps were missing from the per-kind tables, and the section headings claimed goals
  that the scorer does not apply; each row now shows the goal computed from
  `scoring._GOAL_CATEGORY_KEYWORDS`.
- **Undocumented until now.** The README covers the five surfaces, all public names
  (`as_rows`, `to_dark`, `text_width`, `validate_figure_input`), the eight MCP tools,
  `sprezzature-figures-mcp --host/--port`, Docker Compose and its profiles, the Ralph
  Eyeball Loop and the other repository scripts, and the three-Roboto font rule.
- **Editor docs.** The recommendation engine, its cards, the history panel, the export
  bundle and the execution of `FigurePlan.transformations` were described as missing.
  All are built. The architecture tree, the test counts and the deferred items of ROADMAP.md
  were brought up to date. `STATUS.md` keeps its history, under a dated note.


## 2.7.0 (2026-10-16): the wheel carries every face the module offers

**Roboto Serif is back in the wheel, and the wheel grows 3.4 MB to 11.4 MB for
it.** That is the whole release: a typography decision reversing a packaging
one, plus the test that should have been there to make the disagreement
impossible.

2.6.0 narrowed the font package-data to drop Roboto Serif -- 12.2 MB of 18.6
uncompressed, for a family neither theme sets. The saving was real and the
reasoning was sound. What made it a defect is that `fonts.py` went on offering
`serif` and `serif_italic` anyway, so the module advertised ten faces while the
wheel carried eight, and **nothing in this repository could tell**: the source
tree's `assets/fonts/` holds every face regardless of what a build contains, so
every font path passes locally by construction.

It surfaced downstream instead. `sprezzature-maps` set its density plate in the
serif; its CI installs from the wheel rather than the checkout, and answered
with a bare `FileNotFoundError: RobotoSerif-Variable.woff2` -- a filename,
naming neither the face that asked for it nor the fact that the absence was a
decision. Hours went into a packaging bug that was a packaging *choice*.

Shipping the face is the right resolution rather than the convenient one. The
suite's typography is three Roboto -- sans, serif, mono -- and a rule that
holds only where the source tree is checked out is not a rule; `SERIF_STACK` is
public API, and in an installed copy it was quietly resolving to Georgia.
`OFL-RobotoSerif.txt` ships with it: a licence travels with the font it covers.

### Fixed

- **`web_font_faces_css()` linked faces the install did not have.** Its default
  was the entire face table, while Editor mounts `fonts.FONTS_DIR` and serves
  whatever is actually there -- so under the 2.6.0 wheel every page requested
  four Roboto Serif files that were not present. Nothing broke, which is why it
  went unseen: a dead `@font-face` source is a 404 the browser swallows on its
  way to the next family in the stack. The default now reads the directory, so
  the rules and the files are the same set in a damaged install too. (Editor is
  still work in progress; this was cheap rather than urgent.)

- **A missing face now says which face, and what to do.**
  `fonts.MissingFaceError` subclasses `FileNotFoundError`, so existing handlers
  keep working, but the message names the face key that asked rather than only
  the file it wanted. Since the wheel now carries every face offered, reaching
  it means a damaged install, and the text says so instead of leaving the
  reader to guess between accident and intent.

- **Two comments that had drifted into falsehood.** `fonts.py` said Roboto
  Serif "ships for the web app" while pyproject excluded it, and pyproject said
  "the web app self-hosts its own copy" -- two web apps confused for one. The
  sprezzature.ai site does self-host its own `web/fonts/` and was never
  affected; the *Editor* app lives in this package and mounts `FONTS_DIR`.
  `available_faces()` promised "normally all six" for a table of ten.

### Added

- **`fonts.OFFERED_FACES`** -- every face key the module offers, which the
  wheel must carry in full.

- **`tests/test_the_package_serves_only_fonts_it_ships.py`** (9 tests) reads the
  font globs out of `pyproject.toml` and fails if any offered face would be
  left out of a build. It reads the build configuration rather than the
  directory on purpose: the directory is precisely what cannot see the
  difference. Verified in both directions -- reintroducing the 2.6.0 default
  turns it red, restoring it turns it green.

  It also pins the two decisions themselves, so that reversing either is a
  deliberate edit rather than a glob quietly narrowed: the serif ships, and
  every bundled family ships its licence.

- **`tests/test_packaging.py::test_installed_fonts_match_what_the_module_offers`**
  asks a real wheel installed in a fresh venv the same questions, including
  that the serif can actually be embedded. Marked `packaging`, so CI runs it in
  the job that builds and installs; also verified to fail against the 2.6.0
  behaviour before the fix.

## 2.6.0 (2026-10-15): forty figures, and the probe that found what the catalogue only claimed

2.5.0 was prepared in this repository and never reached PyPI, so 2.6.0 is the
first release carrying it. Everything in the 2.5.0 section below ships here.

The catalogue goes from **127 kinds to 167**, additively: nothing was removed,
nothing was renamed. But the headline of this release is not the count. It is
that writing forty figures in a row produced a probe, and the probe found that
a large part of the *existing* catalogue had been advertising options it
silently ignored.

### Added

- **Forty new kinds.** By family:

  - *Distributions and fields* — `hist2d`, `contour`, `tricontour`,
    `trisurface`, `voxels`, `quiver3d`, `line3d`.
  - *Time and sequence* — `acf`, `seasonal-decomposition`, `forecast-fan`,
    `control-chart`, `ohlc`, `bump`, `stem`, `eventplot`, `sparkline`,
    `dual-axis`.
  - *Model diagnostics* — `learning-curve`, `loss-curve`, `validation-curve`,
    `silhouette`, `permutation-importance`, `pdp-ice`, `shap-waterfall`,
    `shap-beeswarm`, `causal-dag`.
  - *Data quality and cohorts* — `missing-matrix`, `cohort-retention`,
    `pointplot`.
  - *Business shapes* — `pie`, `funnel-area`, `progress`, `fishbone`, `table`.
  - *Layout* — `facet`, the small-multiples frame that was the catalogue's
    largest single gap.
  - *Thematic maps* — `map-bars`, `map-bubble`, `map-pie`, `map-flow`,
    `map-tilegrid`. These draw quantities **on** a geography; the projected
    cartography proper stays in `sprezzature-maps`.

  `map-bars` and `map-pie` are flagged in the catalogue as near-duplicates --
  same category, same columns -- with the sentence that separates them
  written down rather than left to the reader: one plots magnitudes free to
  move independently, compared by height off a shared baseline; the other
  plots parts of one whole, compared by angle, a weaker channel paid for the
  one thing bars cannot say -- that the parts are exhaustive.

- **A DataFrame is enough.** `make_figure` took `list[dict]`, which nobody has
  on hand: you have a pandas or polars DataFrame, an Arrow table, a dict of
  columns. `frames.as_rows` normalises all of them at the single point
  everything passes through, so all 167 figures gained it at once. Recognition
  is by offered method (`to_dicts`, `to_pylist`, `to_dict(orient=...)`):
  nothing is imported, no dependency is added, and anyone holding none of
  those libraries pays nothing. Gaps come out as `None` whatever they were
  called, and dates become ISO (International Organization for Standardization, whose 8601 format writes a date as 2026-11-12) labels -- an axis prints and sorts, it does not
  want a `Timestamp`.

  With the refusal that belongs to it: a `NaN` turned `None` used to crash
  deep inside a generator on `float()`. `validate_figure_input` now refuses it
  at the door, naming the column and the row, and pointing anyone who wants to
  *see* their gaps at `missing-matrix`. Roles whose absence **is** the data --
  a tree's root, a forecast's future rows, the unswept components of a
  spectrogram -- declare `tolerates_gaps` and pass.

- **A trigger phrase for every one of the 167 figures.** The nine intents
  covered ordinary demand but named only about forty shapes; for the rest
  `TRIGGERS.md` deferred to `list_kinds` with a handful of examples, so an
  agent could not route "the wind rose", "the forest plot", "where are the
  holes in this dataset". The table gives, per figure, what a user actually
  says in English and in French, grouped by routing family rather than by
  `FIGURES.md`'s sixty-eight categories. Coverage is exact -- the script that
  composes the table checks it against `list_kinds()`.

### Fixed

- **74 of 133 figures advertised a `title` they ignored.** A probe written to
  check six new figures was run across the whole catalogue: render every kind
  with a sentinel in each of its text options, then check the sentinel comes
  back out of the SVG. `make-figure alluvial --title "My title"` did nothing,
  silently, and `--help` offered it anyway.

  Two shapes behind it, one correction. Either the title was *computed from
  the data* -- a good reflex, `bullet` composing "Three of five targets met in
  Q3" so the hook cannot drift from what is drawn -- but the parameter was
  ignored rather than used as the override; or `build_svg` had no `title`
  parameter at all and the wrapper kept its own "for signature parity", which
  several docstrings said out loud. `build_svg` now takes
  `title: Optional[str] = None`, the computed hook becomes its default, and
  the wrapper passes it through. Nothing changes for anyone not passing one.
  Thirty figures were rewired in the first pass and eighteen more after it,
  and the probe is now a test, so the next one fails in CI rather than in a
  user's figure.

- **Nothing visible that is not a parameter.** The six figures added in one
  sitting still had prose composed in code -- `pie`'s footer line, `hist2d`'s
  legend title and empty-cell name, `contour`'s summary, `sparkline`'s three
  column headings, `dual-axis`'s caveat and Pearson *r*. Each is now an
  option where `None` composes the default sentence and a string replaces it,
  so the catalogue publishes them and they arrive free in both CLIs and the
  API. The lesson arrived immediately: the first write of `hist2d`'s
  `legend_title` did not take, the replacement failed silently, and the option
  was advertised everywhere while doing nothing. A declared option that never
  reaches the SVG is exactly as false as a literal, and harder to see.

- **The geometry linter was wrong far more often than the figures were.**
  Three stacked errors produced 116 overlaps across 162 figures, of which two
  were real. `dominant-baseline` was not read, though 422 texts in the
  catalogue carry one, so all of them were placed a third of a line too high.
  A string's ink is not a fraction of its size -- "63 %" at 150 px has nothing
  below the baseline, and charging it 0.2 em of descender invented thirty
  pixels of ink never drawn. A label written twice in the same place is one
  label, not a collision. And `text_invisible_on_background` compared ink to
  *canvas*: a white "74" inside a dark bar is white-on-white from there, and
  perfectly legible in fact -- the rule was wrong 27 times out of 27. It now
  asks what lies **under** the label, replaying the paint in document order,
  and abstains when the markup does not say. Two overlaps and five overflows
  remain across the whole catalogue, all looked at by eye, all real.

- **`_textfit` measured monospace as if it were proportional**, and so cut
  text it had just declared would fit.

### Changed

- `_project3d` carries one camera rather than seven, the Equal Earth
  projection is written once rather than per world map, and `fmt_measured`
  exists because `fmt_number` is built for a tick and a measurement is not a
  tick.
- Every mention of a third-party plotting library is gone from anything that
  neither measures nor forbids one. The examples folder now passes the
  project's own linter, and holds only what a generator can write.


## 2.5.0 (2026-10-13): every figure's own options, on the command line and over HTTP

Each of the 127 generators is a function with a signature — `make_bar(data, *,
out, title, subtitle, width, height, mode, accessibility, language, x_label,
y_label, theme)`. A library caller could read it and pass what it wanted. A
command-line caller could pass `--title`, and nothing else. An HTTP caller
could send an `options` object that was never checked, so a misspelt key was
dropped on the way in and the figure came back looking as though it had
ignored the request.

That surface is now derived from the generators themselves and published
through all three doors.

### Added

- **`options_schema` for all 127 kinds, read off the live signatures.** The
  catalogue builder introspects each `make_<kind>` and its numpydoc docstring
  into a type, a default, the allowed values and a line of help, and freezes
  the result in `catalog/figures.json` — 847 options, where there had been
  none. Deriving rather than hand-writing is what keeps it true: a generator
  that gains a parameter publishes it on the next build, and a new test fails
  when the frozen copy and the live signature disagree.
- **A flag per option, on both command lines.** `make-figure sankey --help`
  now documents `--volume-unit` and `--stage-names`; `make-figure bar --help`
  documents `--width` and `--x-label`. The flags exist only for the figures
  that accept them, the way `scripts/_render.py` has always grown a flag from
  a `build_svg` parameter. `--set name=value` is the scriptable spelling that
  reaches any option without one.
- **`make-figure <kind> --describe`** (and `sprezzature-figures describe
  <kind>`): what the figure needs — its data roles — then what it accepts,
  with every default. `--json` prints the catalogue entry instead.
- **`GET /kinds/{kind}/options`**, the HTTP half of the same answer, and an
  MCP tool (`list_kind_options`) with it.
- **`redraw`, `recommend`, `check` and `list` as `make-figure` sub-commands.**
  They had routes in the HTTP API and commands in the Click twin, and no
  spelling at all in the always-installed command: what you could do depended
  on which door you came through. The behaviour moved into
  `sprezzature_figures.actions`, called by both command lines, so the two
  cannot answer differently. A test pins the route-to-command map.
- **`dark` over HTTP.** It existed as `--dark` and as a `make_figure()`
  keyword; the API could not ask for it.
- **`--json` on `--list`**, for a caller that is not a person.

### Fixed

- **`make-figure <kind>` drew the demo figure untitled.** The command passed
  `title=""` whether or not you asked for a title, and handed the generator
  its own `DEMO_DATA` — which the dispatcher cannot tell from caller data, so
  it suppressed the demo chrome as a precaution. Between them, the reference
  render came out with no headline and no subtitle, and no flag could bring
  them back. An omitted `--title` now means omitted, and a demo render asks
  for the figure's own rows by passing none.
- **The demo *title* survived onto your data.** The dispatcher already
  suppressed the demo subtitle and axis titles when rendering somebody's own
  rows, on the grounds that chrome written for other numbers is false. The
  title — the most quoted line on the figure — was not in that list.
- **An option the figure does not accept is now an error.** Unknown keywords
  were dropped silently (right for a library caller forwarding a bundle of
  shared chrome kwargs; wrong for someone who typed one). The CLI and the API
  name the nearest real option and list the rest; the API answers 422.
- **`make_gauge` ignored `subtitle` and `make_waterfall` ignored
  `accessibility`.** Both parameters existed one level down in `build_svg`, so
  a caller asking every figure for a monochrome palette got the universal one
  from the waterfall, and nothing said so.
- **Canvas defaults in the catalogue were a flat 900x600 for every kind**,
  which was true of almost none of them. They are read off the generator now
  (`bar` is 745x505).

## 2.4.0 (2026-10-02): a mismatched pair raises instead of drawing a shorter chart

### Fixed

- **99 `zip()` calls said nothing about length, and 85 of them should have.**
  A `zip()` over two sequences stops at the shorter one. Where those sequences
  are parallel by construction (x against y, labels against values, centres
  against radii), a length that diverges meant the tail was dropped in silence
  and the figure still rendered, correct-looking and wrong. Those 85 now pass
  `strict=True` and raise instead. The remaining 14 are sliding pairs
  (`zip(xs, xs[1:])`) where the truncation is the point, and say `strict=False`.
  Ten generators already used `strict=True`: the convention existed and had
  never been carried through.

  This is the one change here a caller can feel. Data that silently lost its
  tail now stops with an error, which is the behaviour this package exists to
  provide, and is why this is a minor release rather than a patch.
- **A malformed request got a 500 where it had earned a 422.** The HTTP surface
  answered a client mistake with a server error.
- **`editor`: a textual column profile crashed the whole warnings pass.** One
  column of the wrong kind took down every warning the pass would have raised,
  not just its own.
- **`editor`: four `io_bound` results were never checked.** Whatever those
  calls reported, nobody read it.
- **`horizon`: an empty series is skipped rather than fatal.** One series with
  no points stopped the whole figure.
- **The linter was looking at a fifth of the package.** Its path configuration
  left four fifths unread, so "ruff passes" meant less than it appeared to.
- **`harchaoui.org` is gone, and every reference pointed at it.** The host now
  answers 503; the links go to `deraison.ai` and `sprezzature.ai`.
- **`mcp.py` defined `main` twice, and the two took different arguments.** The
  fallback reached when the `[mcp]` extra is absent took nothing while the real
  one took `argv`, so `main(["--host", "127.0.0.1"])` answered on a machine
  with the extra and raised `TypeError` on a machine without it. The broken
  half is the one a reader who skipped the extra meets first.

### Changed

- **119 typing imprecisions across the package, its scripts and its tools**,
  including one contract string and thirteen names that each stood for two
  different things in the same scope. No behaviour depends on these; they are
  what let the type gate below say something trustworthy.

### Added

- **A type gate**, `mypy.ini` plus one CI step over the package, `scripts/` and
  `tools/`. The monorepo carried one while the skills lived there; at the split
  ruff came with the package and mypy did not. Run by hand, it found the `main`
  defect above in six packages at once.
- **`test_mcp_fallback_signature.py`**, reading the source as a syntax tree so
  it needs neither mypy nor an install; a guard on the command names the help
  text advertises; and a case ruling out the state where that guard's scan
  finds no candidates and reports green while testing nothing.
- **A versioned `.githooks/pre-push`** running lint, types and all three test
  lanes, the default one plus `slow` and `packaging`, so the heavy work happens
  before the push rather than after it.

## 2.3.0 (2026-09-14): a figure proved legible without a vision model

### Added

- **`check_render()` — the questions the eyeball loop asks, answered from the
  SVG source.** The Ralph Eyeball Loop decides "does this read?" by showing the
  PNG to a vision model, and that answer only exists where such a model does. A
  service with a text-only LLM (large language model, a model that reads and writes text), or none, still ships figures and cannot have
  someone look at each one. This asks the same questions from the markup and
  answers them the same way every time: do labels collide, does text run off
  the canvas, did a generator's demo chrome ("Region", "Quarterly figures")
  survive into a real render, is a dark figure actually dark or is there a
  light card in the middle of it, is the caller's title on the figure, is there
  an accessible title and description.

  It makes no judgement of taste and never will. It replaces the eyeball on
  questions of **fact**, which is most of what goes wrong: the failures seen in
  production were overlapping ticks, a leftover template title, and a white
  panel on a dark page — every one decidable from the markup.

  On all five surfaces: `from sprezzature_figures import check_render`,
  `sprezzature-figures check fig.svg` (exit 1 on any finding, so it gates a
  commit), `POST /check_render`, the `check_render` MCP tool derived from that
  route, and a row in the skill.

- **`tests/test_render_matrix.py`** renders the catalogue the way an
  application does — rows in, profile, recommend, bind, render — over datasets
  that reproduce the shapes that broke in production: identifiers long enough
  to collide on an axis, more categories than an axis holds, French labels with
  accents, decimals from a database driver. Every render then goes through
  `check_render`.

### Fixed

- **The checker measured text differently from the generators, and invented a
  defect.** It estimated width as `len(text) × size × 0.52`. On the demo bar
  chart's standfirst at 26 px that gives 757 px, where Roboto renders 640 —
  so the reference figure was reported as overflowing a canvas it fits with
  65 px to spare. A false positive destroys the only thing that makes such a
  module worth having, which is that a failure is worth acting on.

  Width now comes from `scripts/_textfit.py`'s calibrated per-character table —
  the one the generators lay out with — so a string the generator fitted cannot
  be reported here as overflowing. Agreement by construction rather than by two
  independent guesses. The flat ratio survives only as a fallback for an SVG
  this package did not render.

- No light card on a dark page, and a title the caller asked for is honoured
  (`make_pareto`).

## 2.2.0 (2026-09-14): a chart you were sent, tools an agent can choose between, and a dark canvas

### Added

- **`dark=True` — the same figure, drawn for a dark canvas.** The
  full-canvas white rectangle is dropped so the figure sits transparent on
  whatever is behind it, and the chrome (ink, secondary text, gridlines) is
  lightened. Series colours are untouched, and so is the white that carries
  meaning — a label printed on a coloured bar. Reachable as
  `make_figure(..., dark=True)`, `--dark` on the CLI, and `to_dark()` for an
  SVG you already have. Applied centrally in `make_figure` for SVG output and
  popped before the generator runs, so no generator learns a second palette.
  The light rendering is unchanged byte for byte.

- **`redraw()` — a picture of somebody else's chart in, a sprezzature figure
  out.** A vision model reads the image; the figure is drawn here. Reachable
  from every surface: `from sprezzature_figures import redraw`,
  `sprezzature-figures redraw theirs.png`, `POST /redraw`, and the
  `redraw_figure` MCP tool that route derives.

  The design decision is what the mode is for. A picture of a chart carries
  its **design** legibly and its **data** almost never, so the two are kept
  apart and every result says which it got: `data_origin` is `your-data`
  (you passed rows), `read-from-image` (the numbers were printed on the
  original and read back, approximate), or `demo` (nothing readable — the
  redesign on the kind's sample rows, a mock-up to react to). It never
  guesses numbers off a picture.

  The provenance caption is stamped onto the figure itself, in a strip grown
  below the drawing after rendering. Passing it as a subtitle would have
  silently dropped it on 79 of the 127 kinds, whose generators declare no
  `subtitle` parameter — an uncaptioned mock-up that looks like a result is
  the one failure this mode cannot have. For the same reason, a `demo`
  redraw does not inherit the original's axis titles or standfirst: they
  describe columns the sample rows do not have.

  The model may only name a kind from the candidate list it was handed, the
  rule already applied to figure recommendations.

- **`POST /recommend` / the `recommend_figures` MCP tool.** The deterministic
  compatibility + readability ranking the CLI already ran, over HTTP. An agent
  handed 127 kind names and no guidance guesses; this hands back the ones the
  rows can actually fill, each with its role bindings resolved.

### Changed

- **Every MCP tool now carries a written summary and a description saying when
  to call it.** FastAPI derives a missing `summary` from the function name, so
  the headline an MCP host displayed for `redraw_route` was "Redraw Route",
  for `kinds` "Kinds", for `kind_definition` "Kind Definition". That headline
  is most of what an agent reads when choosing between tools from several
  servers. Two tests now fail the build if a summary is the default or a
  description is too short to route on.
- **`TRIGGERS.md` is now a routing document rather than a list of phrases.**
  Enumerating chart names cannot generalise — the catalogue is open-ended and
  grows. The vocabulary of *intent* is closed, so the file routes on that: the
  nine goals `recommend_figures` accepts, the three shapes a chart request
  arrives in, and what to call on each surface for each.

## 2.1.0 (2026-09-13): three figures were drawing something other than what they claimed

### Fixed

- **`hexbin`** binned on a lattice laid out in data units, then painted every
  cell with one pixel radius taken from the x axis. The two axes do not map
  data to pixels at the same rate, so rows landed at 42% of the spacing the
  drawn hexagon needs and each cell swallowed most of its neighbours. Binning
  now happens on the screen lattice, so the tiling is exact whatever the
  aspect ratio.
- **`quiver`** drew a bare triangle per node, sized by magnitude. Its subtitle
  promised "length follows magnitude"; nothing carried length, and the channel
  a vector field is read by was missing. Arrows now have shafts, and length
  runs from 30% to 100% of the node spacing.
- **`spectrogram`** and **`imshow-interpolated`** inflated every cell by
  0.6-0.7px to hide an anti-aliasing seam their group already prevents with
  `shape-rendering="crispEdges"`. On cells that small it was 15-23% of their
  width, so each bled into its neighbour. Cells now use their exact footprint.

### Changed

- **`_svg.raster_row_rects`** merges each run of equal colours in a raster row
  into one rect. Lossless. `spectrogram.svg` drops from 4.5 MB to 1.06 MB with
  the render unchanged pixel for pixel; `imshow-interpolated.svg`, whose ramp
  is now snapped to 64 levels so runs can form at all, from 2.7 MB to 982 KB.
  The quantisation was measured: at most 7/255 difference on any channel.
- **`FIGURES.md`** said 124 chart types; there are 127. The same stale count
  was in `README.md`, `LISEZMOI.md`, `LANDSCAPE.md`, `PAYSAGE.md`,
  `TRIGGERS.md` and `CODING.md`. The registry itself was already correct.

### Added

- **`tools/audit_tiling.py`** measures overlap between congruent cells in a
  rendered figure. Reading generators for lattice defects does not work — the
  pixels-per-unit factor is spelled differently in every file — so this checks
  the output instead. Calibrated on hexbin: 64% before its fix, 0.0% after.

## 2.0.0 (2026-09-11): every figure is authored as SVG, and the package says so

Major, because three things a caller could reach for are gone. Each named
or served a charting library this stack has not used for some time: the
code had moved on and the surface had not.

### Removed

- **`scripts/_vl.py`**, a Vega-Lite spec helper imported by nothing.
- **`sprezzature_figures.fonts.register_matplotlib` and `register_all`**,
  and the `register_all()` call at the top of `make_figure()`. They
  registered the bundled faces with a plotting library this package does
  not use. Neither name is exported from the package's `__all__`, but
  both were importable: a caller reaching for them will need to drop the
  call.
- **`audit_figure.py`'s Vega-Lite JSON (JavaScript Object Notation, records as named fields) mode** — `rules_for_vega`,
  `_iter_units`, `_iter_specs`, `_unit_rules` and the `.json` dispatch,
  about 220 lines. With every figure authored as SVG directly, the
  rendered markup *is* the source and there is no spec to audit. Five
  rules went with it (`missing-axis-title`, `dual-y-axis`,
  `truncated-baseline`, `cvd-unsafe`, `missing-polarity`): each read a
  chart grammar, not a rendering. Passing a directory now expands to
  `.svg`/`.html`/`.htm` only. **This is a breaking change for anyone
  auditing a `.json` spec with this tool.**
- **Roboto Serif from the distributed package.** It was 12.2 MB of an
  18.6 MB wheel, and nothing asks for it: `THEMES["corporate"]` is
  sans+mono, `THEMES["academic"]` is Latin Modern, and no module
  references the `serif` face key. The web app self-hosts its own copy.
  The faces stay in the source tree, so a checkout is unchanged;
  `available_faces()` reports eight of the ten face keys in a wheel
  install rather than all ten, and
  `font_data_uri("serif")` — which nothing called — now raises. The wheel
  drops from 11.5 MB to 3.2 MB, 18.6 MB unpacked to 6.4 MB.
- Unused declared dependencies: `wordcloud`, `vega_datasets`, `altair`,
  `cycler`, `matplotlib` and `seaborn` from the `dataviz` tier, and
  `graphviz` from `causal`. None was imported anywhere. `pydot` stays —
  `causal_estimate.py` parses `.dot` files through
  `networkx.nx_pydot.read_dot`, which reads the format and draws nothing.

### Changed

- **No charting library is named anywhere in this repository any more.**
  127 generator docstrings carried a paragraph of migration history
  ("Previously rendered via Vega-Lite (`vl_convert`); this module now
  builds the `<svg>` markup by hand…"): accurate, but history the reader
  does not need and the stack no longer has. Each was rewritten to keep
  its substance — *why* the geometry is authored directly — without the
  archaeology. Same pass over `fonts.py`, `_style.py`, `_render.py`,
  `explain_model.py`, `causal_estimate.py`, `render_diagram.py`, the
  catalog, the READMEs and the editor docs.
- `catalog/models.py`: `RendererKind` narrowed from
  `("vega_lite", "vega", "svg", "matplotlib", "html")` to
  `("svg", "html")`. All 124 catalogue entries already declared `"svg"`.
- `core/rendering.py`: `_SVG_LIKE_RENDERERS` is now `{"svg"}`, and the
  matplotlib PNG branch is gone.

### Fixed

- **The Latin Modern fonts shipped without their licence.** The wheel's
  `package-data` matched `OFL-*.txt`, which covers the three Roboto
  licences but not `GUST-FONT-LICENSE-LatinModern.txt`, so four faces
  went out with no accompanying terms. The licence now travels with the
  fonts it covers.
- `make_donut.py`'s docstring read "not with Vega or no matplotlib", a
  mangled sentence from an earlier automated pass.

### Testing

- `tests/test_no_third_party_plotting.py` now sweeps **every module in
  the repository** rather than a hand-kept list of five, with two checks:
  no module imports a charting library, and no module so much as *names*
  one. The shortlist version guarded five scripts while 120 generators
  drifted. Three files are allowlisted for the mention rule, each for a
  stated reason: the guard itself, `tools/audit_generators.py` (whose
  backend markers are the whole mechanism), and `make_circle-packing.py`
  (a faithful port of a published algorithm — naming the source of
  ported code is provenance, not a dependency). Nothing is exempt from
  the import rule. The new sweep immediately caught four mentions a
  manual pass had missed.

### Added

- **Explicit axis/color-scale overrides on `heatmap` and `line-multi`,**
  for callers who need several figures to share one comparable scale
  instead of each auto-scaling to its own data (a before/after pair, or a
  fixed print-figure grid). `make_heatmap`/`build_svg` gained `vmin`/`vmax`
  (color-ramp extremes, both CLI-exposed as `--vmin`/`--vmax`);
  `make_line_multi`/`build_svg` gained `x_domain`/`y_domain` (explicit axis
  bounds), `x_tick_step`/`y_tick_step` (evenly-spaced labeled ticks via the
  new `_scale.fixed_step_ticks`), and `y_minor_step` (unlabeled minor
  gridlines, requires `y_domain`); all five auto-exposed as CLI flags
  through `_render.py`'s existing `_OPTIONAL_FLAGS` registry (including a
  new `"lo,hi"` parser for the two tuple-shaped domain flags). Left unset,
  every one of these generators renders byte-identical to before. Covered
  by `tests/test_axis_overrides.py`.

### Removed

- **`choropleth` and `situation_map` moved to their own repo,
  [sprezzature-maps](https://github.com/warith-harchaoui/sprezzature-maps).**
  126 registered chart kinds -> 124. the editor will not grow
  map support; maps get their own product (and, eventually, their own
  Editor) instead of two entries in this catalogue. `sprezzature-maps`
  depends on this package for shared rendering primitives (font
  embedding, self-contained SVG mode) rather than duplicating them; the
  other Geospatial-category kinds that share `assets/geo/` (`dotdensity`,
  `hexbin-map`, `spike-map`) stayed here, unaffected.

- **matplotlib, Vega, and graphviz, entirely.** The last three third-party
  plotting/layout backends are gone: `explain_model.py`'s SHAP/TimeSHAP/
  Shapash paths now reuse the catalogue's own `make_bar`/`make_waterfall`
  generators plus two bespoke SVG plots (beeswarm, dependence scatter)
  built from the shared `_svg.py`/`_style.py` primitives; `causal_estimate.py`'s
  DAG (directed acyclic graph, arrows from causes to effects that never loop back) is a hand-written layered (Sugiyama-style) SVG layout instead of
  `graphviz.Digraph`, and its forest plot is hand-authored SVG instead of
  a matplotlib figure; `render_diagram.py`/`ralph_eyeball_loop.py` drop
  the "vega" source kind entirely (`tikz`/`mermaid`/`svg` remain).
  `pyproject.toml` no longer declares matplotlib in any extra.
  `tests/test_no_third_party_plotting.py` grep-guards the migrated
  scripts against these imports returning.

### Fixed

- **93 unparameterized-chrome-text bugs across 54 generators.** Axis
  titles, legend headers, and unit labels were hardcoded as f-string
  literals with no matching parameter, so a generator plotting real
  (non-demo) data could silently keep its demo chrome: the bug was first
  caught in `make_columnrange` (a revenue chart still labeled "Temperature
  (°C)" / "City", plus a hardcoded month-order list that scrambled real
  date labels outside `["Jan","Apr","Jul","Oct"]`, and a fixed left margin
  that let the y-axis title collide with wide tick labels). Generalized
  into a permanent static check, `scripts/audit_generator_hardcoded_text.py`,
  then every one of the 93 warnings it found was fixed by exposing the
  chrome text as caller-overridable keyword parameters. The audit now
  reports 0 warnings across `scripts/`.

- **CLI/API renders no longer leak demo captions into real data.**
  Passing `--data` only ever set the title, so generators fell back to
  their demo subtitle and axis captions regardless (any CSV (comma-separated values, a table saved as plain text) rendered as a
  bar chart kept the "Quarterly figures" subtitle and "Region" axis
  label). `make_figure()` now suppresses the demo subtitle and titles the
  axes from the user's own column names via the role binding, and filters
  keyword arguments against each generator's actual signature before
  calling it.

- **Causal DAG parsing, forest-plot label collisions, and SHAP/Shapash
  rendering bugs.** `causal_estimate.py`'s `--dag`/`--dag-string` now
  correctly parses hand-written Graphviz DOT (`X -> Y`), not only GML (Graph Modelling Language, a text format for graphs), as
  both flags already documented; forest-plot value labels now measure
  their own rendered width before deciding which side of the dot to sit
  on, instead of switching purely on the value's sign (which collided
  with the row-label column for a near-zero or a large-negative value).
  `explain_model.py`'s SHAP beeswarm caps at 150 subsampled points per
  row so the swarm shape stays legible past `--n-explain 300`, and
  `run_shapash` wraps `model.predict()`'s raw ndarray in a named
  `pd.Series` before handing it to Shapash's `compile()`, which otherwise
  raised `ValueError`. `make_bar-grouped.py`'s `_region_colors()` only
  curated 3 hues; a 4th real region wrapped the cycle and collided with
  the 1st in color, now falls back to the full default `cycle_hues` cycle
  beyond 3 regions.

- **Editor ingest/recommendation: currency misclassification, missed
  data-quality warnings, database-driver types, and a recommendation-limit tie
  break (TAB-03/TAB-05).** `_CURRENCY_NAME_RE` matched `eur`/`usd`/`gbp`
  as a free substring, so a French column named `valeur` ("value") was
  classified `currency` instead of `numeric` purely because it contains
  "eur", which fed a wrong chart-recommendation goal; the codes are now
  delimited (`(^|_)(usd|eur|gbp)($|_)`). `profile_dataframe` computed
  `null_count`/quantile stats per column but never turned them into
  warnings, so a file with missing values, IQR (interquartile range, the spread of the middle half of the values) outliers, or duplicate
  rows produced an empty warning list; `_data_quality_warnings` now
  surfaces all three from the stats already collected. A `DataFrame`
  built from raw database driver rows (`pd.DataFrame(psycopg_rows)`) keeps
  `decimal.Decimal`/`datetime.date` values as plain Python objects, so
  `is_numeric_dtype`/`is_datetime64_any_dtype` both reported `False` on
  columns that were unambiguously numbers or dates, cascading into a
  wrong recommendation goal and, in one observed case, a column binding
  that silently plotted the wrong column entirely; `_coerce_db_driver_types`
  now recasts all-Decimal and all-date `object` columns before profiling.
  Finally, `recommend_figures(limit=...)` truncated its tied candidate
  list before breaking the tie by goal, which could drop the one kind
  that actually answers the request (a datetime+measure trend losing
  "line" to an alphabetically-earlier tied kind); it now accepts an
  optional `goal` and passes it through to `rank()` before truncating.

- **`_SCRIPTS_DIR` resolution no longer loses to an unrelated same-named
  folder.** An installed environment with any third-party `scripts/`
  directory earlier in the search path than the dedicated
  `sprezzature_figures_scripts/` package made every figure resolve
  silently to the wrong place. The dedicated name is now searched first,
  with the generic `scripts/` name kept only as a fallback for running
  from the source tree, where the dedicated name never exists.

- **`--map` accepts a role's label, not only its historical key.** Role
  names predate the current chrome (e.g. `bar`'s category role is still
  called `region`, after its original demo data), so `--map category=month`
  now binds correctly instead of requiring the internal key; a failed
  render lists every required role together with its label and accepted
  types, instead of naming only the first one missing.

- **`_scale.fixed_step_ticks` no longer overshoots `hi`.** When `step` did
  not evenly divide `hi - lo` (e.g. a 24-hour axis ticked every 3 units
  from a 23-inclusive domain), a naive `round()` of the tick count could
  place the last tick past `hi`, rendering a gridline/label outside the
  plotted axis.

- **All 126 registered chart kinds are now `status="stable"`, up from 46.**
  The other 80 were stuck at `status="legacy"`: real, complete generators
  (some 400+ lines with a working `build_svg()` and their own CLI) that
  predated the unified `make_<kind>(data=None, *, out=None, ...) -> Path`
  contract, so `make_figure()` / the CLI / the API / MCP could not call
  them even though the scripts worked. Every one now exposes the contract
  function and a genuine `list[dict]`-shaped `DEMO_DATA`, with caller-supplied
  data threaded through wherever the underlying renderer's geometry allows it
  (documented as accepted-but-illustrative-only on the handful where it
  doesn't, e.g. `chord`, `arcdiagram`, `circle-packing`: a fixed, hand-tuned
  narrative). `gapminder` / `gapminder_variants`, previously blocked on a
  missing external dataset, now ship a small embedded synthetic fallback.
  Added `scripts/_interactive.py`'s `hover_isolate_css()` so the "hover one
  mark, dim the rest" interaction pattern has one shared source instead of
  being hand-written slightly differently per generator. Every stable kind
  now also declares `required_roles`/`optional_roles` in the catalog
  (`tools/build_figures_catalog.py`'s `HAND_ROLES`), derived from each
  generator's actual `DEMO_DATA` shape, so the editor's role-binding UI (user interface) and
  `sprezzature-figures recommend` can reach all 126, not 46.

## [1.1.0] - 2026-08-06

### Removed

- **The last live Vega code path.** `scripts/make_figure.py` (a legacy
  CSV/x/y/kind dispatcher emitting Vega-Lite JSON or matplotlib) predated the
  one-generator-per-kind SVG architecture and was never wired to any
  console-script entry point, but stayed directly runnable and documented in
  `references/publication-presets.md`. Both are deleted, along with
  `_style.vega_config` (its only caller) and `references/figure-catalog.md`
  (an obsolete "prefer Vega-Lite" policy doc). All 126 chart kinds are
  hand-authored SVG; the only Vega left anywhere in the repo is
  `render_diagram.py` rasterising a caller-supplied external spec.

### Fixed

- **Two library crashes found by live-testing the CLI/API surfaces.**
  `make_bar`'s "leads at ..." subtitle formatted `value` with `:.0f` without
  the `float()` cast every other aggregate already had, so a string-typed
  `value` column (the common case from CSV/JSON input) raised `ValueError`.
  `make_area` indexed `row["channel"]` unconditionally and colored bands from
  a dict keyed to the four hardcoded demo channel names, even though
  `channel` is declared optional in the catalog; real data with no channel
  column, or a channel value outside that fixed set, raised `KeyError`.
  Channels are now derived from whatever the data actually carries, falling
  back to a single unnamed series with no legend. Found via
  `sprezzature-figures recommend --render` on a plain three-column CSV.

### Changed

- **`references/` moved off `main` onto a `skills` branch.** It's guidance
  for a human or coding agent (Ralph Eyeball Loop protocol, corner-radius
  policy, engine-selection tables, ...), not something any script or the
  packaged library reads at runtime, and isn't shipped by `pyproject.toml`.
  It now lives alongside the planned Claude/OpenCode `SKILL.md` rewrite on
  the `skills` branch.
- **CI cut from 9 jobs per push to 2.** The 3-OS x 2-Python test matrix plus
  a 3-OS packaging matrix wasn't needed for day-to-day regression coverage
  and left runs queuing during a burst of pushes. Both jobs now run once on
  `ubuntu-latest` / Python 3.12, with a `concurrency` group
  (`cancel-in-progress: true`) so a fast sequence of pushes supersedes its
  own stale runs instead of piling up.

### Fixed

- **`--out` now honours the file extension.** The SVG-first generators used to
  write their SVG string verbatim into whatever path you named, so `--out
  chart.png` produced SVG bytes in a `.png` file. `write_svg` (the shared tail
  every generator calls) now converts the font-embedded SVG to the requested
  format: `.png`, `.pdf`, `.jpg` via `resvg_py`, `.html` wrapped in a minimal
  responsive document, and `.svg` written byte-for-byte as before. Applies to
  the library and both CLIs. (the editor was already correct here: it always
  renders the figure to `.svg` and rasterizes a separate PNG preview.)

### Fixed

- **Seven hero-SVG generators are reachable through the dispatcher again.**
  `speaking_time`, `situation_map`, `binned-grid-map`, `hexmap`, `hexbin-map`,
  `spike-map`, and `dotdensity` failed under `make-figure <kind>` / the editor:
  some crashed importing their sibling helpers (`_interactive`, `_render`, ...),
  the rest had no `make_<kind>` callable for the registry to dispatch to.
  `make_figure._load_module` now guarantees the generator's directory is on
  `sys.path` before import (so a generator loads the same whether it runs first
  or tenth), and each of the seven grew the standard
  `make_<kind>(data=None, *, out=None, ...)` entry that builds its bundled demo.
  The three map generators that render onto a basemap now find their vendored
  Natural Earth data (`assets/geo/countries-50m.json`, `countries-110m.json`,
  `fr/departements-simplifiee.geojson`), which had been referenced but not
  committed. `gapminder` / `gapminder_variants` remain blocked on a separate
  missing dataset and are unchanged.

### Added

- **New figure: `interruption-matrix` ("Qui coupe qui ?").** A directed
  "who cuts whom" heatmap for conversation analysis: rows are speakers being
  cut off, columns the interrupters, each cell the interruption count tinted by
  the interrupter, with row/column totals and a one-line bilan. It carries a
  crosshair hover (self-contained mode): pointing at a cell lights that
  interrupter's whole column and that interrupted's whole row and dims the rest,
  so "everyone X cut" and "everyone who cut X" light up together. Full house
  treatment: accessibility levels, dark mode, forced-colors fallback, native
  tooltips, `role="img"` + a computed `<desc>`. Companion to `speaking_time`;
  92 chart types now. Roles: `interrupter`, `interrupted`, `count`.
- **Intent-aware recommendation ranking.** `sprezzature-figures recommend`
  gained `--intent GOAL` (comparison, trend, distribution, composition,
  relationship, flow, hierarchy, geography, model_evaluation). Without it the
  readability score leaves many kinds tied at 1.00; with it, figures whose
  category serves the stated goal are ranked first (top band [0.6, 1.0], others
  [0.0, 0.4]), with readability breaking ties within each band. The engine
  (`editor.recommendation.score` / `rank`) now takes an optional `goal`, derived
  from each figure's populated `category` (the `intents` catalog field is empty
  across all kinds), so the signal covers all 91 figures with no hand
  annotation. `goal=None` is unchanged, byte-for-byte, from before.
- **`--scale N` for hi-DPI raster output.** Both render CLIs (`make-figure`
  and `sprezzature-figures render`) take `--scale N` to upsample `.png` /
  `.jpg` / `.pdf` output N times, e.g. `--out chart.png --scale 3` for a
  crisp 3x raster. It threads through to the single rasterisation choke point
  (`scripts/_render.py`) via the `SPREZZATURE_RENDER_SCALE` env var, so no
  generator signature changed; the default (1x) leaves output byte-identical,
  and `.svg` / `.html` are unaffected.
- **`--data -` reads from standard input.** `make-figure <kind> --data -`,
  `sprezzature-figures render --data -`, and `recommend --data -` read piped
  JSON (JavaScript Object Notation) / JSONL (JSON Lines, one record per line) / CSV (the shape is sniffed from the content, since stdin has no
  filename), so data can flow straight from a pipe without a temp file:
  `curl -s … | make-figure bar --data -`.
- **Render your own data from the CLI.** `make-figure <kind> --data file`
  (and the Click twin `sprezzature-figures render --data file`) now reads a
  local `.csv` / `.tsv` / `.json` / `.jsonl` file into the row shape every
  generator expects, instead of only the built-in demo data. The loader
  (`sprezzature_figures.data_source.load_records`) stays dependency-light: it
  uses pandas when installed and falls back to the stdlib `csv` reader with
  numeric coercion otherwise, so it works on a bare install. `make_figure.py`
  also gained a `__main__` guard, so `python -m sprezzature_figures.make_figure`
  works.
- **`--map role=column` for the render CLIs.** When a data file's headers
  don't match the figure's role names, bind them without editing the file, e.g.
  `make-figure bar --data gdp.csv --map region=Country --map value=GDP`
  (repeatable). Backed by `data_source.parse_mapping` / `apply_mapping`. The
  render CLIs also now report a clean error (with a `--map` hint) instead of a
  traceback when the data doesn't fit the chosen figure.
- **the editor data panel accepts JSON too.** File import now takes
  `.csv` / `.tsv` / `.xlsx` / `.json` / `.jsonl`, routing JSON through the same
  `data_source.load_records` the CLI uses, so both surfaces accept identical
  shapes.
- **Headless chart recommendation from the CLI.** `sprezzature-figures
  recommend --data file` ranks the chart types your data can fill, best first,
  showing each figure's score and its `role=column` binding. It reuses the same
  deterministic `editor.recommendation` filter + readability score the editor
  GUI (graphical user interface) shows as cards, with no model involved. `--render out` also renders the
  top pick, applying its role binding automatically. Needs the `[cli]` +
  `[editor]` extras (falls back to a clear install hint otherwise).
- **Transformations now execute.** `core.transformations.apply_transformations`
  runs a `FigurePlan`'s filter / sort / aggregate / top-N / group-others /
  calculate / temporal steps deterministically over the imported rows, in list
  order, with no code evaluation. The editor's render path and the export
  bundle both apply it, so a filter or sort requested in the chat actually
  changes the rendered figure and the exported `transformed.csv`. A transform
  whose column is absent is skipped with a note rather than silently emptying
  the figure.
- **The Ralph loop is resilient to a live model failing.** A model that
  returns empty or malformed JSON, times out, or is unreachable no longer
  crashes the turn: the figure still renders and the reason is reported in
  `RalphResult.notes` (stop reason `critique_unavailable`), across manual,
  assisted, and autopilot modes.
- **Model-facing schemas carry field descriptions** and the intent / edit /
  recommend / critique prompts were rewritten so a live model fills every
  field instead of defaulting to empty. `SetStyleOption.option` is now a
  `Literal` of the real `StyleOptions` fields, so the model can only target a
  style setting that exists.
- **Deterministic figure recommendation** (`editor.recommendation`): a
  hard-constraint compatibility filter and a readability score, surfaced as
  one-click auto-bound recommendation cards in the data panel. Stable figures
  gained readability limits (max categories / rows) so the ranking is
  meaningful.
- **Editor side panels**: iteration history is now recorded, an undo / redo /
  "Export .zip" toolbar and a style property panel were added, and edit chat
  operations are de-duplicated. Transform and model-failure notes are shown to
  the user instead of only logged.
- **the editor** (`sprezzature-figures` CLI, `[editor]` extra): a
  local NiceGUI app to import a CSV/XLSX, pick a chart type, bind columns
  to data roles, and refine the figure by chatting with Ralph, an
  LLM/VLM copilot that edits a structured `FigurePlan` and inspects the
  rendered PNG before deciding it's done. See
  [docs/editor/README.md](docs/editor/README.md).
- 7 new chart types: bar, line, area, scatter, histogram, boxplot, heatmap.
  The first `make_figure("bar", ...)` example in the README is finally
  literally true.
- Explicit figure registry (`sprezzature_figures/catalog/figures.json`):
  decouples a chart's public kind name from its filename/function name.
  `make_figure()` and `make-figure --list --status stable` now report an
  honest `stable`/`experimental`/`legacy`/`unavailable` status per figure
  instead of assuming all 90 work.
- Reproducible generator audit (`tools/audit_generators.py`).
- A lightweight GitHub Actions CI workflow.
- **Self-hosted house typography** (`sprezzature_figures/fonts.py`):
  Roboto, Roboto Serif and Roboto Mono are now bundled as variable
  TTF (TrueType Font)/WOFF2 files in the repo/wheel (`assets/fonts/`, shipped as the
  `sprezzature_figures_fonts` package) instead of being assumed present
  on the host or fetched from a CDN (content delivery network, a server that hosts files for many sites). Every hand-written SVG generator and
  every Vega-Lite generator now embeds `@font-face` (base64 WOFF2 (Web Open Font Format 2, the compressed font format browsers download))
  directly in its output (`write_svg()`/`svg_open()`), matplotlib
  generators register the bundled fonts with `font_manager` (and bake
  `svg.fonttype="path"` for portable SVG output), the Vega-Lite → PNG
  preview pipeline points `vl_convert` at the bundled font directory, and
  the editor web app self-hosts the same WOFF2 files (no Google Fonts
  CDN) via `@font-face`. Figures and the editor UI now look identical
  regardless of what fonts are installed on the machine viewing them.

### Changed

- The default LLM/VLM backend ([best-engine-ai-helper]) now passes each request
  a JSON schema for grammar-constrained structured output, and defaults to a
  text model that honours it (`qwen3:8b`) and a vision model that does the same
  for image prompts (`gemma3:12b`). Override with `BEST_LLM_TEXT` /
  `BEST_LLM_VISION`. editor's chat and visual-critique features now work out of
  the box against a local Ollama.

[best-engine-ai-helper]: https://github.com/warith-harchaoui/best-engine-ai-helper

### Fixed

- `make_figure()` (and the `make-figure`/`sprezzature-figures` CLIs) can
  now actually reach the 17 generator scripts whose filenames keep their
  hyphens (`connected-scatter`, `liquid-gauge`, `org-chart`, ...); the
  dispatcher previously guessed a filename by replacing hyphens with
  underscores, which doesn't match the file on disk.
- `sankey` rewritten to accept real `{source, target, value}` flow data
  (with automatic node/layer inference) instead of hardcoded demo
  nodes/links; it previously had no `make_sankey()` at all.
- `waffle`/`dumbbell` adapted to accept arbitrary data instead of a
  hardcoded module-level dataset.
- The `[cli]` extra (`click>=8.1`) is now actually declared; it was
  documented but missing from `pyproject.toml`.
- `figures.json` (the new registry) was missing from the built wheel;
  fixed and covered by a packaging test that builds + installs the wheel
  and renders a figure from it.
- `make_situation_map.py` raised `SystemExit` (not a catchable
  `Exception`) for a missing optional dependency at import time; now
  raises `ImportError`.

---

## [1.0.1] - 2026-07-29

### Added

- 6 new chart types: bell curve (bellcurve), column range (columnrange), funnel, sunburst, treemap, waterfall.
- FIGURES.md catalogue expanded with when-to-use guidance for new entries.

---

## [1.0.0] - 2026-07-29

Initial public release.

- 84 chart types across Vega-Lite, full Vega, matplotlib, and SVG renderers.
- `make_figure(kind, data, **kwargs)` unified dispatcher.
- `list_kinds()` returns all available chart types.
- `make-figure` CLI (argparse) always installed; Click CLI via `[cli]` extra.
- Ralph Eyeball Loop integration for autonomous visual QA (quality assurance; `audit_figure.py`).
- Full type annotations, ruff-clean, pytest test suite.
