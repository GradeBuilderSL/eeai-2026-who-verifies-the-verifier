# Figures

`python make_figures.py` redraws all four from the numbers in `results/` (PNG, SVG, PDF). `extra_models.json`
adds the gpt-5.4-nano bars to figure 1.

- `fig1-evidence-path` — accuracy per evidence condition and model: the evidence path decides, not the model size.
- `fig2-agreement` — share of wrong answers three different models certified unanimously: a second model is not a second opinion when the lie is invisible.
- `fig3-tomorrow` — recorded future vs invented future.
- `fig4-calibrated-judge` — a calibrated decision model (TypeSafe Jev) as the fourth judge.

CC BY 4.0.
