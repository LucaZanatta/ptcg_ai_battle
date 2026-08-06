from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

try:
    from IPython.display import display
except ImportError:
    display = print


DATASET_SLUG = "ptcg-ai-battle-22-curated-deck-archetypes"
KAGGLE_INPUT_ROOT = Path("/kaggle/input")
required_input_files = {
    "archetypes.csv",
    "decks_long.csv",
    "decks_expanded.csv",
    "validation_report.csv",
    "card_usage.csv",
    "deck_similarity.csv",
}


def discover_dataset_root() -> Path:
    direct_root = KAGGLE_INPUT_ROOT / DATASET_SLUG
    if all((direct_root / name).is_file() for name in required_input_files):
        return direct_root

    if KAGGLE_INPUT_ROOT.exists():
        candidates = sorted(
            {
                candidate.parent
                for candidate in KAGGLE_INPUT_ROOT.rglob("archetypes.csv")
                if all(
                    (candidate.parent / name).is_file()
                    for name in required_input_files
                )
            }
        )
        if len(candidates) == 1:
            return candidates[0]
        mounted_entries = sorted(
            path.relative_to(KAGGLE_INPUT_ROOT).as_posix()
            for path in KAGGLE_INPUT_ROOT.iterdir()
        )
        raise FileNotFoundError(
            "Could not uniquely locate the attached deck dataset. "
            f"Candidates: {candidates}; mounted input entries: {mounted_entries}"
        )

    configured_root = os.environ.get("PTCG_DATASET_DIR")
    local_root = (
        Path(configured_root)
        if configured_root
        else Path("../outputs/ptcg_ai_battle_22_decks_v1/dataset")
    )
    if not all((local_root / name).is_file() for name in required_input_files):
        raise FileNotFoundError(f"Local dataset is incomplete: {local_root}")
    return local_root


DATA_ROOT = discover_dataset_root()
if KAGGLE_INPUT_ROOT.exists():
    ASSET_DIR = Path("/kaggle/working")
else:
    configured_assets = os.environ.get("PTCG_ASSET_DIR")
    ASSET_DIR = (
        Path(configured_assets)
        if configured_assets
        else DATA_ROOT.parent / "discussion" / "assets"
    )

ASSET_DIR.mkdir(parents=True, exist_ok=True)
print(f"Dataset directory: {DATA_ROOT}")



#%%CELL%%

archetypes = pd.read_csv(DATA_ROOT / "archetypes.csv")
decks_long = pd.read_csv(DATA_ROOT / "decks_long.csv")
decks_expanded = pd.read_csv(DATA_ROOT / "decks_expanded.csv")
validation = pd.read_csv(DATA_ROOT / "validation_report.csv")
card_usage = pd.read_csv(DATA_ROOT / "card_usage.csv")
similarity = pd.read_csv(DATA_ROOT / "deck_similarity.csv")

print(
    f"{len(archetypes)} archetypes | "
    f"{len(decks_expanded):,} physical card copies | "
    f"{decks_long['card_id'].nunique()} unique Card IDs"
)



#%%CELL%%

assert archetypes["deck_id"].tolist() == [
    f"EX_{index:02d}" for index in range(1, 23)
]
assert set(validation["validation_status"]) == {"validated"}
assert validation["card_count"].eq(60).all()
assert decks_expanded.groupby("deck_id").size().eq(60).all()
assert len(decks_expanded) == 22 * 60
assert len(similarity) == 22 * 22

diagonal = similarity.query("deck_id_a == deck_id_b")
assert diagonal["weighted_jaccard"].eq(1.0).all()
assert diagonal["cosine_similarity"].eq(1.0).all()

validation_view = validation[
    [
        "deck_id",
        "deck_name",
        "validation_status",
        "source_confidence",
        "card_count",
        "unique_card_count",
    ]
]
display(validation_view)



#%%CELL%%

complexity_order = {"low": 0, "medium": 1, "high": 2}
tempo_colors = {
    "aggressive": "#E76F51",
    "midrange": "#2A9D8F",
    "control": "#457B9D",
    "toolbox": "#8E5EA2",
    "combo": "#E9C46A",
}
prize_markers = {
    "mostly_single": "o",
    "mixed": "s",
    "mostly_multi": "^",
}

plot_archetypes = archetypes.copy()
plot_archetypes["setup_score"] = plot_archetypes["setup_complexity"].map(
    complexity_order
)
plot_archetypes["pilot_score"] = plot_archetypes["pilot_complexity"].map(
    complexity_order
)
plot_archetypes["setup_plot"] = plot_archetypes["setup_score"].astype(float)
plot_archetypes["pilot_plot"] = plot_archetypes["pilot_score"].astype(float)
for _, indexes in plot_archetypes.groupby(
    ["setup_score", "pilot_score"], sort=True
).groups.items():
    ordered_indexes = sorted(indexes, key=lambda index: plot_archetypes.loc[index, "deck_id"])
    count = len(ordered_indexes)
    if count == 1:
        continue
    radius = min(0.24, 0.10 + 0.018 * count)
    angles = np.linspace(0, 2 * np.pi, count, endpoint=False)
    plot_archetypes.loc[ordered_indexes, "setup_plot"] += radius * np.cos(angles)
    plot_archetypes.loc[ordered_indexes, "pilot_plot"] += radius * np.sin(angles)

fig, ax = plt.subplots(figsize=(11, 7))
for (tempo, prize_profile), group in plot_archetypes.groupby(
    ["tempo", "prize_profile"], sort=True
):
    ax.scatter(
        group["setup_plot"],
        group["pilot_plot"],
        s=105,
        color=tempo_colors[tempo],
        marker=prize_markers[prize_profile],
        edgecolor="white",
        linewidth=0.8,
        alpha=0.95,
    )
for row in plot_archetypes.itertuples():
    x_direction = 1 if row.setup_plot >= row.setup_score else -1
    y_direction = 1 if row.pilot_plot >= row.pilot_score else -1
    ax.annotate(
        row.deck_id.replace("_", ""),
        (row.setup_plot, row.pilot_plot),
        xytext=(5 * x_direction, 5 * y_direction),
        textcoords="offset points",
        fontsize=8,
        ha="left" if x_direction > 0 else "right",
        va="bottom" if y_direction > 0 else "top",
    )
ax.set(
    title="22 archetypes: setup burden vs. decision burden",
    xlabel="Setup complexity",
    ylabel="Pilot complexity",
    xticks=[0, 1, 2],
    yticks=[0, 1, 2],
    xticklabels=["Low", "Medium", "High"],
    yticklabels=["Low", "Medium", "High"],
)
ax.grid(alpha=0.18)
tempo_handles = [
    Line2D(
        [0],
        [0],
        marker="o",
        color="none",
        markerfacecolor=color,
        markeredgecolor="white",
        markersize=9,
        label=tempo.title(),
    )
    for tempo, color in tempo_colors.items()
]
prize_handles = [
    Line2D(
        [0],
        [0],
        marker=marker,
        color="none",
        markerfacecolor="#6B7280",
        markersize=8,
        label=profile.replace("_", " ").title(),
    )
    for profile, marker in prize_markers.items()
]
tempo_legend = ax.legend(
    handles=tempo_handles,
    title="Tempo",
    bbox_to_anchor=(1.02, 1.0),
    loc="upper left",
    frameon=False,
    fontsize=8,
)
ax.add_artist(tempo_legend)
ax.legend(
    handles=prize_handles,
    title="Prize profile",
    bbox_to_anchor=(1.02, 0.58),
    loc="upper left",
    frameon=False,
    fontsize=8,
)
fig.tight_layout()
fig.savefig(ASSET_DIR / "archetype_map.png", dpi=180, bbox_inches="tight")
plt.show()



#%%CELL%%

staples = (
    card_usage.query("card_type != 'BASIC_ENERGY'")
    .sort_values(["deck_count", "total_copies", "card_name"], ascending=[False, False, True])
    .head(15)
    .sort_values(["deck_count", "total_copies"], ascending=True)
)

fig, ax = plt.subplots(figsize=(10, 7))
bars = ax.barh(staples["card_name"], staples["deck_count"], color="#457B9D")
ax.bar_label(
    bars,
    labels=[f"{value}/22" for value in staples["deck_count"]],
    padding=3,
    fontsize=8,
)
ax.set(
    title="Most widely shared non-Basic-Energy cards",
    xlabel="Number of decks containing the card",
    ylabel="",
    xlim=(0, 22),
)
ax.grid(axis="x", alpha=0.18)
fig.tight_layout()
fig.savefig(ASSET_DIR / "staple_cards.png", dpi=180, bbox_inches="tight")
plt.show()

display(
    staples[
        [
            "card_name",
            "card_class",
            "deck_count",
            "deck_share",
            "total_copies",
            "average_copies_when_used",
        ]
    ].sort_values(["deck_count", "total_copies"], ascending=False)
)



#%%CELL%%

composition = archetypes.set_index("deck_id")[
    ["pokemon_count", "trainer_count", "energy_count"]
]
composition.columns = ["Pokemon", "Trainer", "Energy"]

fig, ax = plt.subplots(figsize=(12, 6))
composition.plot(
    kind="bar",
    stacked=True,
    ax=ax,
    color=["#2A9D8F", "#457B9D", "#E9C46A"],
    width=0.82,
)
ax.set(
    title="Every deck contains 60 cards, but the mix varies",
    xlabel="Deck",
    ylabel="Physical card copies",
    ylim=(0, 60),
)
ax.legend(ncol=3, frameon=False, loc="upper center")
ax.grid(axis="y", alpha=0.18)
fig.tight_layout()
fig.savefig(ASSET_DIR / "deck_composition.png", dpi=180, bbox_inches="tight")
plt.show()



#%%CELL%%

similarity_matrix = similarity.pivot(
    index="deck_id_a", columns="deck_id_b", values="weighted_jaccard"
).loc[archetypes["deck_id"], archetypes["deck_id"]]

fig, ax = plt.subplots(figsize=(11, 9))
image = ax.imshow(similarity_matrix, cmap="viridis", vmin=0, vmax=1)
ax.set_xticks(range(len(similarity_matrix.columns)))
ax.set_yticks(range(len(similarity_matrix.index)))
ax.set_xticklabels(
    [value.replace("_", "") for value in similarity_matrix.columns],
    rotation=90,
    fontsize=8,
)
ax.set_yticklabels(
    [value.replace("_", "") for value in similarity_matrix.index], fontsize=8
)
ax.set_title("Quantity-aware deck similarity (weighted Jaccard)")
fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Similarity")
fig.tight_layout()
fig.savefig(ASSET_DIR / "deck_similarity.png", dpi=180, bbox_inches="tight")
plt.show()



#%%CELL%%

complexity_score = {"low": 0, "medium": 1, "high": 2}
curriculum = archetypes.assign(
    curriculum_score=archetypes["setup_complexity"].map(complexity_score)
    + archetypes["pilot_complexity"].map(complexity_score)
).sort_values(
    ["curriculum_score", "tempo", "prize_profile", "deck_id"]
)

display(
    curriculum[
        [
            "deck_id",
            "deck_name",
            "tempo",
            "prize_profile",
            "setup_complexity",
            "pilot_complexity",
            "suggested_training_role",
        ]
    ]
)



#%%CELL%%

def greedy_diverse_panel(matrix: pd.DataFrame, size: int = 6) -> list[str]:
    """Select a deterministic low-overlap panel from a similarity matrix."""
    if not 1 <= size <= len(matrix):
        raise ValueError("size must be between 1 and the number of decks")
    off_diagonal_mean = (
        matrix.mask(np.eye(len(matrix), dtype=bool)).mean(axis=1)
    )
    selected = [str(off_diagonal_mean.idxmin())]
    while len(selected) < size:
        candidates = [deck for deck in matrix.index if deck not in selected]
        next_deck = min(
            candidates,
            key=lambda deck: (
                float(matrix.loc[deck, selected].mean()),
                str(deck),
            ),
        )
        selected.append(str(next_deck))
    return selected


panel_ids = greedy_diverse_panel(similarity_matrix, size=6)
coverage_panel = archetypes.set_index("deck_id").loc[panel_ids].reset_index()
print("Example six-deck low-overlap evaluation panel:")
display(
    coverage_panel[
        [
            "deck_id",
            "deck_name",
            "tempo",
            "prize_profile",
            "suggested_training_role",
        ]
    ]
)



#%%CELL%%

controlled_pairs = (
    similarity.query("deck_id_a < deck_id_b")
    .sort_values(
        ["weighted_jaccard", "shared_copies", "deck_id_a", "deck_id_b"],
        ascending=[False, False, True, True],
    )
    .head(10)
)
name_lookup = archetypes.set_index("deck_id")["deck_name"]
controlled_pairs = controlled_pairs.assign(
    deck_a_name=controlled_pairs["deck_id_a"].map(name_lookup),
    deck_b_name=controlled_pairs["deck_id_b"].map(name_lookup),
)
print("High-overlap pairs for controlled deck-change experiments:")
display(
    controlled_pairs[
        [
            "deck_id_a",
            "deck_a_name",
            "deck_id_b",
            "deck_b_name",
            "weighted_jaccard",
            "shared_copies",
        ]
    ]
)



#%%CELL%%

def export_deck(deck_id: str, path: str | Path | None = None) -> list[int]:
    rows = decks_long.query("deck_id == @deck_id").sort_values("card_id")
    if rows.empty:
        raise KeyError(f"Unknown deck_id: {deck_id}")
    card_ids = [
        int(row.card_id)
        for row in rows.itertuples()
        for _ in range(int(row.quantity))
    ]
    if len(card_ids) != 60:
        raise ValueError(f"{deck_id} reconstructed to {len(card_ids)} cards")
    if path is not None:
        Path(path).write_text(
            "\n".join(map(str, card_ids)) + "\n", encoding="utf-8"
        )
    return card_ids


example_deck = export_deck("EX_10")
print(f"EX_10 export: {len(example_deck)} cards; first 10 IDs = {example_deck[:10]}")

