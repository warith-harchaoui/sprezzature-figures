"""
theme — the Studio's visual language, matching the public
harchaoui.org/warith/sprezzature site (same Roboto typography, the same
neutral/brand-blue palette, the same rounded-card look) instead of raw
default Quasar styling.

The installed NiceGUI build ships no Tailwind utility CSS at all (its
``.classes()`` calls happily accept Tailwind-style tokens like ``w-1/4`` or
``gap-4``, but nothing defines them, so they are silent no-ops) -- that gap
is what made the first cut of the Studio UI look unstyled. This module is a
small, hand-authored, self-hosted subset of Tailwind covering exactly the
utility classes the Studio components use, plus the brand design tokens
(colors, radius, shadow) lifted from the reference site's own
``css/app.css``. No CDN, no build step: one `<style>` block injected once at
app startup (see ``studio/app.py::register_theme``).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re

# Brand + neutral tokens, copied from the reference site's Tailwind config
# (css/app.css): iOS-blue accent, Tailwind's stock neutral/gray/red/green/
# orange scales for the few semantic colors the Studio already uses.
_TOKENS = """
:root {
  --sz-blue: #007AFF;
  --sz-blue-dark: #0A84FF;
  --sz-ink: #171717;
  --sz-radius-sm: .375rem;
  --sz-radius: .5rem;
  --sz-radius-lg: .75rem;
  --sz-radius-xl: 1rem;
  --sz-shadow-sm: 0 1px 2px 0 rgba(0,0,0,.05);
  --sz-shadow: 0 1px 3px 0 rgba(0,0,0,.1), 0 1px 2px -1px rgba(0,0,0,.1);
}
"""

# Base page/typography reset -- the reference site's antialiased body on a
# neutral-50 canvas, ink-900 text, Roboto (already loaded by
# sprezzature_figures.fonts / register_fonts()).
_BASE = """
html, body { background: #FAFAFA; color: var(--sz-ink); -webkit-font-smoothing: antialiased; }
.nicegui-content { padding: 0 !important; gap: 0 !important; }
"""

# Handful of Quasar-native components restyled to the house look instead of
# Material defaults: primary buttons in brand blue with rounded corners,
# inputs/selects/uploaders as quiet neutral-bordered fields, cards with the
# reference site's soft border + shadow-sm + rounded-xl.
_COMPONENTS = """
.q-btn { border-radius: var(--sz-radius) !important; text-transform: none !important; font-weight: 500 !important; box-shadow: none !important; }
.q-btn.bg-primary, .q-btn[color=primary] { background: var(--sz-blue) !important; }
.q-btn.bg-primary:hover, .q-btn[color=primary]:hover { background: var(--sz-blue-dark) !important; }
.q-field__control { border-radius: var(--sz-radius) !important; }
.q-field--outlined .q-field__control:before { border-color: #E5E5E5 !important; }
.q-uploader { width: 100%; border: 1px solid #E5E5E5; border-radius: var(--sz-radius-lg); box-shadow: none; }
.q-uploader__header { background: var(--sz-blue) !important; border-radius: var(--sz-radius-lg) var(--sz-radius-lg) 0 0; }
.q-uploader__subtitle { display: none !important; }
"""

# A focused Tailwind-compatible subset: exactly the tokens the Studio
# components use today, plus a few (rounded-xl/2xl, shadow-sm, bg-white,
# neutral-*, space-y-*) added for the card-based redesign. Kept small and
# hand-readable rather than a full Tailwind build.
_UTILITIES = """
.w-full { width: 100%; } .h-full { height: 100%; } .h-screen { height: 100vh; }
.w-1/2 { width: 50%; } .w-1/3 { width: 33.3333%; } .w-2/3 { width: 66.6667%; }
.w-1/4 { width: 25%; } .w-3/4 { width: 75%; }
.max-w-full { max-width: 100%; } .min-w-0 { min-width: 0; }
.flex { display: flex; } .flex-col { flex-direction: column; } .flex-1 { flex: 1 1 0%; } .flex-wrap { flex-wrap: wrap; }
.items-center { align-items: center; } .items-start { align-items: flex-start; } .items-end { align-items: flex-end; }
.justify-between { justify-content: space-between; } .justify-center { justify-content: center; }
.gap-1 { gap: .25rem; } .gap-2 { gap: .5rem; } .gap-3 { gap: .75rem; } .gap-4 { gap: 1rem; } .gap-6 { gap: 1.5rem; }
.overflow-y-auto { overflow-y: auto; } .overflow-hidden { overflow: hidden; }
.p-0 { padding: 0; } .p-2 { padding: .5rem; } .p-3 { padding: .75rem; } .p-4 { padding: 1rem; } .p-5 { padding: 1.25rem; } .p-6 { padding: 1.5rem; }
.px-2 { padding-left: .5rem; padding-right: .5rem; } .px-3 { padding-left: .75rem; padding-right: .75rem; } .px-4 { padding-left: 1rem; padding-right: 1rem; } .px-6 { padding-left: 1.5rem; padding-right: 1.5rem; }
.py-1 { padding-top: .25rem; padding-bottom: .25rem; } .py-2 { padding-top: .5rem; padding-bottom: .5rem; } .py-3 { padding-top: .75rem; padding-bottom: .75rem; } .py-4 { padding-top: 1rem; padding-bottom: 1rem; }
.pl-2 { padding-left: .5rem; } .pr-2 { padding-right: .5rem; }
.mt-1 { margin-top: .25rem; } .mt-2 { margin-top: .5rem; } .mt-4 { margin-top: 1rem; }
.mb-2 { margin-bottom: .5rem; } .mb-4 { margin-bottom: 1rem; } .mx-auto { margin-left: auto; margin-right: auto; }
.space-y-1 > * + * { margin-top: .25rem; } .space-y-2 > * + * { margin-top: .5rem; } .space-y-4 > * + * { margin-top: 1rem; }
.text-xs { font-size: .75rem; line-height: 1rem; } .text-sm { font-size: .875rem; line-height: 1.25rem; }
.text-base { font-size: 1rem; line-height: 1.5rem; } .text-lg { font-size: 1.125rem; line-height: 1.75rem; }
.text-xl { font-size: 1.25rem; line-height: 1.75rem; } .text-2xl { font-size: 1.5rem; line-height: 2rem; }
.font-medium { font-weight: 500; } .font-semibold { font-weight: 600; } .font-bold { font-weight: 700; }
.whitespace-pre-wrap { white-space: pre-wrap; } .cursor-pointer { cursor: pointer; }
.transition { transition: all .15s cubic-bezier(.4,0,.2,1); }
.rounded { border-radius: var(--sz-radius-sm); } .rounded-lg { border-radius: var(--sz-radius); }
.rounded-xl { border-radius: var(--sz-radius-lg); } .rounded-2xl { border-radius: var(--sz-radius-xl); } .rounded-full { border-radius: 9999px; }
.shadow-sm { box-shadow: var(--sz-shadow-sm); } .shadow { box-shadow: var(--sz-shadow); }
.border { border: 1px solid #E5E5E5; } .border-t { border-top: 1px solid #E5E5E5; } .border-b { border-bottom: 1px solid #E5E5E5; }
.border-l { border-left: 1px solid #E5E5E5; } .border-r { border-right: 1px solid #E5E5E5; }
.bg-white { background-color: #FFFFFF; }
.bg-neutral-50 { background-color: #FAFAFA; } .bg-neutral-100 { background-color: #F5F5F5; } .bg-neutral-200 { background-color: #E5E5E5; }
.bg-blue-50 { background-color: #EFF6FF; } .bg-blue-100 { background-color: #DBEAFE; } .bg-gray-100 { background-color: #F3F4F6; }
.text-neutral-400 { color: #A3A3A3; } .text-neutral-500 { color: #737373; } .text-neutral-600 { color: #525252; }
.text-neutral-700 { color: #404040; } .text-neutral-900 { color: #171717; }
.text-gray-500 { color: #6B7280; } .text-gray-600 { color: #4B5563; }
.text-brand-blue { color: var(--sz-blue); } .text-orange-700 { color: #C2410C; }
.text-red-600 { color: #DC2626; } .text-green-600 { color: #16A34A; }
"""

# The house "card" -- the reference site's rounded-xl / border-neutral-200 /
# shadow-sm section container (its "How to get a figure" and chart panels
# both use this exact recipe). Studio panes are wrapped in `.sz-card` so the
# sidebar/canvas/chat read as distinct sections instead of bare page flow.
_CARD = """
.sz-card { background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: var(--sz-radius-lg); box-shadow: var(--sz-shadow-sm); padding: 1.25rem; }
.sz-header { background: #FFFFFF; border-bottom: 1px solid #E5E5E5; }
.sz-chat-bubble-user { background: #DBEAFE; }
.sz-chat-bubble-assistant { background: #F5F5F5; }
"""


def theme_css() -> str:
    return _TOKENS + _BASE + _COMPONENTS + _UTILITIES + _CARD


# A class selector is a dot followed by a letter, then class-name chars
# (Tailwind fraction classes such as ``w-1/2`` carry a literal slash). The
# leading-letter requirement skips numeric fragments in declaration values
# like ``.25rem`` or ``rgba(0,0,0,.05)``.
_CLASS_SELECTOR_RE = re.compile(r"\.([A-Za-z][A-Za-z0-9_/-]*)")


def supported_classes() -> frozenset[str]:
    """The set of class names ``theme_css()`` actually defines.

    Derived from the stylesheet itself (not a second hand-maintained list),
    so it can never drift from what the ``<style>`` block ships. This is the
    source of truth the coverage guard checks every component's
    ``.classes(...)`` tokens against -- a class a component uses but that is
    absent here would silently no-op (the exact failure that left the first
    Studio UI unstyled), so ``tests/studio/test_theme_coverage.py`` fails
    loudly instead.
    """
    return frozenset(_CLASS_SELECTOR_RE.findall(theme_css()))
