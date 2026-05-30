"""
Description: Small analysis of WMATA bus system
Jacob Flignor
March 2026
"""

# ── Imports ───────────────────────────────────────────
import gtfs_kit as gk
import pathlib as pl
import pandas as pd
import warnings
import glob
from datetime import datetime
import os
from pandas.errors import PerformanceWarning
from functools import reduce


warnings.filterwarnings(
    "ignore",
    category=PerformanceWarning
)


date_str = datetime.now().strftime("%Y%m%d")
# ── Helper Time Function ─────────────────────────────────────────

def split_dates_by_type(feed):
    """
    Returns dict with keys 'weekday', 'saturday', 'sunday', 'weekend'
    mapping to lists of YYYYMMDD date strings.
    """
    all_dates = feed.get_dates()
    result = {"weekday": [], "saturday": [], "sunday": []}
    for d in all_dates:
        dt = datetime.strptime(str(d), "%Y%m%d")
        dow = dt.weekday()  
        if dow < 5:
            result["weekday"].append(d)
        elif dow == 5:
            result["saturday"].append(d)
        else:
            result["sunday"].append(d)
    result["weekend"] = result["saturday"] + result["sunday"]
    return result

def filter_feed_by_day_type(feed, day_type="weekday"):
    date_groups = split_dates_by_type(feed)
    dates = date_groups[day_type]
    return gk.restrict_to_dates(feed, dates)

def load_xwalks(corridor_type="general"):
    suffix = f"_{corridor_type}"

    x_walk = pd.read_csv(f"data/wmata_bus_xwalk{suffix}.csv")
    x_walk_long = (
        x_walk
        .melt(
            id_vars="old_name",
            value_vars=x_walk.filter(like="new_").columns,
            var_name="name",
            value_name="new_name",
        )
        .drop(columns="name")
        .drop_duplicates()
        .dropna()
    )

    corridor_map_raw = pd.read_csv(f"data/wmata_corridor_xwalk{suffix}.csv")

    return x_walk_long, corridor_map_raw


# ── Prepare Ridership data ─────────────────────────────────────────
def load_ridership(data_dir="data/ridership"):
    def extract_date(filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        return datetime.strptime(name, "%m-%Y")

    files = sorted(glob.glob(f"{data_dir}/*.csv"), key=extract_date)

    def read_and_sum(f):
        df = pd.read_csv(f, encoding="utf-16", sep="\t", header=1)
        df.columns = df.columns.str.strip()
        df["file_month"] = os.path.splitext(os.path.basename(f))[0]
        df["total_ridership"] = (
            df[["Weekday", "Saturday", "Sunday"]]
            .replace({",": ""}, regex=True)
            .apply(pd.to_numeric, errors="coerce")
            .sum(axis=1)
        )
        return df

    combined = pd.concat([read_and_sum(f) for f in files], ignore_index=True)
    combined["file_month"] = combined["file_month"].apply(extract_date)
    return combined, files


def agg_ridership(df, prefix, n_months):
    monthly = (
        df.groupby(["Route", "file_month"], as_index=False)
        .agg(monthly_total=("total_ridership", "sum"))
    )
    return (
        monthly.groupby("Route", as_index=False)
        .agg(
            **{f"{prefix}_total_ridership":  ("monthly_total", "sum")},
            **{f"{prefix}_median_ridership": ("monthly_total", "median")},
        )
        .assign(**{f"{prefix}_monthly_ridership": lambda d: d[f"{prefix}_total_ridership"] / n_months})
    )

def build_ridership_comp(x_walk_long, level="route", corridor_map=None, pre_n=7, post_n=6, data_dir="data/ridership"):
    combined, files = load_ridership(data_dir)
    dates = combined["file_month"].drop_duplicates().sort_values()
    pre_months  = dates.iloc[:pre_n].tolist()
    post_months = dates.iloc[pre_n:].tolist()
    pre_agg  = agg_ridership(combined[combined["file_month"].isin(pre_months)],  prefix="pre",  n_months=pre_n)
    post_agg = agg_ridership(combined[combined["file_month"].isin(post_months)], prefix="post", n_months=post_n)
    comp = (
        post_agg
        .merge(x_walk_long, how="left", left_on="Route", right_on="new_name")
        .drop(columns="Route")
        .merge(pre_agg, how="outer", left_on="old_name", right_on="Route")
        .drop(columns="Route")
        .rename(columns={"old_name": "pre_route_id", "new_name": "post_route_id"})
    )
    if level == "route":
        return comp
    if level == "corridor":
        if corridor_map is None:
            raise ValueError("corridor_map is required when level='corridor'")
        comp_mapped = comp.merge(
            corridor_map[["pre_route_id", "post_route_id", "corridor"]],
            on=["pre_route_id", "post_route_id"], how="left"
        )
        pre_ridership = (
            comp_mapped.drop_duplicates(subset=["corridor", "pre_route_id"])
            .groupby("corridor", as_index=False)
            .agg(pre_total_ridership=("pre_total_ridership", "sum"))
            .assign(pre_monthly_ridership=lambda d: d["pre_total_ridership"] / pre_n)
        )
        post_ridership = (
            comp_mapped.drop_duplicates(subset=["corridor", "post_route_id"])
            .groupby("corridor", as_index=False)
            .agg(post_total_ridership=("post_total_ridership", "sum"))
            .assign(post_monthly_ridership=lambda d: d["post_total_ridership"] / post_n)
        )
        return (
            pre_ridership
            .merge(post_ridership, on="corridor", how="outer")
            .assign(
                pre_corridor_id=lambda d: d["corridor"],
                post_corridor_id=lambda d: d["corridor"],
            )
            .drop(columns="corridor")
        )

def agg_ridership_by_type(data_dir="data/ridership"):
    def extract_date(filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        return datetime.strptime(name, "%m-%Y")

    def read_raw(f):
        df = pd.read_csv(f, encoding="utf-16", sep="\t", header=1)
        df.columns = df.columns.str.strip()
        df["file_month"] = os.path.splitext(os.path.basename(f))[0]
        for col in ["Weekday", "Saturday", "Sunday"]:
            df[col] = (
                df[col]
                .replace({",": ""}, regex=True)
                .pipe(pd.to_numeric, errors="coerce")
            )
        return df

    files = sorted(glob.glob(f"{data_dir}/*.csv"), key=extract_date)
    raw = pd.concat([read_raw(f) for f in files], ignore_index=True)
    raw["file_month"] = raw["file_month"].apply(extract_date)
    return raw

def build_ridership_comp_by_type(
    x_walk_long,
    day_type="weekday",
    level="route",
    corridor_map=None,
    pre_n=7,
    post_n=6,
):
    raw = agg_ridership_by_type()
    dates = raw["file_month"].drop_duplicates().sort_values()
    pre_months  = dates.iloc[:pre_n].tolist()
    post_months = dates.iloc[pre_n:].tolist()

    if day_type == "weekday":
        cols = ["Weekday"]
    elif day_type == "saturday":
        cols = ["Saturday"]
    elif day_type == "sunday":
        cols = ["Sunday"]
    elif day_type == "weekend":
        cols = ["Saturday", "Sunday"]
    else:
        raise ValueError("day_type must be 'weekday', 'saturday', 'sunday', or 'weekend'")

    raw["type_ridership"] = raw[cols].sum(axis=1)

    def agg_typed(df, prefix, n_months):
        monthly = (
            df.groupby(["Route", "file_month"], as_index=False)
            .agg(monthly_total=("type_ridership", "sum"))
        )
        return (
            monthly.groupby("Route", as_index=False)
            .agg(
                **{f"{prefix}_total_ridership":  ("monthly_total", "sum")},
                **{f"{prefix}_median_ridership": ("monthly_total", "median")},
            )
            .assign(**{f"{prefix}_monthly_ridership": lambda d: d[f"{prefix}_total_ridership"] / n_months})
        )

    pre_agg  = agg_typed(raw[raw["file_month"].isin(pre_months)],  "pre",  pre_n)
    post_agg = agg_typed(raw[raw["file_month"].isin(post_months)], "post", post_n)

    comp = (
        post_agg
        .merge(x_walk_long, how="left", left_on="Route", right_on="new_name")
        .drop(columns="Route")
        .merge(pre_agg, how="outer", left_on="old_name", right_on="Route")
        .drop(columns="Route")
        .rename(columns={"old_name": "pre_route_id", "new_name": "post_route_id"})
    )

    if level == "route":
        return comp
    if level == "corridor":
        if corridor_map is None:
            raise ValueError("corridor_map required when level='corridor'")
        comp_mapped = comp.merge(
            corridor_map[["pre_route_id", "post_route_id", "corridor"]],
            on=["pre_route_id", "post_route_id"], how="left"
        )
        pre_ridership = (
            comp_mapped.drop_duplicates(subset=["corridor", "pre_route_id"])
            .groupby("corridor", as_index=False)
            .agg(pre_total_ridership=("pre_total_ridership", "sum"))
            .assign(pre_monthly_ridership=lambda d: d["pre_total_ridership"] / pre_n)
        )
        post_ridership = (
            comp_mapped.drop_duplicates(subset=["corridor", "post_route_id"])
            .groupby("corridor", as_index=False)
            .agg(post_total_ridership=("post_total_ridership", "sum"))
            .assign(post_monthly_ridership=lambda d: d["post_total_ridership"] / post_n)
        )
        return (
            pre_ridership
            .merge(post_ridership, on="corridor", how="outer")
            .assign(
                pre_corridor_id=lambda d: d["corridor"],
                post_corridor_id=lambda d: d["corridor"],
            )
            .drop(columns="corridor")
        )


# ── Prepare GTFS data ─────────────────────────────────────────
def load_data(path):
    base_dir = pl.Path.cwd()
    full_dir = base_dir / "data" / path
    path = pl.Path(full_dir).resolve()
    feed = gk.read_feed(path, dist_units="mi")
    return feed


# ── Prepare Stops per Route ─────────────────────────────────────────
def count_stops_per_bus_route(feed, prefix, level, corridor_map):

    bus_routes = feed.routes[feed.routes["route_type"] == 3][["route_id", "route_short_name", "route_long_name"]]
    bus_trips = feed.trips[feed.trips["route_id"].isin(bus_routes["route_id"])][["route_id", "trip_id", "direction_id"]]
    bus_stop_times = (
        feed.stop_times[feed.stop_times["trip_id"].isin(bus_trips["trip_id"])]
        [["trip_id", "stop_id", "stop_sequence", "arrival_time"]]
        .merge(bus_trips, on="trip_id")
        .sort_values(["trip_id", "stop_sequence"])
    )

    st = bus_stop_times.copy()
    st["arrival_time"] = pd.to_timedelta(st["arrival_time"])
    trip_stats = (
        st.groupby(["route_id", "direction_id", "trip_id"])
        .agg(
            num_stops=("stop_id", "nunique"),
            trip_duration_hrs=("arrival_time", lambda x: (x.max() - x.min()).total_seconds() / 3600)
        )
        .reset_index()
    )
    trip_stats["stops_per_hour"] = trip_stats["num_stops"] / trip_stats["trip_duration_hrs"].replace(0, float("nan"))

    if level == "corridor":
        route_col = f"{prefix}_route_id"

        stop_counts = (
            bus_stop_times
            .merge(corridor_map[["pre_route_id", "post_route_id", "corridor"]],
                   left_on="route_id", right_on=route_col, how="left")
            .drop_duplicates(subset=["trip_id", "stop_id", "corridor"])  
            .groupby("corridor")["stop_id"]
            .nunique()
            .reset_index()
            .rename(columns={"stop_id": "num_unique_stops"})
        )

        stops_per_hour = (
            trip_stats
            .merge(corridor_map[["pre_route_id", "post_route_id", "corridor"]],
                   left_on="route_id", right_on=route_col, how="left")
            .drop_duplicates(subset=["route_id", "direction_id", "trip_id", "corridor"])
            .groupby("corridor")["stops_per_hour"]
            .mean()
            .reset_index()
        )

        result = (
            stop_counts.merge(stops_per_hour, on="corridor")
            .rename(columns={
                "corridor":         f"{prefix}_corridor_id",
                "num_unique_stops": f"{prefix}_num_unique_stops",
                "stops_per_hour":   f"{prefix}_stops_per_hour",
            })
        )

    else:
        stop_counts = (
            bus_stop_times
            .groupby(["route_id", "direction_id"])["stop_id"]
            .nunique()
            .reset_index()
            .groupby("route_id")["stop_id"]
            .mean()
            .reset_index()
        )
        stops_per_hour = (
            trip_stats.groupby(["route_id", "direction_id"])["stops_per_hour"]
            .mean()
            .reset_index()
            .groupby("route_id")["stops_per_hour"]
            .mean()
            .reset_index()
        )
        result = (
            stop_counts.merge(stops_per_hour, on="route_id")
            .rename(columns={
                "route_id":       f"{prefix}_route_id",
                "stop_id":        f"{prefix}_num_unique_stops",
                "stops_per_hour": f"{prefix}_stops_per_hour",
            })
        )

    return result

def build_trip_comp(pre_feed, post_feed, x_walk_long, level="route", corridor_map=None):

    pre_trips  = count_stops_per_bus_route(pre_feed,  prefix="pre",  level=level, corridor_map=corridor_map)
    post_trips = count_stops_per_bus_route(post_feed, prefix="post", level=level, corridor_map=corridor_map)

    pre_id  = f"pre_{level}_id"
    post_id = f"post_{level}_id"

    if level == "route":
        return (
            post_trips
            .merge(x_walk_long, how="left", left_on=post_id, right_on="new_name")
            .drop(columns=post_id)
            .merge(pre_trips, how="outer", left_on="old_name", right_on=pre_id)
            .drop(columns=pre_id)
            .rename(columns={"old_name": pre_id, "new_name": post_id})
        )

    return post_trips.merge(pre_trips, left_on=post_id, right_on=pre_id, how="outer")

# ── GTFS Summary Stats ─────────────────────────────────────────
def route_level_summary_stats(feed, day_type="weekday"):
    date_groups = split_dates_by_type(feed)
    dates = date_groups[day_type]
    route_stats = gk.routes.compute_route_stats(feed, dates)
    return route_stats


def process_gtfs_stats(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df["start_time_td"] = pd.to_timedelta(df["start_time"])
    df["end_time_td"]   = pd.to_timedelta(df["end_time"])
    df["service_span"]  = (df["end_time_td"] - df["start_time_td"]).dt.total_seconds() / 60
    min_date = df["date"].min()
    max_date = df["date"].max()
    num_days  = (max_date - min_date).days + 1
    num_weeks = num_days / 7
    return df, num_days, num_weeks


# ── Aggregate GTFS Stats (route or corridor) ─────────────────────────────────────────
def aggregate_stats(df, prefix, num_weeks, level="route", corridor_map=None):
    # if level == "corridor":
    #     if corridor_map is None:
    #         raise ValueError("corridor_map is required when level='corridor'")
    #     df = df.merge(corridor_map, left_on="route_id", right_on=f"{prefix}_route_id", how="left")
    #     df = df.drop_duplicates(subset=["route_id", "date", "corridor"])  # add this
    #     group_col = "corridor"
    # elif level == "route":
    #     group_col = "route_id"
    # else:
    #     raise ValueError("level must be 'route' or 'corridor'")
        
        
    if level == "corridor":
        if corridor_map is None:
            raise ValueError("corridor_map is required when level='corridor'")
    
        corridor_lookup = (
            corridor_map[["corridor", f"{prefix}_route_id"]]
            #.drop_duplicates()
        )
        df = df.merge(corridor_lookup, left_on="route_id", right_on=f"{prefix}_route_id", how="left")
    
        df = df.drop_duplicates(subset=["corridor", "route_id", "date"])        
        group_col = "corridor"
        
    elif level == "route":
        group_col = "route_id"
    else:
        raise ValueError("level must be 'route' or 'corridor'")
    

    df["distance_per_trip"] = df["service_distance"] / df["num_trips"]
    df = df.copy().reset_index(drop=True)

    if level == "corridor":
        daily = (
            df.groupby([group_col, "date"], as_index=False)
            .agg(
                daily_trips=("num_trips",         "sum"),
                total_distance=("service_distance","sum"),
                total_duration=("service_duration","sum"),
                corridor_start=("start_time_td",  "min"),
                corridor_end=("end_time_td",       "max"),
            )
            .assign(
                corridor_speed=lambda d: d["total_distance"] / d["total_duration"],
                corridor_span=lambda d: (
                    (d["corridor_end"] - d["corridor_start"])
                    .dt.total_seconds() / 60
                ),
            )
        )

        return (
            daily.groupby(group_col, as_index=False)
            .agg(
                **{f"{prefix}_mean_service_span":    ("corridor_span",  "mean")},
                **{f"{prefix}_median_service_speed": ("corridor_speed", "median")},
                **{f"{prefix}_mean_trips":           ("daily_trips",    "mean")},
                **{f"{prefix}_median_trips":         ("daily_trips",    "median")},
            )
            .rename(columns={group_col: f"{prefix}_corridor_id"})
        )

    # ── Route level ───────────────────────────────────────────
    agg_dict = {
        f"{prefix}_mean_headway":         ("mean_headway",  "mean"),
        f"{prefix}_median_headway":       ("mean_headway",  "median"),
        f"{prefix}_sd_headway":           ("mean_headway",  "std"),
        f"{prefix}_min_headway":          ("mean_headway",  "min"),
        f"{prefix}_mean_service_span":    ("service_span",  "mean"),
        f"{prefix}_median_service_speed": ("service_speed", "median"),
        f"{prefix}_mean_trips":           ("num_trips",     "mean"),
        f"{prefix}_median_trips":         ("num_trips",     "median"),
    }

    return (
        df.groupby(group_col, as_index=False)
        .agg(**agg_dict)
        .rename(columns={group_col: f"{prefix}_route_id"})
    )


# ── Compare Pre and Post Stats ─────────────────────────────────────────
def compute_pre_post_diff(merged_df, pre_prefix="pre", post_prefix="post", id_cols=None, method="diff"):
    id_cols = id_cols or []
    merged_df = merged_df.copy()

    for col in merged_df.columns:
        if isinstance(col, str) and col.startswith(f"{pre_prefix}_") and col not in id_cols:
            post_col = col.replace(pre_prefix, post_prefix, 1)
            if post_col in merged_df.columns:
                change_col = col.replace(pre_prefix, "change", 1)
                if method == "diff":
                    merged_df[change_col] = merged_df[post_col] - merged_df[col]
                elif method == "pct":
                    merged_df[change_col] = ((merged_df[post_col] - merged_df[col]) / merged_df[col].replace(0, pd.NA)) * 100
                else:
                    raise ValueError("method must be 'diff' or 'pct'")

    return merged_df.drop_duplicates()

# ── Pivot Longer ─────────────────────────────────────────
def pivot_longer(df, id_vars, prefixes):
    join_cols = id_vars + ["metric"]

    melted = [
        df[[*id_vars, *[c for c in df.columns if c.startswith(f"{prefix}_") and c not in id_vars]]]
        .melt(id_vars=id_vars, var_name="metric", value_name=f"{prefix}_value")
        .assign(metric=lambda x, p=prefix: x["metric"].str.removeprefix(f"{p}_"))
        for prefix in prefixes
    ]

    return reduce(lambda l, r: l.merge(r, on=join_cols), melted)

def rename_metrics(df):
    rename_map = {
        "wmean_headway":        "Weighted Mean Headway (Minutes, weighted by Trip Count)",
        "mean_headway":         "Mean Headway (Minutes)",
        "median_headway":       "Median Headway (Minutes)",
        "sd_headway":           "Std Dev Headway (Minutes)",
        "min_headway":          "Min Headway (Minutes)",
        "max_headway":          "Max Headway (Minutes)",
        "wmean_service_span":   "Weighted Mean Service Span (Minutes)",
        "mean_service_span":    "Mean Service Span (Minutes)",
        "median_service_span":  "Median Service Span (Minutes)",
        "sd_service_span":      "Std Dev Service Span (Minutes)",
        "min_service_span":     "Min Service Span (Minutes)",
        "max_service_span":     "Max Service Span (Minutes)",
        "mean_distance":        "Mean Distance (Miles)",
        "median_distance":      "Median Distance (Miles)",
        "wmean_service_speed":  "Weighted Mean Speed (MPH)",
        "mean_service_speed":   "Mean Speed (MPH)",
        "median_service_speed": "Median Speed (MPH)",
        "wmean_trip_duration":  "Weighted Mean Trip Duration (Hours)",
        "mean_trip_duration":   "Mean Trip Duration (Hours)",
        "median_trip_duration": "Median Trip Duration (Hours)",
        "total_trips":          "Total Trips",
        "mean_trips":           "Mean Trips",
        "median_trips":         "Median Trips",
    }
    df = df.copy()
    df["metric"] = df["metric"].replace(rename_map)
    return df


pre_change_path  = "wmata_121524062825.zip"
post_change_path = "wmata_062925121925.zip"

pre_change_feed_all  = load_data(pre_change_path)
post_change_feed_all = load_data(post_change_path)

#LEVEL = "corridor"
#crosswalk_type = "augmented"
#day_type="weekday"

def run_analysis(LEVEL, crosswalk_type, day_type="weekday"):

    print("split by day")
    pre_change_feed  = filter_feed_by_day_type(pre_change_feed_all,  day_type=day_type)
    post_change_feed = filter_feed_by_day_type(post_change_feed_all, day_type=day_type)

    x_walk_long, corridor_map_raw = load_xwalks(corridor_type=crosswalk_type)

    if LEVEL == "corridor":
        corridor_map = (
            corridor_map_raw
            .merge(x_walk_long, how="left", left_on="Route", right_on="new_name")
            .rename(columns={"Corridor": "corridor", "old_name": "pre_route_id", "new_name": "post_route_id"})
            .drop(columns="Route")
        )
    else:
        corridor_map = None
    print("prep ridership")

    ridership_pre_post_comp = build_ridership_comp_by_type(
        x_walk_long,
        day_type=day_type,
        level=LEVEL,
        corridor_map=corridor_map,
    )

    pre_post_trip_comp = build_trip_comp(
        pre_change_feed,
        post_change_feed,
        x_walk_long,
        level=LEVEL,
        corridor_map=corridor_map,
    )

    #pre_change_stats  = route_level_summary_stats(pre_change_feed,  day_type=day_type)
    #post_change_stats = route_level_summary_stats(post_change_feed, day_type=day_type)
    
    #pre_change_stats  = pre_change_stats[pre_change_stats["route_id"].str.startswith(("C", "D"))]
    #post_change_stats = post_change_stats[post_change_stats["route_id"].str.startswith(("C", "D"))]
    
    
    #pre_change_stats.to_csv("_intermediate/pre_change_summary_stats_weekday.csv")
    #post_change_stats.to_csv("_intermediate/post_change_summary_stats_weekday.csv")
    
    pre_change_stats = pd.read_csv('_intermediate/pre_change_summary_stats_weekday.csv')
    post_change_stats = pd.read_csv('_intermediate/post_change_summary_stats_weekday.csv')
    

    
    
    
    pre_change_stats_processed,  pre_num_days,  pre_num_weeks  = process_gtfs_stats(pre_change_stats)
    post_change_stats_processed, post_num_days, post_num_weeks = process_gtfs_stats(post_change_stats)

    pre_agg  = aggregate_stats(pre_change_stats_processed,  prefix="pre",  num_weeks=pre_num_weeks,  level=LEVEL, corridor_map=corridor_map)
    post_agg = aggregate_stats(post_change_stats_processed, prefix="post", num_weeks=post_num_weeks, level=LEVEL, corridor_map=corridor_map)


    print("aggregated")
    
    
    PRE_ID  = f"pre_{LEVEL}_id"
    POST_ID = f"post_{LEVEL}_id"

    if LEVEL == "route":
        pre_post_comp = (
            post_agg
            .merge(x_walk_long, how="left", left_on=POST_ID, right_on="new_name")
            .merge(pre_agg, how="outer", left_on="old_name", right_on=PRE_ID)
        )
    else:
        pre_post_comp = post_agg.merge(pre_agg, how="outer", left_on=POST_ID, right_on=PRE_ID)

    pre_post_comp = (
        pre_post_comp
        .merge(ridership_pre_post_comp, how="left", on=[PRE_ID, POST_ID])
        .merge(pre_post_trip_comp,      how="left", on=[PRE_ID, POST_ID])
        .dropna(subset=[PRE_ID, POST_ID])
    )

    pre_post_comp[[PRE_ID, POST_ID]].drop_duplicates()
    pre_post_comp.groupby([PRE_ID, POST_ID]).size().reset_index(name="count").query("count > 1")

    pre_post_comp.to_csv(f"_intermediate/summary_output_comp_{LEVEL}_{day_type}_{date_str}.csv")

    drop_cols = ["old_name", "new_name"]
    id_cols   = [PRE_ID, POST_ID]

    diff_df = compute_pre_post_diff(pre_post_comp, id_cols=id_cols, method="diff").drop(columns=drop_cols, errors="ignore")
    pct_df  = compute_pre_post_diff(pre_post_comp, id_cols=id_cols, method="pct").drop(columns=drop_cols, errors="ignore")

    diff_long_df_func = pivot_longer(diff_df, id_vars=id_cols, prefixes=["pre", "post", "change"]).assign(category=f"diff_{LEVEL}")
    pct_long_df_func  = pivot_longer(pct_df,  id_vars=id_cols, prefixes=["pre", "post", "change"]).assign(category=f"pct_{LEVEL}")

    val_rename = {
        "total_ridership":   "Total Ridership",
        "monthly_ridership": "Monthly Ridership",
        "median_ridership":  "Median Ridership",
        "num_unique_stops":  "Unique Stops",
        "stops_per_hour":    "Stops Per Hour",
    }

    diff_long_df = rename_metrics(diff_long_df_func)
    diff_long_df["metric"] = diff_long_df["metric"].replace(val_rename)

    pct_long_df = rename_metrics(pct_long_df_func)
    pct_long_df["metric"] = pct_long_df["metric"].replace(val_rename)

    print(f"Running at level: {LEVEL} | day_type: {day_type}")
    print(f"Unique post {LEVEL}s: {pre_post_comp[POST_ID].nunique()}")
    print(f"Unique pre  {LEVEL}s: {pre_post_comp[PRE_ID].nunique()}")
    print(f"Metrics available: {diff_long_df['metric'].unique()}")

    if LEVEL == "corridor":
        diff_long_df_output = diff_long_df[["pre_corridor_id", "post_corridor_id", "metric", "pre_value", "post_value"]].drop_duplicates()
        # STEP 9: Include day_type in export filename
        diff_long_df_output.to_csv(f"export/bus_comp_{LEVEL}_{day_type}_{date_str}_{crosswalk_type}.csv", index=False)
    else:
        corridor_map = (
            corridor_map_raw
            .merge(x_walk_long, how="left", left_on="Route", right_on="new_name")
            .rename(columns={"Corridor": "corridor", "old_name": "pre_route_id", "new_name": "post_route_id"})
            .drop(columns="Route")
        )
        diff_long_df_output = (
            diff_long_df[["pre_route_id", "post_route_id", "metric", "pre_value", "post_value"]]
            .drop_duplicates()
            .merge(
                corridor_map[["pre_route_id", "post_route_id", "corridor"]],
                on=["pre_route_id", "post_route_id"],
                how="left"
            )
        )
        diff_long_df_output.to_csv(f"export/bus_comp_{LEVEL}_{day_type}_{date_str}_{crosswalk_type}.csv", index=False)


for day_type in ["weekday", "weekend"]:
#for day_type in ["weekday"]:
    for crosswalk_type in ["augmented"]:
        for LEVEL in ["corridor", "route"]:
            run_analysis(LEVEL, crosswalk_type, day_type=day_type)


def load_csvs(directory=".", keyword=None, crosswalk_type=None, day_type=None):
    files = [
        f for f in os.listdir(directory)
        if f.endswith(".csv")
        and (keyword is None or keyword in f)
        and (crosswalk_type is None or crosswalk_type in f)
        and (day_type is None or day_type in f)
        and date_str in f
    ]
    dfs = []
    for f in files:
        df = pd.read_csv(os.path.join(directory, f))
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


for day_type in ["weekday", "weekend"]:
#for day_type in ["weekday"]:
    corridor_df = load_csvs("export", keyword="corridor", crosswalk_type="augmented", day_type=day_type)
    route_df    = load_csvs("export", keyword="route",    crosswalk_type="augmented", day_type=day_type)

    if not corridor_df.empty:
        #corridor_df = corridor_df.drop(columns=corridor_df.columns[0], errors="ignore")
        corridor_df.to_csv(f"augmented_corridor_df_{day_type}_{date_str}.csv", index=False)

    if not route_df.empty:
        #route_df = route_df.drop(columns=route_df.columns[0], errors="ignore")
        route_df.to_csv(f"augmented_route_df_{day_type}_{date_str}.csv", index=False)
        
        
        
        
        
        
        