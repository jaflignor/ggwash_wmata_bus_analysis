import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np



METRIC = "Mean Speed (MPH)"
LABEL  = "Change In Average Speed (MPH)"
 
SELECT_PAIRS = [
    ("33",  "D80"), ("70",  "D40"), ("79",  "D4X"), ("90",  "C53"),
    ("92",  "C53"), ("A2",  "C13"), ("A6",  "C13"), ("A8",  "C13"),
    ("B2",  "C41"), ("H2",  "C61"), ("H4",  "C61"), ("S2",  "D60"),
    ("S9",  "D6X"), ("V2",  "C31"), ("V4",  "C31"), ("W4",  "C21"),
    ("X2",  "D20"),
]
 
LOWER_IS_BETTER = False
 
GOOD_COLOR  = "#1D9E75"
BAD_COLOR   = "#D85A30"
ZERO_COLOR  = "#B4B2A9"
TEXT_COLOR  = "#000000"
MUTED       = "#888780"
 
df_full = pd.read_csv("augmented_route_df_weekday_20260630.csv")
df = df_full[df_full["metric"] == METRIC].copy()
 
pair_set = {(str(a), str(b)) for a, b in SELECT_PAIRS}
df = df[df.apply(lambda r: (str(r["pre_route_id"]), str(r["post_route_id"])) in pair_set, axis=1)]
 
if df.empty:
    raise ValueError(f"No rows found for metric='{METRIC}' with selected routes.")
 
agg = df[["pre_route_id", "post_route_id", "pre_value", "post_value", "corridor"]].copy()
agg["label"] = agg["pre_route_id"].astype(str) + " → " + agg["post_route_id"].astype(str)
agg["delta"] = agg["post_value"] - agg["pre_value"]
agg["pct_change"] = (agg["delta"] / agg["pre_value"]) * 100

 
agg = agg.sort_values("pct_change", ascending=True)
 
def is_improvement(pct):
    return pct > 0 if not LOWER_IS_BETTER else pct < 0
 
n = len(agg)
fig_h = max(4, n * 0.52 + 1.8)
fig, ax = plt.subplots(figsize=(11, 8.5)) 
y_positions = np.arange(n)
colors = [GOOD_COLOR if is_improvement(p) else BAD_COLOR for p in agg["pct_change"]]
 
bars = ax.barh(
    y_positions,
    agg["pct_change"],
    color=colors,
    height=0.6,
    zorder=2
)
 
ax.axvline(0, color="#444441", linewidth=0.8, zorder=3)
 
for i, (_, row) in enumerate(agg.iterrows()):
    pct = row["pct_change"]
    improved = is_improvement(pct)
    label_x = pct + (0.3 if pct >= 0 else -0.3)
    ha = "left" if pct >= 0 else "right"
    col = GOOD_COLOR if improved else BAD_COLOR
    ax.text(label_x, i, f"{pct:+.1f}%", va="center", ha=ha,
            fontsize=8, color=col)
 
ax.set_yticks(y_positions)
ax.set_yticklabels(agg["label"], fontsize=11, color=TEXT_COLOR)
ax.set_xlabel(LABEL, fontsize=10, color=TEXT_COLOR, labelpad=8)
ax.tick_params(axis="x", colors=TEXT_COLOR, labelsize=9)
ax.tick_params(axis="y", length=0)
 
 
ax.set_title(
    "Changes in Average Speed for High Frequency Routes\nDecember 2024 – December 2025",
    fontsize=13, color=TEXT_COLOR, pad=12, loc="center"
)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#D3D1C7")
 
ax.xaxis.grid(True, color="#E8E6DF", linewidth=0.5, zorder=0)
ax.set_axisbelow(True)
 
x_abs_max = agg["pct_change"].abs().max()
ax.set_xlim(-x_abs_max * 1.5, x_abs_max * 1.5) 
legend_elements = [
    mpatches.Patch(facecolor=GOOD_COLOR, label="Speed increased"),
    mpatches.Patch(facecolor=BAD_COLOR,  label="Speed decreased"),
]
ax.legend(handles=legend_elements, fontsize=8, frameon=False,
          loc="lower right", labelcolor=TEXT_COLOR)
 
fig.text(
    0.12, -0.02,
    "Note: Each row constitues route before and after the redesign.\nRoutes can be repeated twice if route has multiple pre-design routes.",
    fontsize=7, color=TEXT_COLOR, ha="left"
)




###Number of Stops
METRIC = "Unique Stops"
LABEL  = "Number of Unique Bus Stops on Route"

SELECT_PAIRS = [
    ("33",  "D80"), ("70",  "D40"), ("79",  "D4X"), ("90",  "C53"),
    ("92",  "C53"), ("A2",  "C13"), ("A6",  "C13"), ("A8",  "C13"),
    ("B2",  "C41"), ("H2",  "C61"), ("H4",  "C61"), ("S2",  "D60"),
    ("S9",  "D6X"), ("V2",  "C31"), ("V4",  "C31"), ("W4",  "C21"),
    ("X2",  "D20"),
]

PRE_COLOR  = "#D85A30"
POST_COLOR = "#1D9E75"
TEXT_COLOR = "#000000"
GRAY       = "#B4B2A9"

df_full = pd.read_csv("augmented_route_df_weekday_20260630.csv")
df = df_full[df_full["metric"] == METRIC].copy()

pair_set = {(str(a), str(b)) for a, b in SELECT_PAIRS}
df = df[df.apply(lambda r: (str(r["pre_route_id"]), str(r["post_route_id"])) in pair_set, axis=1)]

if df.empty:
    raise ValueError(f"No rows found for metric='{METRIC}' with selected routes.")

agg = df[["pre_route_id", "post_route_id", "pre_value", "post_value", "corridor"]].copy()
agg["label"] = agg["pre_route_id"].astype(str) + " → " + agg["post_route_id"].astype(str)
agg["delta"] = agg["post_value"] - agg["pre_value"]

agg = agg.sort_values("pre_value", ascending=True).reset_index(drop=True)
#agg = agg.sort_values("delta", ascending=True).reset_index(drop=True)
n = len(agg)
fig, ax = plt.subplots(figsize=(11, 8.5))
y_positions = np.arange(n)

for i, row in agg.iterrows():
    ax.plot(
        [row["pre_value"], row["post_value"]],
        [i, i],
        color=GRAY, linewidth=1.2, zorder=1
    )
    ax.scatter(row["pre_value"],  i, color=PRE_COLOR,  zorder=2, s=60)
    ax.scatter(row["post_value"], i, color=POST_COLOR, zorder=2, s=60)

    # label the delta at the end of the line
    x_label = max(row["pre_value"], row["post_value"]) + 0.5
    delta_color = POST_COLOR if row["delta"] >= 0 else PRE_COLOR
    ax.text(x_label, i, f"{row['delta']:+.0f}", va="center", ha="left",
            fontsize=8, color=delta_color)

ax.set_yticks(y_positions)
ax.set_yticklabels(agg["label"], fontsize=11, color=TEXT_COLOR)
ax.set_xlabel(LABEL, fontsize=10, color=TEXT_COLOR, labelpad=8)
ax.tick_params(axis="x", colors=TEXT_COLOR, labelsize=9)
ax.tick_params(axis="y", length=0)

ax.set_title(
    "Number of Stops per Route Before and After Redesign\nDecember 2024 – December 2025",
    fontsize=13, color=TEXT_COLOR, pad=12, loc="center", linespacing=1.2
)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#D3D1C7")

ax.xaxis.grid(True, color="#E8E6DF", linewidth=0.5, zorder=0)
ax.set_axisbelow(True)

legend_elements = [
    mpatches.Patch(facecolor=PRE_COLOR,  label="Before redesign"),
    mpatches.Patch(facecolor=POST_COLOR, label="After redesign"),
]
ax.legend(handles=legend_elements, fontsize=8, frameon=False,
          loc="lower right", labelcolor=TEXT_COLOR)

fig.text(
    0.12, -0.02,
    "Note: Each row constitutes a route before and after the redesign.\nRoutes can be repeated if multiple pre-redesign routes map to the same post-redesign route.\nFor example, the C53 is a combination of both the 90 and 92 and shows different stopping patterns.",
    fontsize=7, color=TEXT_COLOR, ha="left"
)

