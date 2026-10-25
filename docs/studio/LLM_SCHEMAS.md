# LLM/VLM structured output contracts

Ask a language model a free-text question and you get free text back: fine
for a chat reply, unusable as input to a program that expects, say, a list
of exactly this shape of edit. So every model call in Studio asks for a
specific shape instead of a paragraph, that shape is written down once as a
Pydantic schema, a Python description of "this response must have exactly
these fields, of exactly these types" (`sprezzature_figures.studio.
assistant.schemas`, plus `core.figure_plan.UserIntent`, reused rather than
duplicated), and the model's answer is checked against that schema (with
exactly one repair attempt) before anything downstream ever sees it. The
model never generates or executes code; it only ever fills in one of these
predeclared shapes.

## The client (`assistant.client`)

```python
class LLMClient(Protocol):
    def chat_text(self, prompt, *, system=None, response_model=None, temperature=0.1): ...
    def chat_vision(self, prompt, image: bytes, *, system=None, response_model=None, temperature=0.1): ...
```

`BestEngineLLMClient` is the real implementation: it wraps
`best_engine_ai_helper.llm.chat(prompt, *, system, images, json_schema,
temperature)` (a single function, not separate text/vision methods),
which is why `chat_text`/`chat_vision` on the client both funnel into one
private `_call()`. Model selection (which tag, which backend: Ollama,
OpenAI-compatible, LangChain) is entirely `best-engine-ai-helper`'s job;
nothing in this package hardcodes a model name or talks to a backend
directly.

`FakeLLMClient` (`assistant.fake_client`) is a queue of scripted responses:
model instances, raw strings (including deliberately invalid JSON), or
exceptions, replayed in order. Every test in this repository uses it instead
of a real model call.

## How the schema reaches the model

The response model isn't only used to check the answer after the fact: its
`model_json_schema()` (the same shape description, exported as JSON) is
handed to the backend *before* generation starts, as a grammar constraint,
a rule that blocks the model from producing any token that would break the
required shape, the same way a fill-in-the-blanks form makes some answers
impossible to write down. This steers the model to the right shape in the
first place instead of hoping it complies (Ollama's structured output, the
OpenAI `json_schema` response format). Each field also carries a
`description` in the Pydantic model, which the model sees, so it fills the
field with a real value instead of a default.

One transport detail lives in `best-engine-ai-helper`: some of these
schemas are a discriminated union, one field ("which kind of edit is
this?") that decides which of several different shapes the rest of the
object must take, the way a form's "type of vehicle" checkbox decides
whether the next field asks for a car's plate number or a bike's frame
size. Ollama's grammar engine cannot build that kind of union when its
branches are expressed as `$ref` pointers (references to a shape defined
elsewhere in the schema); when it tries, it silently emits an empty value
instead of raising an error. So the schema is flattened to a single tagged
object before it is sent to Ollama, and this package's own Pydantic model
re-validates the answer against the true union afterwards. The net effect
is that `FigureOperation` lists (chart edits, safe repairs) come back
populated rather than silently empty.

## Validate-then-repair (`assistant.repair`)

```
call -> validate against schema
  \-> on failure: one "fix your JSON" follow-up -> validate again
       \-> on second failure: raise LLMResponseError(raw_response=...)
```

Never falls through to a partially-valid object. `LLMResponseError` carries
the raw text so the caller can show the user what actually came back.

## The three contract types

### `UserIntent` (plan §10.1, `core.figure_plan.UserIntent`)

What the user is trying to show, extracted from their request plus a
`DatasetProfile` (column names/types/statistics; never raw rows unless
explicitly configured otherwise, see [DATA_PRIVACY.md](DATA_PRIVACY.md)).
`analytical_goal` is one of `comparison | trend | distribution |
composition | relationship | flow | hierarchy | geography |
model_evaluation | unknown`.

### `EditProposal` (plan §10.2)

```python
class EditProposal(BaseModel):
    summary: str
    operations: list[FigureOperation]
    expected_effect: str
    requires_confirmation: bool
    confirmation_reason: str | None
```

`FigureOperation` is the same discriminated union from
[FIGURE_PLAN.md](FIGURE_PLAN.md): 15 kinds, no free-form edits. Every
operation is re-validated against `core.validate_operation()` after the
model returns it (`assistant.edit.propose_edit`): anything referencing a
nonexistent column or an undeclared style option is dropped, silently, one
operation at a time, not the whole proposal.

### `VisualCritique` (plan §10.3)

```python
class VisualCritique(BaseModel):
    verdict: Literal["satisfied", "needs_changes", "blocked"]
    message_alignment_score: int       # 0-100, same for the next 4 fields
    readability_score: int
    visual_hierarchy_score: int
    accessibility_score: int
    data_fidelity_score: int
    issues: list[VisualIssue]
    safe_repairs: list[FigureOperation]
    editorial_suggestions: list[EditorialSuggestion]
    concise_summary: str
```

`safe_repairs` is re-filtered by `ralph.policy.is_safe_repair()` and
`core.validate_operation()` before anything in it is applied: the model's
own claim that a repair is "safe" is never trusted blindly. See
[RALPH_LOOP.md](RALPH_LOOP.md).

## `FigureRecommendation`/`RecommendationSet` (plan §6, LLM-facing half only)

`assistant.recommend.explain_recommendations()` reranks/explains a
**pre-filtered** list of already-compatible figure kinds: it never
introduces a kind outside the list it's handed. The deterministic
compatibility/scoring step that would build that candidate list (plan §6's
`studio/recommendation/` package) isn't built yet; see
[ROADMAP.md](ROADMAP.md).
