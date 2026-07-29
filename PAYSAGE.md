# Paysage

## Place de sprezzature-figures dans l'écosystème

`sprezzature-figures` est le module de visualisation de données de la suite [sprezzature](https://github.com/sprezzature/sprezzature) — un ensemble de paquets Python pour produire du contenu web de qualité publication.

```
suite sprezzature
├── sprezzature-figures   ← ce paquet  (84 types de graphiques)
├── sprezzature-colors    (palettes de couleurs accessibles)
├── sprezzature-vision    (génération de textes alternatifs, légendes)
├── sprezzature-audio     (transcription audio, traduction de sous-titres)
├── sprezzature-publish   (réécriture en langage clair, balises méta, SEO)
└── best-engine-ai-helper (détection matériel LLM/VLM et sélection de modèles)
```

## Alternatives

| Outil | Quand le préférer |
|-------|-------------------|
| Matplotlib | Tracés Python polyvalents ; contrôle bas niveau. |
| Vega-Lite (brut) | Graphique unique en JavaScript ; pas de wrapper Python nécessaire. |
| Plotly | Graphiques interactifs Python avec l'écosystème Plotly complet. |
| Altair | Wrapper Vega-Lite avec API native pandas. |
| Seaborn | Graphiques statistiques intégrés à pandas. |
| D3.js | Animations SVG personnalisées ; contrôle complet du navigateur. |
| Observable Plot | Alternative JS moderne à D3 pour l'analyse exploratoire. |

## Quand choisir sprezzature-figures

- Vous avez besoin de 84 types de graphiques prêts à l'emploi via une API unique et cohérente.
- Vous voulez que `make_figure("treemap", data)` fonctionne sans lire de documentation.
- Vous avez besoin de la boucle Ralph Eyeball pour le contrôle qualité visuel automatisé.
- Votre production doit respecter les standards sprezzature (WRITING.md, CODING.md).
- Vous construisez un pipeline qui intègre des figures dans une publication web.
