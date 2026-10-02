"""Talk figures for EEAI 2026 (02.10.2026). Every number is from docs/TALK-PACK-20260922.md §5
(itself reproducible from smoke-tests-20260921/*.json). Run: python make_figures.py
Outputs PNG + SVG + PDF next to this file. Optional: extra_models.json {"label": {"A": x, "B": y, "C": z, "D": w}}
(e.g. the gpt-5.4-nano run) is merged into figure 1 if present.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
INK, MUTED, ACCENT, WARN = "#1b1b1f", "#8a8a93", "#1f6f8b", "#c8502a"

# Fig. 1 — accuracy on 100 date-anchored tax-law questions (fiscal-fr-bench), per evidence condition.
CONDS = ["A *\ncompressed history,\nthen answer", "B\ntoday's version\n(static RAG)", "C\nversion in force\n(benchmark oracle)",
         "D\none typed figure per version,\ndata own the dates"]
ACC = {"gpt-5.4": [77, 3, 91, 99], "gpt-5.4-mini": [52, 3, 90, 99]}
NOTES: list[str] = []
extra = HERE / "extra_models.json"
if extra.exists():
    for label, v in json.loads(extra.read_text(encoding="utf-8")).items():
        ACC[label] = [v["A"], v["B"], v["C"], v["D"]]
        if v.get("note"):
            NOTES.append(f"{label}: {v['note']}")
# Three independent judges: share of WRONG answers (gpt-5.4 answers) unanimously certified as supported.
UNANIMOUS_WRONG = {"A": (9, 23), "B": (2, 97), "C": (5, 9)}


def fig_accuracy() -> None:
    fig, ax = plt.subplots(figsize=(12, 6.4), dpi=200)
    n = len(ACC)
    width = 0.8 / n
    palette = [ACCENT, "#5aa9c4", "#a7cfdd", "#d9ebf1"][:n]
    for i, (label, vals) in enumerate(ACC.items()):
        xs = [j + (i - (n - 1) / 2) * width for j in range(4)]
        bars = ax.bar(xs, vals, width * 0.95, label=label, color=palette[i], edgecolor="none")
        for b, v in zip(bars, vals, strict=True):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, str(v), ha="center", va="bottom",
                    fontsize=9, color=INK)
    ax.set_xticks(range(4), CONDS, fontsize=10)
    ax.set_ylim(0, 132)
    ax.set_ylabel("correct answers out of 100", fontsize=10)
    ax.set_title("The evidence path decides, not the model size", fontsize=13, color=INK, loc="left", pad=28)
    ax.text(0, 1.02, "100 date-anchored questions on the versioned French tax code (fiscal-fr-bench); "
            "deterministic scoring, no human labels",
            transform=ax.transAxes, fontsize=8.5, color=MUTED)
    for key, j in (("A", 0), ("B", 1), ("C", 2)):
        k, m = UNANIMOUS_WRONG[key]
        ax.text(j, 128, f"3 judges unanimously certify\n{k}/{m} ({100 * k // m}%) of the WRONG answers",
                ha="center", va="top", fontsize=7.2, color=WARN if key == "A" else MUTED)
    ax.text(3, 128, "verifier = the resolved value:\ncatches 16/16 the judges passed,\n0 false alarms",
            ha="center", va="top", fontsize=7.2, color=ACCENT)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0.0, 0.84))
    if NOTES:
        ax.text(0, -0.2, "* " + " · ".join(NOTES) + ".\nRepeat runs (gpt-5.4-mini, ×3): D 99 / 99 / 99 — same single miss; "
                "C 90 / 90 / 91; B 3 / 3 / 3; A 52 / 66 / 60 — the compression step itself is stochastic.",
                transform=ax.transAxes, fontsize=7.5, color=MUTED, va="top")
    fig.tight_layout()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(HERE / f"fig1-evidence-path.{ext}")
    plt.close(fig)


def fig_agreement() -> None:
    """Fig. 2 — agreement is uninformative exactly when the degradation is invisible."""
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200)
    rows = [
        ("natural summarizer errors\n(AggreFact, visible hallucinations)", 3, 60),
        ("visibly stale version\n(today's text, date mismatch)", 2, 97),
        ("injected restriction drop\n(stale value asserted as current)", 60, 100),
        ("compressed intermediate\n(off by one version)", 39, 100),
    ]
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [MUTED, MUTED, WARN, WARN]
    bars = ax.barh(labels, vals, color=colors, edgecolor="none")
    for b, v, note in zip(bars, vals, ["0/28, 2/32 of 64", "2 of 97", "5 of 9 · 7 of 10", "9 of 23"], strict=True):
        ax.text(v + 1, b.get_y() + b.get_height() / 2, f"{v}%  ({note})", va="center", fontsize=8.5, color=INK)
    ax.set_xlim(0, 100)
    ax.set_xlabel("wrong answers that three different models unanimously certified", fontsize=9)
    ax.set_title("A second model is not a second opinion\n— when the lie is invisible in the evidence",
                 fontsize=12, color=INK, loc="left")
    ax.invert_yaxis()
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", labelsize=8.5)
    fig.tight_layout()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(HERE / f"fig2-agreement.{ext}")
    plt.close(fig)


def fig_tomorrow() -> None:
    """Fig. 3 — predictive advice: recorded future vs invented future."""
    fig, ax = plt.subplots(figsize=(7.5, 3.8), dpi=200)
    groups = ["future version RECORDED (47 pairs)", "future NOT recorded (78 pairs)"]
    model = [38, 72]
    resolve = [45, 0]
    x = range(2)
    ax.bar([i - 0.2 for i in x], model, 0.38, label="model reading the full history", color=MUTED)
    ax.bar([i + 0.2 for i in x], resolve, 0.38, label="deterministic resolve", color=ACCENT)
    ax.set_xticks(list(x), groups, fontsize=9.5)
    ax.text(-0.2, 40, "38 correct", ha="center", fontsize=9)
    ax.text(0.2, 47, "45 correct", ha="center", fontsize=9, color=ACCENT)
    ax.text(0.8, 74, "72 invented figures", ha="center", fontsize=9, color=WARN)
    ax.text(1.2, 3, "declines (\"expired\")\n72 times", ha="center", fontsize=9, color=ACCENT)
    ax.set_ylim(0, 85)
    ax.set_ylabel("answers", fontsize=9)
    ax.set_title("Tomorrow: every \"will apply\" has a recorded event behind it — or is not said",
                 fontsize=12, color=INK, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(HERE / f"fig3-tomorrow.{ext}")
    plt.close(fig)


def fig_jev() -> None:
    """Fig. 4 — the calibrated decision model (TypeSafe Jev, 02.10) is honest about its input, not about the lost original."""
    fig, ax = plt.subplots(figsize=(8.5, 4.4), dpi=200)
    conds = ["A  compressed history\n(invisible lie)", "B  today's version\n(visible staleness)",
             "C  version in force\n(answerer's date errors)"]
    certified = [10 / 19 * 100, 2 / 97 * 100, 9 / 9 * 100]
    labels = ["10 of 19", "2 of 97", "9 of 9"]
    conf = ["mean P(supported) 0.53", "mean P(supported) 0.07", "mean P(supported) 0.89"]
    bars = ax.bar(conds, certified, 0.55, color=[WARN, MUTED, WARN], edgecolor="none")
    for b, lab, c in zip(bars, labels, conf, strict=True):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, f"{lab}\n{c}", ha="center", va="bottom",
                fontsize=9, color=INK)
    ax.set_ylim(0, 125)
    ax.set_ylabel("WRONG answers the calibrated judge certifies, %", fontsize=9)
    ax.set_title("Calibration is honesty about the input — not about the lost original", fontsize=12, color=INK, loc="left", pad=26)
    ax.text(0, 1.02, "TypeSafe Jev (System One, jev-1.13.0) as a 4th judge over the same 100×3 stored answers; 300 verdicts, $0.025, ~90 s",
            transform=ax.transAxes, fontsize=8, color=MUTED)
    ax.text(0.5, 0.86, "Of the 9 invisible lies the three LLM judges passed unanimously, Jev signed 8.\n"
            "The resolved value catches all 9 — with no model at all.",
            transform=ax.transAxes, ha="center", fontsize=9, color=ACCENT)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="x", labelsize=9)
    fig.tight_layout()
    for ext in ("png", "svg", "pdf"):
        fig.savefig(HERE / f"fig4-calibrated-judge.{ext}")
    plt.close(fig)


if __name__ == "__main__":
    fig_accuracy()
    fig_agreement()
    fig_tomorrow()
    fig_jev()
    print("figures written to", HERE)
