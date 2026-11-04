"""``python -m sprezzature_figures`` runs the same click group as ``sprezzature-figures``.

The argparse ``main`` of ``make_figure.py`` used to answer
``python -m sprezzature_figures.make_figure KIND``; it was removed with the
rest of the argparse front door, and a module run that silently does nothing
is worse than one that does not exist. This is the one module entry point.
"""

from sprezzature_figures.cli import main

if __name__ == "__main__":
    main(prog_name="sprezzature-figures")
