"""
Typed operations the FigurePlan can undergo.

Two distinct layers, per plan §4.2/§4.3:

- ``Transform``: a deterministic, auditable data-shaping step (filter, sort,
  aggregate, ...) that lives in ``FigurePlan.transformations`` and is applied
  to the dataset before rendering. No free-form formulas.
- ``FigureOperation``: a single chat-driven edit to the plan itself (set a
  title, bind a column, add a filter, ...). This is what an LLM's
  ``EditProposal`` (plan §10.2) is allowed to emit, validated before being
  applied -- never arbitrary code.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Transforms: deterministic data-shaping steps (plan §4.3)
# --------------------------------------------------------------------------


class _TransformBase(BaseModel):
    transform_id: str = ""


class FilterByValue(_TransformBase):
    kind: Literal["filter_value"] = "filter_value"
    column: str
    op: Literal["eq", "neq", "in", "not_in"] = "eq"
    values: list[Any] = Field(default_factory=list)


class FilterByRange(_TransformBase):
    kind: Literal["filter_range"] = "filter_range"
    column: str
    minimum: float | None = None
    maximum: float | None = None


class FilterTemporal(_TransformBase):
    kind: Literal["filter_temporal"] = "filter_temporal"
    column: str
    start: str | None = None  # ISO 8601 date/datetime
    end: str | None = None


class SortTransform(_TransformBase):
    kind: Literal["sort"] = "sort"
    column: str
    ascending: bool = True


class AggregateTransform(_TransformBase):
    kind: Literal["aggregate"] = "aggregate"
    group_by: list[str] = Field(default_factory=list)
    value_column: str
    agg: Literal["sum", "mean", "median", "min", "max", "count"] = "sum"
    output_column: str | None = None


class RenameDisplay(_TransformBase):
    kind: Literal["rename_display"] = "rename_display"
    column: str
    display_name: str


class TopN(_TransformBase):
    kind: Literal["top_n"] = "top_n"
    column: str
    n: int
    by: str | None = None  # value column to rank by; defaults to row order


class GroupOthers(_TransformBase):
    kind: Literal["group_others"] = "group_others"
    column: str
    keep: list[str] = Field(default_factory=list)
    other_label: str = "Other"


class CalculateDerived(_TransformBase):
    kind: Literal["calculate"] = "calculate"
    calc: Literal["difference", "ratio"]
    left: str
    right: str
    output_column: str


Transform = Annotated[
    FilterByValue
    | FilterByRange
    | FilterTemporal
    | SortTransform
    | AggregateTransform
    | RenameDisplay
    | TopN
    | GroupOthers
    | CalculateDerived,
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------
# Figure operations: chat-driven, plan-level edits (plan §4.2)
# --------------------------------------------------------------------------


class Annotation(BaseModel):
    annotation_id: str
    kind: Literal["text", "highlight", "reference_line", "callout"] = "text"
    target: str | None = None
    text: str = ""
    x: float | None = None
    y: float | None = None


class _OperationBase(BaseModel):
    operation_id: str
    reason: str = ""
    requires_confirmation: bool = False


class SetFigureKind(_OperationBase):
    operation_type: Literal["set_figure_kind"] = "set_figure_kind"
    new_kind: str


class BindColumn(_OperationBase):
    operation_type: Literal["bind_column"] = "bind_column"
    role: str
    columns: list[str] = Field(default_factory=list)


class UnbindColumn(_OperationBase):
    operation_type: Literal["unbind_column"] = "unbind_column"
    role: str


class SetTitle(_OperationBase):
    operation_type: Literal["set_title"] = "set_title"
    title: str


class SetSubtitle(_OperationBase):
    operation_type: Literal["set_subtitle"] = "set_subtitle"
    subtitle: str | None = None


# The style options a SetStyleOption may target. Kept in lockstep with
# figure_plan.StyleOptions' fields (a test asserts they match) and declared as a
# Literal so the value is a hard enum in the JSON schema the model receives --
# without it the model invents option names like "label_size" that
# validate_operation then rejects, so the edit silently does nothing.
StyleOptionName = Literal[
    "theme",
    "accessibility_mode",
    "width",
    "height",
    "font_scale",
    "legend_position",
    "sort_order",
    "number_format",
    "date_format",
    "highlight_values",
    "show_grid",
    "show_labels",
    "label_rotation",
    "palette",
]


class SetStyleOption(_OperationBase):
    operation_type: Literal["set_style_option"] = "set_style_option"
    option: StyleOptionName = Field(
        description=(
            "Which style setting to change. font_scale = text/label SIZE (>1 "
            "bigger, <1 smaller); legend_position = where the legend sits "
            "(top/right/bottom/left/none); label_rotation = tilt of axis labels "
            "in degrees; sort_order = category order; show_grid / show_labels = "
            "on/off toggles; palette / theme = colours; width / height = canvas "
            "size in px; number_format / date_format = value formatting."
        )
    )
    value: Any = Field(
        default=None,
        description="The new value for that option (e.g. 1.4 for font_scale, \"bottom\" for legend_position).",
    )


class AddFilter(_OperationBase):
    operation_type: Literal["add_filter"] = "add_filter"
    transform: Transform


class RemoveFilter(_OperationBase):
    operation_type: Literal["remove_filter"] = "remove_filter"
    transform_id: str


class SortRows(_OperationBase):
    operation_type: Literal["sort_rows"] = "sort_rows"
    transform: SortTransform


class AggregateRows(_OperationBase):
    operation_type: Literal["aggregate_rows"] = "aggregate_rows"
    transform: AggregateTransform


class CalculateColumn(_OperationBase):
    operation_type: Literal["calculate_column"] = "calculate_column"
    transform: CalculateDerived


class LimitCategories(_OperationBase):
    operation_type: Literal["limit_categories"] = "limit_categories"
    transform: TopN | GroupOthers


class AddAnnotation(_OperationBase):
    operation_type: Literal["add_annotation"] = "add_annotation"
    annotation: Annotation


class RemoveAnnotation(_OperationBase):
    operation_type: Literal["remove_annotation"] = "remove_annotation"
    annotation_id: str


class SetOutputSize(_OperationBase):
    operation_type: Literal["set_output_size"] = "set_output_size"
    width: int
    height: int


FigureOperation = Annotated[
    SetFigureKind
    | BindColumn
    | UnbindColumn
    | SetTitle
    | SetSubtitle
    | SetStyleOption
    | AddFilter
    | RemoveFilter
    | SortRows
    | AggregateRows
    | CalculateColumn
    | LimitCategories
    | AddAnnotation
    | RemoveAnnotation
    | SetOutputSize,
    Field(discriminator="operation_type"),
]
