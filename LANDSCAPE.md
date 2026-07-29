# Landscape

## How sprezzature-figures fits in the ecosystem

`sprezzature-figures` is the data-visualisation skill of the [sprezzature](https://harchaoui.org/warith/sprezzature/) suite — a collection of Python packages that help build publication-quality web content.

```
sprezzature suite
├── sprezzature-figures   ← this package  (84 chart types)
├── sprezzature-colors    (accessible colour palettes)
├── sprezzature-vision    (alt-text generation, image captioning)
├── sprezzature-audio     (audio transcription, caption translation)
├── sprezzature-publish   (plain-language rewrite, meta tags, SEO)
└── best-engine-ai-helper (LLM/VLM hardware detection and model selection)
```

## Alternatives

| Tool | When to prefer it |
|------|--------------------|
| Matplotlib | General-purpose Python plotting; lower-level control. |
| Vega-Lite (raw) | Single chart in JavaScript; no Python wrapper needed. |
| Plotly | Interactive charts in Python with full Plotly ecosystem. |
| Altair | Vega-Lite wrapper with pandas-native API. |
| Seaborn | Statistical charts tightly integrated with pandas. |
| D3.js | Custom SVG animations; full browser control. |
| Observable Plot | Modern JS alternative to D3 for exploratory analysis. |

## When to choose sprezzature-figures

- You need 84 ready-to-use chart types with a single consistent API.
- You want `make_figure("treemap", data)` to just work without reading docs.
- You need the Ralph Eyeball Loop for autonomous visual QA.
- Your output must meet the sprezzature publication standards (WRITING.md, CODING.md).
- You are building a pipeline that feeds figures into a web publication.
