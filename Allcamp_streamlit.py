import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import altair as alt
from datetime import datetime, timedelta
import calendar

# ==============================
# 1. PAGE CONFIG & BASIC THEME
# ==============================
st.set_page_config(
    layout="centered", 
    page_title="AllCamp Demand Strategy (Integrated)"
)

# --- styling for a muted, natural color palette & smaller footnotes ---
st.markdown("""
<style>
    /* Overall background / text */
    .stApp {
        background-color: #F5F5F3; /* a light earthy tone */
        color: #2E2F2E;
        font-family: "Helvetica Neue", Arial, sans-serif;
    }
    /* Headers in a deeper green */
    h1, h2, h3, h4 {
        color: #126B37; 
    }
    /* Smaller footnote text */
    .footnote {
        font-size: 0.8rem;
        color: #555;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <style>
    /* Style the entire sidebar */
    [data-testid="stSidebar"] {
        background-color: #EFF6EE; /* a light pastel green/gray */
        border-right: 1px solid #DDD;
    }
    /* Change the default text style of the sidebar */
    [data-testid="stSidebar"] .css-1n76uvr p,
    [data-testid="stSidebar"] .css-1n76uvr label {
        color: #2E2F2E !important;  
        font-family: "Helvetica Neue", Arial, sans-serif;
        font-size: 1rem;
    }
    /* Style the radio labels (the text next to the radio button) */
    [role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p {
        color: #126B37 !important; /* forest green text */
        font-weight: 600;          /* semi-bold */
    }
    /* Change radio bullet color (for webkit-based browsers) */
    input[type="radio"] {
        accent-color: #126B37 !important; /* a forest green accent */
    }
    /* Make the selected radio item stand out (more subtle approach) */
    [role="radiogroup"] > label:nth-of-type(even) {
        background-color: #F8FAF7; /* slight alternate row shading */
    }
    [role="radiogroup"] > label:hover {
        background-color: #E4F0E8; /* highlight on hover */
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ==============================
# 2. ALTAIR THEME CONFIG
# ==============================
def allcamp_theme():
    """
    Custom Altair theme
    """
    return {
        "config": {
            "view": {
                "stroke": "transparent",  
                "fill": "#FFFFFF"       
            },
            "background": "#F5F5F3",     
            "title": {
                "fontSize": 18,
                "anchor": "start",
                "font": "Helvetica Neue, Arial",
                "color": "#126B37"
            },
            "axis": {
                "domainColor": "#126B37",
                "domainWidth": 1,
                "tickColor": "#126B37",
                "labelColor": "#2E2F2E",
                "labelFont": "Helvetica Neue, Arial",
                "titleFont": "Helvetica Neue, Arial",
                "titleColor": "#2E2F2E",
                "grid": False
            },
            "legend": {
                "labelFont": "Helvetica Neue, Arial",
                "labelColor": "#2E2F2E",
                "titleFont": "Helvetica Neue, Arial",
                "titleColor": "#2E2F2E"
            },
            "bar": {
                "color": "#126B37"  
            }
        }
    }

# Register and enable the custom theme
alt.themes.register("allcamp_theme", allcamp_theme)
alt.themes.enable("allcamp_theme")


# ==============================
# 3. DATA LOADING
# ==============================
@st.cache_data
def load_campgrounds_data():
    df = pd.read_csv("campgrounds.csv")
    df["went_live_date"] = pd.to_datetime(df["went_live_date"], errors="coerce")
    df["first_booked_at_date"] = pd.to_datetime(
        df["first_booked_at_date"], errors="coerce", utc=True, format='ISO8601'
    )
    df["campground_h3_hexagon_id_l4"] = df["campground_h3_hexagon_id_l4"].astype(str)
    return df

@st.cache_data
def load_transactions_data():
    df = pd.read_csv("transactions.csv")
    df["trip_checkin_date"] = pd.to_datetime(df["trip_checkin_date"], errors="coerce")
    df["trip_checkout_date"] = pd.to_datetime(df["trip_checkout_date"], errors="coerce")
    df["h3_hexagon_id_l4"] = df["h3_hexagon_id_l4"].astype(str)
    return df

@st.cache_data
def load_searches_data():
    df = pd.read_csv("searches.csv")
    df["destination_h3_cell_id"] = df["destination_h3_cell_id"].astype(str)
    df["destination_h3_parent_id"] = df["destination_h3_parent_id"].astype(str, errors="ignore")
    df["origin_h3_cell_id"] = df["origin_h3_cell_id"].astype(str)
    df["origin_h3_parent_id"] = df["origin_h3_parent_id"].astype(str, errors="ignore")
    return df

df_camp = load_campgrounds_data()
df_trans = load_transactions_data()
df_search = load_searches_data()


# ==============================
# 4. PARTIAL REVENUE LOGIC
# ==============================
analysis_start = pd.to_datetime("2028-01-01")
analysis_end   = pd.to_datetime("2028-12-31")

# Filter out canceled only
df_trans_valid = df_trans[df_trans["is_booking_canceled"] == False].copy()

def nights_in_overlap(checkin, checkout, window_start, window_end):
    """Compute how many nights fall in [window_start, window_end]."""
    if pd.isnull(checkin) or pd.isnull(checkout):
        return 0
    trip_start = max(checkin, window_start)
    trip_end = min(checkout, window_end + pd.Timedelta(days=1))
    return max((trip_end - trip_start).days, 0)

def total_trip_nights(checkin, checkout):
    """Total nights for the entire booking (checkout exclusive)."""
    if pd.isnull(checkin) or pd.isnull(checkout):
        return 0
    return (checkout - checkin).days

# Partial revenue column
df_trans_valid["partial_revenue_2028"] = 0.0
df_trans_valid["partial_nights_2028"] = 0
df_trans_valid["total_trip_nights"] = 0

for idx, row in df_trans_valid.iterrows():
    cin = row["trip_checkin_date"]
    cout= row["trip_checkout_date"]
    overlap = nights_in_overlap(cin, cout, analysis_start, analysis_end)
    full_nights = total_trip_nights(cin, cout)
    if full_nights > 0 and overlap > 0:
        fraction_2028 = overlap / full_nights
        df_trans_valid.at[idx, "partial_revenue_2028"] = fraction_2028 * row["trip_total_cost"]
        df_trans_valid.at[idx, "partial_nights_2028"]  = overlap
        df_trans_valid.at[idx, "total_trip_nights"]    = full_nights


# ==============================
# 5. BASIC AGGREGATIONS
# ==============================
agg_df_camp = (
    df_camp
    .dropna(subset=["went_live_date"])
    .groupby("campground_h3_hexagon_id_l4", dropna=True)
    .agg(
        count_of_campgrounds=("campground_uuid", "nunique"),
        total_sites=("number_of_sites", "sum"),
        total_tent_sites=("tent_friendly_sites", "sum"),
        total_rv_sites=("rv_friendly_sites", "sum"),
        total_structure_sites=("structure_sites", "sum"),
    )
    .reset_index()
    .rename(columns={"campground_h3_hexagon_id_l4": "h3_id"})
)

agg_df_trans = (
    df_trans_valid.groupby("h3_hexagon_id_l4", dropna=True)
    .agg(
        count_of_bookings=("booking_uuid", "nunique"),
        total_revenue=("partial_revenue_2028", "sum"),
    )
    .reset_index()
    .rename(columns={"h3_hexagon_id_l4": "h3_id"})
)


# ==============================
# 6. OVERVIEW STATS
# ==============================
@st.cache_data
def compute_overview_stats():
    df_valid_2028 = df_trans_valid[df_trans_valid["partial_nights_2028"] > 0].copy()

    total_camp_count_all = df_camp["campground_uuid"].nunique()
    df_live = df_camp[df_camp["went_live_date"].notnull()]
    live_camp_count = df_live["campground_uuid"].nunique()
    df_active = df_camp[df_camp["first_booked_at_date"].notnull()]
    active_camp_count = df_active["campground_uuid"].nunique()

    total_revenue_2028 = df_valid_2028["partial_revenue_2028"].sum()
    total_bookings_2028 = df_valid_2028["booking_uuid"].nunique()

    merged = df_valid_2028.merge(
        df_camp[["campground_uuid","campground_state"]],
        on="campground_uuid",
        how="left"
    )
    revenue_by_state = (
        merged.groupby("campground_state")["partial_revenue_2028"].sum()
        .reset_index()
        .rename(columns={"partial_revenue_2028":"state_revenue_2028"})
        .sort_values("state_revenue_2028", ascending=False)
    )

    cat_counts = (
        df_valid_2028.groupby("campsite_category")["booking_uuid"]
        .nunique()
        .reset_index()
        .rename(columns={"booking_uuid":"count_of_bookings"})
    )

    return {
        "total_camp_count_all": total_camp_count_all,
        "live_camp_count": live_camp_count,
        "active_camp_count": active_camp_count,
        "total_revenue_2028": total_revenue_2028,
        "total_bookings_2028": total_bookings_2028,
        "revenue_by_state_df": revenue_by_state,
        "campsite_category_df": cat_counts,
    }

overview_stats = compute_overview_stats()


# ==============================
# 7. MAP HELPERS
# ==============================
def build_hex_map(df, metric_col, tooltip_label, lat=34.5, lng=-85.0, zoom=4, max_clip=None):
    local_df = df.copy()
    if max_clip is not None and len(local_df) > 0:
        clip_val = np.percentile(local_df[metric_col], max_clip)
        local_df["clipped"] = local_df[metric_col].clip(upper=clip_val)
    else:
        local_df["clipped"] = local_df[metric_col]

    max_val = local_df["clipped"].max()
    if max_val <= 0:
        local_df["norm"] = 0
    else:
        local_df["norm"] = local_df["clipped"] / max_val

    color_expression = """[
        190 + (20 - 190) * norm,
        210 + (96 - 210) * norm,
        100 + (22 - 100) * norm,
        200
    ]"""

    tile_layer = pdk.Layer(
        "TileLayer",
        data="https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
        pickable=False,
        tile_size=256,
        opacity=0.7
    )

    h3_layer = pdk.Layer(
        "H3HexagonLayer",
        data=local_df,
        get_hexagon="h3_id",
        get_fill_color=color_expression,
        pickable=True,
        extruded=False,
        filled=True
    )

    view_state = pdk.ViewState(latitude=lat, longitude=lng, zoom=zoom)
    tooltip = {
        "html": f"""
            <b>H3 ID:</b> {{h3_id}}<br/>
            <b>{tooltip_label}:</b> {{{metric_col}}}
        """,
        "style": {"backgroundColor": "rgba(0,0,0,0.7)", "color": "white"},
    }

    return pdk.Deck(layers=[tile_layer, h3_layer], initial_view_state=view_state, tooltip=tooltip)


def build_search_map(df, h3_col, metric_col="searchers", tooltip_label="Search Volume"):
    local_df = df.copy()
    local_df.rename(columns={h3_col:"h3_id"}, inplace=True)

    if len(local_df) > 0:
        clip_val = np.percentile(local_df[metric_col], 95)
        local_df["clipped"] = local_df[metric_col].clip(upper=clip_val)
    else:
        local_df["clipped"] = 0

    max_val = local_df["clipped"].max()
    if max_val <= 0:
        local_df["norm"] = 0
    else:
        local_df["norm"] = local_df["clipped"] / max_val

    color_expression = """[
        255 + (20 - 255) * norm,
        255 + (96 - 255) * norm,
        100 + (22 - 100) * norm,
        200
    ]"""

    tile_layer = pdk.Layer(
        "TileLayer",
        data="https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
        pickable=False,
        tile_size=256,
        opacity=0.7,
    )

    h3_layer = pdk.Layer(
        "H3HexagonLayer",
        data=local_df,
        get_hexagon="h3_id",
        get_fill_color=color_expression,
        pickable=True,
        extruded=False,
        filled=True
    )

    view_state = pdk.ViewState(latitude=34.5, longitude=-85.0, zoom=4)
    tooltip = {
        "html": f"""
            <b>H3 ID:</b> {{h3_id}}<br/>
            <b>{tooltip_label}:</b> {{{metric_col}}}
        """,
        "style": {"backgroundColor":"rgba(0,0,0,0.7)","color":"white"}
    }

    return pdk.Deck(layers=[tile_layer, h3_layer], initial_view_state=view_state, tooltip=tooltip)


# ==============================
# 8. OCCUPANCY LOGIC 
# ==============================

def compute_occupancy_for_month_category_with_all(month, category, weekend_only=False):

    start_date_2028 = pd.to_datetime(f"2028-{month:02d}-01")
    last_day = calendar.monthrange(2028, month)[1]
    end_date_2028 = pd.to_datetime(f"2028-{month:02d}-{last_day}")

    df_cg = df_camp.copy()

    def capacity_sites_for_cat(row):
        if category == "All":
            return row.get("number_of_sites", 0) or 0
        elif category == "tent-or-rv":
            return (row.get("tent_friendly_sites", 0) or 0) + (row.get("rv_friendly_sites", 0) or 0)
        elif category == "rv-only":
            return row.get("rv_friendly_sites", 0) or 0
        elif category == "structure":
            return row.get("structure_sites", 0) or 0
        else:
            # fallback
            return row.get("number_of_sites", 0) or 0

    # Only consider campgrounds that went live by end_date_2028
    df_cg = df_cg[df_cg["went_live_date"].notnull()].copy()
    df_cg["capacity_sites_for_cat"] = df_cg.apply(capacity_sites_for_cat, axis=1)

    df_cg["start_for_capacity"] = df_cg["went_live_date"].apply(
        lambda d: max(d, start_date_2028) if pd.notnull(d) else start_date_2028
    )
    df_cg["end_for_capacity"] = end_date_2028

    capacity_list = []
    for idx, row in df_cg.iterrows():
        live_start = row["start_for_capacity"]
        live_end   = row["end_for_capacity"]
        cat_sites  = row["capacity_sites_for_cat"]
        if live_end < live_start or cat_sites <= 0:
            capacity_list.append(0)
            continue

        if not weekend_only:
            days_in_window = (live_end - live_start).days + 1
            capacity_list.append(days_in_window * cat_sites)
        else:
            # Only count FRI=4, SAT=5, SUN=6
            days_count = 0
            current = live_start
            while current <= live_end:
                if current.weekday() in [4,5,6]:
                    days_count += 1
                current += pd.Timedelta(days=1)
            capacity_list.append(days_count * cat_sites)

    df_cg["capacity_site_nights"] = capacity_list
    capacity_by_hex = (
        df_cg
        .groupby("campground_h3_hexagon_id_l4", dropna=True)["capacity_site_nights"]
        .sum()
        .reset_index()
        .rename(columns={"campground_h3_hexagon_id_l4":"h3_id"})
    )

    # If "All", do not filter by campsite_category. Otherwise filter
    df_trans_filtered = df_trans_valid.copy()
    df_trans_filtered = df_trans_filtered[df_trans_filtered["trip_checkout_date"] <= end_date_2028].copy()

    if category != "All":
        df_trans_filtered = df_trans_filtered[df_trans_filtered["campsite_category"] == category]

    usage_list = []
    for idx, b_row in df_trans_filtered.iterrows():
        cin  = b_row["trip_checkin_date"]
        cout = b_row["trip_checkout_date"]
        overlap_start = max(cin, start_date_2028)
        overlap_end   = min(cout, end_date_2028)
        if overlap_end <= overlap_start:
            usage_list.append(0)
        else:
            if not weekend_only:
                usage_list.append((overlap_end - overlap_start).days)
            else:
                # weekend-only usage
                day_count = 0
                current = overlap_start
                while current < overlap_end:
                    if current.weekday() in [4,5,6]:
                        day_count += 1
                    current += pd.Timedelta(days=1)
                usage_list.append(day_count)

    df_trans_filtered["used_site_nights"] = usage_list
    usage_by_hex = (
        df_trans_filtered
        .groupby("h3_hexagon_id_l4", dropna=True)["used_site_nights"]
        .sum()
        .reset_index()
        .rename(columns={"h3_hexagon_id_l4":"h3_id"})
    )

    merged = capacity_by_hex.merge(usage_by_hex, on="h3_id", how="outer").fillna(0)
    merged["occupancy_rate"] = 0.0
    valid_mask = merged["capacity_site_nights"] > 0
    merged.loc[valid_mask, "occupancy_rate"] = (
        merged.loc[valid_mask,"used_site_nights"] / merged.loc[valid_mask,"capacity_site_nights"]
    )
    return merged, start_date_2028, end_date_2028


def tiered_color_for_occupancy(occ):
    if occ < 0.4:
        return [255, 255, 102, 180]  # yellow
    elif occ < 0.7:
        return [144, 238, 144, 180]  # light green
    else:
        return [0, 100, 0, 220]      # dark green


# ==============================
# 9. SEARCH DEMAND PAGE
# ==============================
def group_search_by_parent_id(df, parent_col="destination_h3_parent_id"):
    grp = (
        df.groupby(parent_col, dropna=True)[["searchers","rv_searchers","tent_searchers"]]
        .sum()
        .reset_index()
    )
    return grp


# ==============================
# 10. EXPANSION OPPORTUNITIES
# ==============================
def days_in_overlap(start_date, end_date, window_start, window_end):
    actual_start = max(start_date, window_start)
    actual_end   = min(end_date, window_end)
    diff = (actual_end - actual_start).days + 1
    return max(diff, 0)

@st.cache_data
def compute_expansion_opportunities():
    df_camp_se = df_camp[
        (df_camp["campground_region"] == "Southeast")
        & (df_camp["went_live_date"].notnull())
    ].copy()

    partial_cap = []
    rv_cap = []
    tent_cap = []
    struct_cap = []

    for idx, row in df_camp_se.iterrows():
        wld = row["went_live_date"]
        if pd.isnull(wld):
            partial_cap.append(0)
            rv_cap.append(0)
            tent_cap.append(0)
            struct_cap.append(0)
            continue

        days_live = days_in_overlap(
            wld, pd.Timestamp("2099-12-31"), analysis_start, analysis_end
        )
        total_sites = row.get("number_of_sites", 0) or 0
        rv_sites    = row.get("rv_friendly_sites", 0) or 0
        tent_sites  = row.get("tent_friendly_sites", 0) or 0
        st_sites    = row.get("structure_sites", 0) or 0

        partial_cap.append(days_live * total_sites)
        rv_cap.append(days_live * rv_sites)
        tent_cap.append(days_live * tent_sites)
        struct_cap.append(days_live * st_sites)

    df_camp_se["partial_capacity"]   = partial_cap
    df_camp_se["rv_capacity"]        = rv_cap
    df_camp_se["tent_capacity"]      = tent_cap
    df_camp_se["structure_capacity"] = struct_cap

    cap_se = (
        df_camp_se
        .groupby("campground_h3_hexagon_id_l4", dropna=True)
        .agg({
            "partial_capacity":"sum",
            "rv_capacity":"sum",
            "tent_capacity":"sum",
            "structure_capacity":"sum",
        })
        .reset_index()
        .rename(columns={"campground_h3_hexagon_id_l4":"h3_id"})
    )

    df_trans_se = df_trans_valid.merge(
        df_camp_se[["campground_uuid","campground_h3_hexagon_id_l4"]],
        on="campground_uuid",
        how="inner"
    )

    usage_list = []
    rv_usage_list = []
    tent_usage_list = []
    struct_usage_list = []

    for idx, row in df_trans_se.iterrows():
        cin = row["trip_checkin_date"]
        cout= row["trip_checkout_date"]
        days_booked = days_in_overlap(cin, cout - pd.Timedelta(days=1), analysis_start, analysis_end)
        usage_list.append(days_booked)

        cat = row.get("campsite_category", None)
        if cat == "rv-only":
            rv_usage_list.append(days_booked)
            tent_usage_list.append(0)
            struct_usage_list.append(0)
        elif cat == "tent-or-rv":
            rv_usage_list.append(days_booked / 2.0)
            tent_usage_list.append(days_booked / 2.0)
            struct_usage_list.append(0)
        elif cat == "structure":
            rv_usage_list.append(0)
            tent_usage_list.append(0)
            struct_usage_list.append(days_booked)
        else:
            tent_usage_list.append(days_booked)
            rv_usage_list.append(0)
            struct_usage_list.append(0)

    df_trans_se["used_site_nights"]      = usage_list
    df_trans_se["used_rv_nights"]        = rv_usage_list
    df_trans_se["used_tent_nights"]      = tent_usage_list
    df_trans_se["used_structure_nights"] = struct_usage_list

    usage_agg = (
        df_trans_se
        .groupby("campground_h3_hexagon_id_l4", dropna=True)
        .agg({
            "used_site_nights":"sum",
            "used_rv_nights":"sum",
            "used_tent_nights":"sum",
            "used_structure_nights":"sum",
        })
        .reset_index()
        .rename(columns={"campground_h3_hexagon_id_l4":"h3_id"})
    )

    merged_occ = cap_se.merge(usage_agg, on="h3_id", how="outer").fillna(0)
    merged_occ["occupancy_rate"] = 0.0
    valid_mask = merged_occ["partial_capacity"]>0
    merged_occ.loc[valid_mask,"occupancy_rate"] = (
        merged_occ.loc[valid_mask,"used_site_nights"] / merged_occ.loc[valid_mask,"partial_capacity"]
    )

    # Summarize search demand
    if "glamping_searchers" in df_search.columns:
        srch_cols = ["searchers","rv_searchers","tent_searchers","glamping_searchers"]
    else:
        srch_cols = ["searchers","rv_searchers","tent_searchers"]

    search_agg = (
        df_search
        .groupby("destination_h3_cell_id", dropna=True)[srch_cols]
        .sum()
        .reset_index()
        .rename(columns={"destination_h3_cell_id":"h3_id"})
        .fillna(0)
    )
    if "glamping_searchers" not in search_agg.columns:
        search_agg["glamping_searchers"] = 0


    final_df = merged_occ.merge(search_agg, on="h3_id", how="outer").fillna(0)
    final_df["priority_score"] = final_df["occupancy_rate"] * final_df["searchers"]

    final_df["general_searchers"] = (
        final_df["searchers"]
        - final_df["rv_searchers"]
        - final_df["tent_searchers"]
        - final_df["glamping_searchers"]
    )
    final_df["sum_of_specified"] = (
        final_df["rv_searchers"]
        + final_df["tent_searchers"]
        + final_df["glamping_searchers"]
    )
    final_df["rv_searchers_adjusted"] = final_df["rv_searchers"]
    final_df["tent_searchers_adjusted"] = final_df["tent_searchers"]
    final_df["structure_searchers_adjusted"] = final_df["glamping_searchers"]

    has_spec = final_df["sum_of_specified"] > 0
    final_df.loc[has_spec,"rv_searchers_adjusted"] += (
        final_df.loc[has_spec,"general_searchers"]
        * (final_df.loc[has_spec,"rv_searchers"]/final_df.loc[has_spec,"sum_of_specified"])
    )
    final_df.loc[has_spec,"tent_searchers_adjusted"] += (
        final_df.loc[has_spec,"general_searchers"]
        * (final_df.loc[has_spec,"tent_searchers"]/final_df.loc[has_spec,"sum_of_specified"])
    )
    final_df.loc[has_spec,"structure_searchers_adjusted"] += (
        final_df.loc[has_spec,"general_searchers"]
        * (final_df.loc[has_spec,"glamping_searchers"]/final_df.loc[has_spec,"sum_of_specified"])
    )

    # Mismatch ratio
    # Shortfall-based approach: mismatch = 0 if demand <= supply,
    # else (demand - supply)/ supply, and 10 if supply=0 but demand>0.

    # Example for RV:
    final_df["rv_mismatch_ratio"] = 0.0

    rv_demand = final_df["rv_searchers_adjusted"]
    rv_supply = final_df["rv_capacity"]

    # Where supply > 0 and demand > supply => ratio = (demand - supply)/supply
    short_mask = (rv_supply > 0) & (rv_demand > rv_supply)
    final_df.loc[short_mask,"rv_mismatch_ratio"] = (
        (rv_demand[short_mask] - rv_supply[short_mask]) / rv_supply[short_mask]
    )

    # If supply=0 but there's demand => ratio=10
    inf_mask = (rv_supply==0) & (rv_demand>0)
    final_df.loc[inf_mask,"rv_mismatch_ratio"] = 10

    # Repeat for tent:
    final_df["tent_mismatch_ratio"] = 0.0
    tent_demand = final_df["tent_searchers_adjusted"]
    tent_supply = final_df["tent_capacity"]
    short_mask_tent = (tent_supply>0) & (tent_demand>tent_supply)
    final_df.loc[short_mask_tent,"tent_mismatch_ratio"] = (
        (tent_demand[short_mask_tent] - tent_supply[short_mask_tent]) / tent_supply[short_mask_tent]
    )
    inf_mask_tent = (tent_supply==0) & (tent_demand>0)
    final_df.loc[inf_mask_tent,"tent_mismatch_ratio"] = 10

    # And for structure:
    final_df["structure_mismatch_ratio"] = 0.0
    str_demand = final_df["structure_searchers_adjusted"]
    str_supply = final_df["structure_capacity"]
    short_mask_str = (str_supply>0) & (str_demand>str_supply)
    final_df.loc[short_mask_str,"structure_mismatch_ratio"] = (
        (str_demand[short_mask_str] - str_supply[short_mask_str]) / str_supply[short_mask_str]
    )
    inf_mask_str = (str_supply==0) & (str_demand>0)
    final_df.loc[inf_mask_str,"structure_mismatch_ratio"] = 10

    # Finally set max mismatch
    final_df["max_mismatch_ratio"] = final_df[[
        "rv_mismatch_ratio","tent_mismatch_ratio","structure_mismatch_ratio"
    ]].max(axis=1)


    return final_df

expansion_data = compute_expansion_opportunities()


# ==============================
# 11. MULTI-PAGE APP
# ==============================
def main():
    pages = [
        "Home / Overview",
        "Campgrounds",
        "Transactions",
        "Monthly Occupancy (By Category, 2028)",
        "Search Demand",
        "Expansion Opportunities"
    ]
    page = st.sidebar.radio("Go to Page:", pages)

    # ===================================
    #  HOME / OVERVIEW (IMPROVED LAYOUT)
    # ===================================
    if page == "Home / Overview":
        # --- Hero Banner ---
        st.markdown(
            """
            <div style="background-color:#EFF6EE; padding:1.5rem; border-radius:0.5rem; margin-bottom:1rem;">
                <h1 style="color:#126B37; margin-top:0;">AllCamp — Southeastern Demand Strategy</h1>
                <p style="color:#4A4A4A;">
                    The year is <strong>2029</strong>, and AllCamp is expanding private campgrounds 
                    across the Southeastern US. This presentation shows <strong>2028 data</strong> 
                    for bookings, revenue, and search demand — guiding our <strong>2029</strong> strategy.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- KPI "card" Row 1: 3 columns ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"""
                <div style="background-color:#FFFFFF; 
                            padding:1rem; 
                            border-radius:0.5rem; 
                            border:1px solid #DDD;">
                    <h4 style="margin-bottom:0.5rem; color:#126B37;">All SE Campgrounds</h4>
                    <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                        {overview_stats['total_camp_count_all']:,}
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f"""
                <div style="background-color:#FFFFFF; 
                            padding:1rem; 
                            border-radius:0.5rem; 
                            border:1px solid #DDD;">
                    <h4 style="margin-bottom:0.5rem; color:#126B37;">Live Campgrounds</h4>
                    <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                        {overview_stats['live_camp_count']:,}
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                f"""
                <div style="background-color:#FFFFFF; 
                            padding:1rem; 
                            border-radius:0.5rem; 
                            border:1px solid #DDD;">
                    <h4 style="margin-bottom:0.5rem; color:#126B37;">Active Campgrounds</h4>
                    <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                        {overview_stats['active_camp_count']:,}
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )

        # --- KPI "card" Row 2: 2 columns ---
        col4, col5 = st.columns(2)
        with col4:
            st.markdown(
                f"""
                <div style="background-color:#FFFFFF; 
                            padding:1rem; 
                            border-radius:0.5rem; 
                            border:1px solid #DDD; 
                            margin-top:1rem;">
                    <h4 style="margin-bottom:0.5rem; color:#126B37;">Total Bookings (2028)</h4>
                    <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                        {overview_stats['total_bookings_2028']:,}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col5:
            st.markdown(
                f"""
                <div style="background-color:#FFFFFF; 
                            padding:1rem; 
                            border-radius:0.5rem; 
                            border:1px solid #DDD; 
                            margin-top:1rem;">
                    <h4 style="margin-bottom:0.5rem; color:#126B37;">Gross Booking Value</h4>
                    <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                        ${overview_stats['total_revenue_2028']:,.0f}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        # --- Expander for definitions ---
        with st.expander("Click for definitions & notes"):
            st.caption("""
            **All SE Campgrounds**  
            Every Southeastern private campground in the system, regardless of status.

            **Live Campgrounds**  
            A campground with a non-null `went_live_date` (publicly visible).

            **Active Campgrounds**  
            A campground that has at least one booking (`first_booked_at_date` is not null).

            **Total Bookings (2028)**   
            Count of unique bookings that have any nights within 2028 
            (excluding canceled).

            **Gross Booking Value**  
            Revenue allocated to 2028 based on nights stayed. If a trip overlaps years, only the portion in 2028 is counted.

            """)

        st.markdown("---")

        # Quick Key Objectives
        st.markdown("""
        ### Key Objectives
        - **Scale** private campgrounds in the Southeast.
        - Identify **revenue hotspots** and **supply gaps**.
        """)

        # Top States by 2028 Partial Revenue
        st.markdown("### Top States by 2028 Gross Booking Volume")
        df_states = overview_stats["revenue_by_state_df"].copy()
        top_states = df_states.head(8)

        bar_chart = (
            alt.Chart(top_states)
            .mark_bar() 
            .encode(
                x=alt.X("state_revenue_2028:Q", title="Gross Booking Value"),
                y=alt.Y("campground_state:N", sort="-x", title="State")
            )
            .properties(width=600, height=300)
        )
        # Center the chart with simple HTML
        st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
        st.altair_chart(bar_chart, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.caption("""
        <div class="footnote">
        **Gross Booking Value** is prorated by trip nights.  
        Example: If a 4-night trip spans 2 nights in 2028 and 2 outside 2028, we allocate 50% of `trip_total_cost` to 2028.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        ---
        **Explore** more details on the subsequent pages:
        - **Campgrounds** 
        - **Transactions** 
        - **Monthly Occupancy** 
        - **Search Demand**
        - **Expansion Opportunities** 
        """)


    # ===========================
    #  CAMPGROUNDS PAGE
    # ===========================
    elif page == "Campgrounds":
        st.markdown(
            """
            <div style="background-color:#EFF6EE; 
                        padding:1.0rem; 
                        border-radius:0.5rem; 
                        margin-bottom:1rem;">
                <h1 style="color:#126B37; margin-top:0; margin-bottom:0;">
                    Campgrounds
                </h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ------------------------------------
        # 1) Quick Aggregations for KPI Cards
        # ------------------------------------
        df_camp_live = df_camp[df_camp["went_live_date"].notnull()].copy()
        total_live_cg_count = df_camp_live["campground_uuid"].nunique()
        sum_all_sites = df_camp_live["number_of_sites"].fillna(0).sum()
        avg_sites_per_cg = sum_all_sites / total_live_cg_count if total_live_cg_count else 0

        # ============================
        #  NEW: 2027 BASELINE LOGIC
        # ============================
        df_camp_2027 = df_camp[df_camp["went_live_date"] < pd.Timestamp("2028-01-01")]
        live_2027_count = df_camp_2027["campground_uuid"].nunique()
        sum_2027_sites  = df_camp_2027["number_of_sites"].fillna(0).sum()

        if live_2027_count > 0:
            yoy_campgrowth = (total_live_cg_count - live_2027_count) / live_2027_count
        else:
            yoy_campgrowth = None

        if sum_2027_sites > 0:
            yoy_sitesgrowth = (sum_all_sites - sum_2027_sites) / sum_2027_sites
        else:
            yoy_sitesgrowth = None

        # Format as percentage strings
        yoy_campgrowth_str  = f"{yoy_campgrowth * 100:.1f}%" if yoy_campgrowth is not None else "N/A"
        yoy_sitesgrowth_str = f"{yoy_sitesgrowth * 100:.1f}%" if yoy_sitesgrowth is not None else "N/A"

        # ------------------------------------
        # 2) Display KPI Cards (similar style)
        # ------------------------------------
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Total Live Campgrounds (2028)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {total_live_cg_count:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Total Sites (2028)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {sum_all_sites:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Avg Sites / Campground</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {avg_sites_per_cg:,.1f}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # ------------------------------------
        #  NEW: Row 2 of KPI with 2027->2028
        # ------------------------------------
        col4, col5 = st.columns(2)
        with col4:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD; 
                        margin-top:1rem;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">YoY Growth (Campgrounds)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {yoy_campgrowth_str}
                </p>
                <p style="margin:0; font-size:0.9rem; color:#666;">
                    2027: {live_2027_count:,} → 2028: {total_live_cg_count:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD; 
                        margin-top:1rem;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">YoY Growth (Sites)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {yoy_sitesgrowth_str}
                </p>
                <p style="margin:0; font-size:0.9rem; color:#666;">
                    2027: {sum_2027_sites:,} → 2028: {sum_all_sites:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # ------------------------------------
        # 3) Definitions & Notes Expander
        # ------------------------------------
        with st.expander("Click for definitions & notes"):
            st.caption("""
            **Live Campgrounds (2028)**: Private campgrounds whose `went_live_date` 
            is not null (thus publicly visible) by 2028.

            **Total Sites (2028)**: Sum of `number_of_sites` across all campgrounds live in 2028.

            **Avg Sites / Campground**: 
            `Total Sites (2028) ÷ # of Live Campgrounds (2028)`

            **2027 Baseline**: 
            Campgrounds with `went_live_date` < 2028-01-01.

            **YoY Growth**:
            \\
            ( (2028 value) - (2027 value) ) / (2027 value ) * 100%
            """)

        # ------------------------------------------------------
        # 4) Existing Logic: Metric Selection + Hex Map Display
        # ------------------------------------------------------
        st.write("Aggregated live campgrounds by H3 hex. Select a metric below.")

        metric_options = {
            "Live Campgrounds": "count_of_campgrounds",
            "All Live Sites": "total_sites",
            "Tent-Friendly Sites": "total_tent_sites",
            "RV-Friendly Sites": "total_rv_sites",
            "Structure Sites": "total_structure_sites"
        }
        choice = st.selectbox("Choose metric:", list(metric_options.keys()))
        col = metric_options[choice]

        deck_map = build_hex_map(
            agg_df_camp,
            metric_col=col,
            tooltip_label=choice,
            lat=33.0, 
            lng=-82.0, 
            zoom=4, 
            max_clip=95
        )
        st.pydeck_chart(deck_map)




    # ===========================
    #  TRANSACTIONS PAGE
    # ===========================
    elif page == "Transactions":

        # 1) Banner Title
        st.markdown(
            """
            <div style="background-color:#EFF6EE; 
                        padding:1.0rem; 
                        border-radius:0.5rem; 
                        margin-bottom:1rem;">
                <h1 style="color:#126B37; margin-top:0; margin-bottom:0;">
                    Transactions (2028)
                </h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ----------------------------------------------------------------
        # 2) Compute KPI metrics
        df_trans_2028 = df_trans_valid[df_trans_valid["partial_nights_2028"] > 0].copy()
        total_bookings_2028 = df_trans_2028["booking_uuid"].nunique()
        sum_revenue_2028 = df_trans_2028["partial_revenue_2028"].sum()
        avg_revenue_2028 = sum_revenue_2028 / total_bookings_2028 if total_bookings_2028 else 0
        sum_nights_2028 = df_trans_2028["partial_nights_2028"].sum()
        avg_nights_2028 = sum_nights_2028 / total_bookings_2028 if total_bookings_2028 else 0

        # 3) KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">2028 Bookings</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {total_bookings_2028:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Gross Booking Value</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    ${sum_revenue_2028:,.0f}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Avg Booking Value</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    ${avg_revenue_2028:,.0f}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Avg Nights (2028)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {avg_nights_2028:,.1f}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # 4) Expander for definitions
        with st.expander("Click for definitions & notes"):
            st.caption("""
            **2028 Bookings**  
            Unique booking UUIDs where at least 1 night overlaps 2028 (excluded if canceled).

            **Gross Booking Value**  
            Sum of booking value attributed to 2028 nights (partial if the trip spans years).

            **Avg Booking Value**   
            Average value per booking in 2028 (based on prorated revenue).

            **Avg Nights (2028)**  
            Average partial nights per booking in 2028.
            """)

        st.markdown("<h3 style='text-align:center;'>Campsite Category Comparison (Bookings & Value)</h3>", unsafe_allow_html=True)

        df_cat = (
            df_trans_2028
            .groupby("campsite_category", dropna=True)
            .agg(
                bookings=("booking_uuid","nunique"),
                revenue=("partial_revenue_2028","sum")
            )
            .reset_index()
        )
        df_cat["avg_revenue"] = df_cat["revenue"] / df_cat["bookings"]

        chart_bookings = (
            alt.Chart(df_cat)
            .mark_bar()
            .encode(
                x=alt.X("bookings:Q", title="Count of Bookings"),
                y=alt.Y("campsite_category:N", sort="-x", title="Campsite Category")
            )
            .properties(width=220, height=300)
        )
        chart_revenue = (
            alt.Chart(df_cat)
            .mark_bar()
            .encode(
                x=alt.X("revenue:Q", title="Gross Booking Value"),
                y=alt.Y("campsite_category:N", sort="-x", title="Campsite Category")
            )
            .properties(width=220, height=300)
        )
        chart_avgrev = (
            alt.Chart(df_cat)
            .mark_bar()
            .encode(
                x=alt.X("avg_revenue:Q", title="Avg Booking Value"),
                y=alt.Y("campsite_category:N", sort="-x", title="Campsite Category")
            )
            .properties(width=220, height=300)
        )

        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            st.markdown("<p style='font-weight:bold; text-align:center;'>Bookings</p>", 
                        unsafe_allow_html=True)
            st.altair_chart(chart_bookings, use_container_width=True)
        with c2:
            st.markdown("<p style='font-weight:bold; text-align:center;'>Gross Booking Value</p>", unsafe_allow_html=True)

            st.altair_chart(chart_revenue, use_container_width=True)
        with c3:
            st.markdown("<p style='font-weight:bold; text-align:center;'>Avg Booking Value</p>", 
                        unsafe_allow_html=True)
            st.altair_chart(chart_avgrev, use_container_width=True)

        st.write("Below: Geographic distribution of 2028-overlapping bookings & booking value.")
        available_cats = ["All"] + sorted(df_cat["campsite_category"].unique().tolist())
        chosen_cat = st.selectbox("Filter map by campsite category:", available_cats)

        if chosen_cat == "All":
            local_agg = agg_df_trans
        else:
            cat_subset = df_trans_2028[df_trans_2028["campsite_category"] == chosen_cat]
            cat_agg = (
                cat_subset
                .groupby("h3_hexagon_id_l4", dropna=True)
                .agg(
                    count_of_bookings=("booking_uuid","nunique"),
                    total_revenue=("partial_revenue_2028","sum")
                )
                .reset_index()
                .rename(columns={"h3_hexagon_id_l4":"h3_id"})
            )
            local_agg = cat_agg

        metric_options = {
            "Count of Bookings (Overlap 2028)": "count_of_bookings",
            "Total Booking Value": "total_revenue"
        }
        choice = st.selectbox("Choose metric to map:", list(metric_options.keys()))
        col_ = metric_options[choice]

        deck_map = build_hex_map(
            local_agg,
            metric_col=col_,
            tooltip_label=choice,
            lat=34.0,
            lng=-85.0,
            zoom=4,  # Zoom level set to 4
            max_clip=95
        )
        st.pydeck_chart(deck_map)


    # ===========================
    #  MONTHLY OCCUPANCY PAGE
    # ===========================
    elif page == "Monthly Occupancy (By Category, 2028)":
        # 1) Banner-Style Heading
        st.markdown(
            """
            <div style="background-color:#EFF6EE; 
                        padding:1.0rem; 
                        border-radius:0.5rem; 
                        margin-bottom:1rem;">
                <h1 style="color:#126B37; margin-top:0; margin-bottom:0;">
                    Monthly Occupancy (By Category, 2028)
                </h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 2) UI for Month, Category, Weekend Filter
        col1, col2, col3 = st.columns(3)
        with col1:
            chosen_month = st.slider("Select Month (2028):", min_value=1, max_value=12, value=6)
        with col2:
            cat_options = ["All", "tent-or-rv", "rv-only", "structure"]
            chosen_category = st.selectbox("Campsite Category:", cat_options)
        with col3:
            weekend_only = st.checkbox("Weekend Only?", value=False)

        # 3) Compute occupancy data
        occ_df, start_d, end_d = compute_occupancy_for_month_category_with_all(
            chosen_month, chosen_category, weekend_only
        )

        # 4) Summaries for KPI Cards
        total_capacity = occ_df["capacity_site_nights"].sum()
        total_used = occ_df["used_site_nights"].sum()
        overall_occ = (total_used / total_capacity) if total_capacity > 0 else 0
        h3_count = occ_df["h3_id"].nunique()

        # 5) KPI Cards
        colA, colB, colC, colD = st.columns(4)
        with colA:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Total Capacity</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {int(total_capacity):,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with colB:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Used Site-Nights</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {int(total_used):,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with colC:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Occupancy Rate</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {overall_occ:.1%}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with colD:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;"># of H3 Cells</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {h3_count:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # 6) Expander for Definitions
        with st.expander("Click for definitions & notes"):
            st.caption(f"""
            **Date Range**: {start_d.strftime('%B %Y')} – {end_d.strftime('%Y-%m-%d')}
            
            **Category**: {chosen_category}  
            **Weekend Only**: {weekend_only}

            **Total Capacity (site-nights)**  
            Sum of `capacity_site_nights` across all H3 cells in this time window.

            **Used Site-Nights**  
            Sum of `used_site_nights` across all H3 cells.

            **Occupancy Rate**  
            `Used Site-Nights` ÷ `Total Capacity`.

            **# of H3 Cells**  
            Number of distinct H3 hex cells that have capacity > 0 in this time window.
            """)

        st.write("Toggle weekend-only to see if occupancy spikes on Fridays/Saturdays/Sundays.")

        # 7) Display the PyDeck Map
        local_occ = occ_df.copy()
        local_occ["color_array"] = local_occ["occupancy_rate"].apply(tiered_color_for_occupancy)

        tile_layer = pdk.Layer(
            "TileLayer",
            data="https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
            pickable=False,
            tile_size=256,
            opacity=0.7
        )

        occ_layer = pdk.Layer(
            "H3HexagonLayer",
            data=local_occ,
            get_hexagon="h3_id",
            get_fill_color="color_array",
            pickable=True,
            extruded=False,
            filled=True
        )

        view_state = pdk.ViewState(latitude=34.5, longitude=-85.0, zoom=4)
        tooltip = {
            "html": """
            <b>H3 ID:</b> {h3_id}<br/>
            <b>Occupancy Rate:</b> {occupancy_rate}<br/>
            <b>Capacity (site-nights):</b> {capacity_site_nights}<br/>
            <b>Used (site-nights):</b> {used_site_nights}
            """,
            "style":{"backgroundColor":"rgba(0,0,0,0.7)","color":"white"}
        }
        deck = pdk.Deck(layers=[tile_layer, occ_layer], initial_view_state=view_state, tooltip=tooltip)
        st.pydeck_chart(deck)

        # 8) Top 10 H3 Cells Table
        top_10 = local_occ.sort_values("occupancy_rate", ascending=False).head(10)
        st.subheader("Top 10 Highest-Occupancy H3 Cells")
        st.dataframe(top_10[["h3_id","capacity_site_nights","used_site_nights","occupancy_rate"]])


    # ===========================
    #  SEARCH DEMAND PAGE
    # ===========================
    elif page == "Search Demand":
        # 1) Banner Title
        st.markdown(
            """
            <div style="background-color:#EFF6EE; 
                        padding:1.0rem; 
                        border-radius:0.5rem; 
                        margin-bottom:1rem;">
                <h1 style="color:#126B37; margin-top:0; margin-bottom:0;">
                    Search Demand
                </h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 2) Compute some KPIs from df_search
        total_searches = df_search["searchers"].sum()
        distinct_dests = df_search["destination_h3_cell_id"].nunique()
        distinct_origins = df_search["origin_h3_cell_id"].nunique()
        avg_searches_per_dest = (total_searches / distinct_dests) if distinct_dests else 0

        # 3) KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div style="background-color:#FFFFFF;
                        padding:1rem;
                        border-radius:0.5rem;
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Total Searches</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {total_searches:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background-color:#FFFFFF;
                        padding:1rem;
                        border-radius:0.5rem;
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Distinct Destinations</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {distinct_dests:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background-color:#FFFFFF;
                        padding:1rem;
                        border-radius:0.5rem;
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Distinct Origins</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {distinct_origins:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div style="background-color:#FFFFFF;
                        padding:1rem;
                        border-radius:0.5rem;
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Avg Searches/Destination</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {avg_searches_per_dest:,.1f}
                </p>
            </div>
            """, unsafe_allow_html=True)

        # 4) Expander for definitions
        with st.expander("Click for definitions & notes"):
            st.caption("""
            **Total Searches**  
            Sum of `searchers` across all rows in `searches.csv`.

            **Distinct Destinations**  
            Unique `destination_h3_cell_id`s that appear in `searches.csv`.

            **Distinct Origins**  
            Unique `origin_h3_cell_id`s that appear in `searches.csv`.

            **Avg Searches / Destination**  
            `Total Searches` ÷ `Distinct Destinations`.
            """)

        # 5) Existing “mode” logic for Destination/Origin
        st.write("Visualize search volume by destination or origin hex. Also see breakdown by channel and type.")
        mode = st.radio("View Search Volume by:", ["Destination", "Origin"])

        if mode == "Destination":
            agg_dest = (
                df_search
                .groupby("destination_h3_cell_id")["searchers"]
                .sum()
                .reset_index()
                .rename(columns={"searchers":"total_searchers"})
            )
            deck_map = build_search_map(
                agg_dest,
                h3_col="destination_h3_cell_id",
                metric_col="total_searchers",
                tooltip_label="Dest Search Vol"
            )
            st.pydeck_chart(deck_map)

            top_10_dest = agg_dest.sort_values("total_searchers", ascending=False).head(10)
            st.subheader("Top 10 Destination H3s by Searchers")
            st.dataframe(top_10_dest)

            st.write("---")
            st.subheader("Group by Destination's Parent ID")
            if st.checkbox("Show parent_id grouping?"):
                parent_grp = (
                    df_search.groupby("destination_h3_parent_id")[["searchers","rv_searchers","tent_searchers"]]
                    .sum()
                    .reset_index()
                )
                st.dataframe(parent_grp.sort_values("searchers", ascending=False).head(15))

        else:
            agg_orig = (
                df_search
                .groupby("origin_h3_cell_id")["searchers"]
                .sum()
                .reset_index()
                .rename(columns={"searchers":"total_searchers"})
            )
            deck_map = build_search_map(
                agg_orig,
                h3_col="origin_h3_cell_id",
                metric_col="total_searchers",
                tooltip_label="Orig Search Vol"
            )
            st.pydeck_chart(deck_map)

            top_10_orig = agg_orig.sort_values("total_searchers", ascending=False).head(10)
            st.subheader("Top 10 Origin H3s by Searchers")
            st.dataframe(top_10_orig)

            st.write("---")
            st.subheader("Group by Origin's Parent ID")
            if st.checkbox("Show parent_id grouping?"):
                parent_grp = (
                    df_search.groupby("origin_h3_parent_id")[["searchers","rv_searchers","tent_searchers"]]
                    .sum()
                    .reset_index()
                )
                st.dataframe(parent_grp.sort_values("searchers", ascending=False).head(15))

        # 6) Channel & Type Breakdown
        st.write("---")
        st.subheader("Channel & Type Breakdown")

        channel_cols = [
            "seo_searchers","paid_search_engine_searchers","social_searchers",
            "sharing_searchers","direct_searchers","other_channel_searchers"
        ]
        df_channels = (
            df_search[channel_cols].sum()
            .reset_index().rename(columns={"index":"channel",0:"count_of_searchers"})
        )
        ch_bar = (
            alt.Chart(df_channels)
            .mark_bar()
            .encode(
                x=alt.X("count_of_searchers:Q", title="Searchers"),
                y=alt.Y("channel:N", sort="-x", title="Channel")
            )
            .properties(width=500, height=300)
        )
        st.altair_chart(ch_bar, use_container_width=True)

        st.subheader("Search Type Breakdown (Tent, RV, etc.)")
        type_cols = [
            "tent_searchers","rv_searchers","glamping_searchers",
            "family_friendly_searchers","pet_friendly_searchers","good_for_groups_searchers"
        ]
        counts = []
        for c in type_cols:
            if c in df_search.columns:
                counts.append((c, df_search[c].sum()))
        if counts:
            type_df = pd.DataFrame(counts, columns=["search_type","count_of_searchers"])
            type_bar = (
                alt.Chart(type_df)
                .mark_bar()
                .encode(
                    x=alt.X("count_of_searchers:Q", title="Searchers"),
                    y=alt.Y("search_type:N", sort="-x", title="Search Type")
                )
                .properties(width=500, height=300)
            )
            st.altair_chart(type_bar, use_container_width=True)
        else:
            st.write("No specialized search-type columns found in `searches.csv`.")


    # ===========================
    #  EXPANSION OPPORTUNITIES
    # ===========================
    elif page == "Expansion Opportunities":
        st.markdown(
            """
            <div style="background-color:#EFF6EE; 
                        padding:1.0rem; 
                        border-radius:0.5rem; 
                        margin-bottom:1rem;">
                <h1 style="color:#126B37; margin-top:0; margin-bottom:0;">
                    Expansion Opportunities
                </h1>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --------------------------------------------
        # 1) Partial-Year / Mismatch Summary Stats
        # --------------------------------------------


        total_capacity = expansion_data["partial_capacity"].sum()
        total_used = expansion_data["used_site_nights"].sum()
        overall_occ = (total_used / total_capacity) if total_capacity > 0 else 0
        h3_count = expansion_data["h3_id"].nunique()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Total Capacity (2028)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {int(total_capacity):,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Used Site-Nights (2028)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {int(total_used):,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">Avg Occupancy</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {overall_occ:.1%}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div style="background-color:#FFFFFF; 
                        padding:1rem; 
                        border-radius:0.5rem; 
                        border:1px solid #DDD;">
                <h4 style="margin-bottom:0.5rem; color:#126B37;">H3 Cells (SE)</h4>
                <p style="font-size:1.5rem; margin:0; font-weight:bold;">
                    {h3_count:,}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("Click for definitions & notes"):
            st.caption("""
            **Partial Year Logic**  
            - Capacity and used site-nights are prorated for 2028 based on each
              campground's went_live_date and each booking’s nights in 2028.

            **Total Capacity (2028)**  
            - Sum of partial_capacity for Southeastern H3 cells.

            **Used Site-Nights (2028)**  
            - Sum of used_site_nights in those H3 cells.

            **Avg Occupancy**  
            - used_site_nights ÷ partial_capacity.

            **H3 Cells (SE)**  
            - Distinct Southeastern H3 cells with any partial capacity.
            """)

        st.write("""
        Below, we identify **priority scores** and **mismatch ratios** 
        to highlight areas with high demand but insufficient supply.
        """)

        # --------------------------------------------
        # 1A) Priority Score
        # --------------------------------------------
        st.subheader("Preview: Priority Score")
        st.write("""
        *Priority Score = Occupancy Rate × Total Searchers*  
        Higher scores suggest areas that are both well-booked (higher occupancy) 
        **and** heavily searched.
        """)
        top_10 = expansion_data.sort_values("priority_score", ascending=False).head(10)
        st.dataframe(top_10[[
            "h3_id","partial_capacity","used_site_nights",
            "occupancy_rate","searchers","priority_score"
        ]])

        df_map = expansion_data[["h3_id","priority_score"]].copy()
        df_map["priority_score"] = df_map["priority_score"].round(0).astype(int)

        # Priority Score Map
        df_map = expansion_data[["h3_id","priority_score"]].copy()
        if not df_map.empty:
            clip_val = np.percentile(df_map["priority_score"], 95)
            df_map["clipped"] = df_map["priority_score"].clip(upper=clip_val)
        else:
            df_map["clipped"] = 0

        max_val = df_map["clipped"].max() if not df_map.empty else 0
        df_map["norm"] = df_map["clipped"] / max_val if max_val>0 else 0

        color_expr = """[
            255 + (20 - 255)*norm,
            255 + (96 - 255)*norm,
            100 + (22 - 100)*norm,
            200
        ]"""

        tile_layer = pdk.Layer(
            "TileLayer",
            data="https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
            pickable=False,
            tile_size=256,
            opacity=0.7
        )
        h3_layer = pdk.Layer(
            "H3HexagonLayer",
            data=df_map,
            get_hexagon="h3_id",
            get_fill_color=color_expr,
            pickable=True,
            extruded=False,
            filled=True
        )
        view_state = pdk.ViewState(latitude=34.5, longitude=-85.0, zoom=4)
        tooltip = {
            "html": "<b>H3 ID:</b> {h3_id}<br/><b>Priority Score:</b> {priority_score}",
            "style": {"backgroundColor":"rgba(0,0,0,0.7)","color":"white"}
        }
        deck_map = pdk.Deck(
            layers=[tile_layer, h3_layer],
            initial_view_state=view_state,
            tooltip=tooltip
        )
        st.pydeck_chart(deck_map)

        # --------------------------------------------
        # 1B) Mismatch Ratios (Demand > Supply)
        # --------------------------------------------
        st.write("---")
        st.subheader("Mismatch Ratios (Demand > Supply)")

        mismatch_metrics = [
            "rv_mismatch_ratio",
            "tent_mismatch_ratio",
            "structure_mismatch_ratio",
            "max_mismatch_ratio"
        ]
        chosen_mm = st.selectbox("Select mismatch metric:", mismatch_metrics, index=3)

        min_search = st.slider("Minimum total searchers to display:", 0, 5000, 100)
        map_df_2 = expansion_data[ expansion_data["searchers"] >= min_search ].copy()

        map_df_2["tent_searchers_adjusted"] = map_df_2["tent_searchers_adjusted"].round(0).astype(int)
        map_df_2["rv_searchers_adjusted"]   = map_df_2["rv_searchers_adjusted"].round(0).astype(int)
        map_df_2["structure_searchers_adjusted"] = map_df_2["structure_searchers_adjusted"].round(0).astype(int)


        if not map_df_2.empty:
            clip_val_2 = np.percentile(map_df_2[chosen_mm], 95)
            # For safety, also cap at 10 if you want "infinite" to be 10:
            map_df_2[chosen_mm] = map_df_2[chosen_mm].clip(upper=10)
            map_df_2["clipped"] = map_df_2[chosen_mm].clip(upper=clip_val_2)
        else:
            map_df_2["clipped"] = 0

        mm_max_val = map_df_2["clipped"].max() if not map_df_2.empty else 0
        map_df_2["norm"] = map_df_2["clipped"] / mm_max_val if mm_max_val>0 else 0

        def mismatch_str(x):
            return "∞" if x >= 10 else round(x,2)
        map_df_2["mismatch_display"] = map_df_2[chosen_mm].apply(mismatch_str)

        mismatch_color_expr = """[
            255,
            255 * (1 - norm),
            150 * (1 - norm),
            200
        ]"""

        tile_layer_mismatch = pdk.Layer(
            "TileLayer",
            data="https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
            pickable=False,
            tile_size=256,
            opacity=0.7
        )

        # Tooltip references the same columns as before:
        tooltip_html = """
        <div style="font-size:0.85em;">
          <b>H3 ID:</b> {h3_id}<br/><br/>
          
          <b>Tent Capacity:</b> {tent_capacity}<br/>
          <b>Tent Demand (Adj):</b> {tent_searchers_adjusted}<br/>
          <b>Tent Mismatch:</b> {tent_mismatch_ratio}<br/><br/>

          <b>RV Capacity:</b> {rv_capacity}<br/>
          <b>RV Demand (Adj):</b> {rv_searchers_adjusted}<br/>
          <b>RV Mismatch:</b> {rv_mismatch_ratio}<br/><br/>

          <b>Structure Capacity:</b> {structure_capacity}<br/>
          <b>Glamping Demand (Adj):</b> {structure_searchers_adjusted}<br/>
          <b>Structure Mismatch:</b> {structure_mismatch_ratio}<br/><br/>

          <b>Total Searchers:</b> {searchers}<br/>
          <b>General Searchers:</b> {general_searchers}<br/>
          <b>Max Mismatch Ratio:</b> {max_mismatch_ratio}
        </div>
        """

        h3_layer_mismatch = pdk.Layer(
            "H3HexagonLayer",
            data=map_df_2,
            get_hexagon="h3_id",
            get_fill_color=mismatch_color_expr,
            pickable=True,
            extruded=False,
            filled=True
        )
        mismatch_tip = {
            "html": tooltip_html,
            "style":{"backgroundColor":"rgba(0,0,0,0.7)","color":"white"}
        }
        mismatch_view_state = pdk.ViewState(latitude=34.5, longitude=-85.0, zoom=4)
        mismatch_deck = pdk.Deck(
            layers=[tile_layer_mismatch, h3_layer_mismatch],
            initial_view_state=mismatch_view_state,
            tooltip=mismatch_tip
        )
        st.pydeck_chart(mismatch_deck)

        with st.expander("Click for definitions & notes on mismatch ratio"):
            st.markdown("""
        **Partial-Year Capacity**  
        Each campground’s capacity is prorated for the fraction of 2028 it was live 
        (e.g. if it went live on 2028-05-01, only ~8 months of capacity count).  
        For each site type (RV, tent, structure), we calculate **site_nights** = (days live) × (number of sites).

        ---

        **Search Demand**  
        We split total searchers into **RV**, **Tent**, and **Structure** (Glamping) buckets.  
        If a search is general (no specific type), we distribute that general portion **proportionally** 
        among RV/Tent/Structure based on the hex’s existing breakdown.

        ---

        **Mismatch Ratio**  
        - If ratio \\(> 0\\), demand exceeded local site capacity.  
        - If ratio \\(= 10\\), there was **no** supply in that category, but **some** demand.  
        - The **map** colors each H3 hex by the **max** mismatch ratio across RV, Tent, and Structure.
        """)


        st.write(f"**Note**: Only hexes with ≥ {min_search} total searchers shown. Darker color = higher {chosen_mm}.")


        # ===============================================
        #  LOST REVENUE ESTIMATE (REAL CONVERSION & RATE)
        # ===============================================
        st.subheader("Lost Revenue from Unmet Demand (Using Actual Conversion & Rate)")

        # 1) Filter Southeastern Campgrounds
        df_camp_se = df_camp[
            (df_camp["campground_region"] == "Southeast") 
            & (df_camp["went_live_date"].notnull())
        ].copy()

        # 2) Merge Southeastern Campgrounds with valid transactions
        df_trans_se = df_trans_valid.merge(
            df_camp_se[["campground_uuid","campground_h3_hexagon_id_l4"]],
            on="campground_uuid",
            how="inner"
        )

        # Keep only bookings with partial nights in 2028:
        df_trans_se_2028 = df_trans_se[df_trans_se["partial_nights_2028"] > 0].copy()

        # A) Actual Southeastern Bookings & Searches
        total_bookings_se = df_trans_se_2028["booking_uuid"].nunique()

        total_searchers_se = expansion_data["searchers"].sum()

        # B) Compute Real Conversion Rate
        if total_searchers_se > 0:
            actual_conversion_rate = total_bookings_se / total_searchers_se
        else:
            actual_conversion_rate = 0

        # C) Compute Actual Average Nightly Rate (Southeast, partial 2028)
        total_nights_se_2028 = df_trans_se_2028["partial_nights_2028"].sum()
        total_revenue_se_2028 = df_trans_se_2028["partial_revenue_2028"].sum()

        if total_nights_se_2028 > 0:
            average_nightly_rate_se = total_revenue_se_2028 / total_nights_se_2028
        else:
            average_nightly_rate_se = 0

        # D) Calculate "Unfilled" site-nights using the mismatch approach
        df_loss = expansion_data.copy() 

        # For each category, unfilled = max(demand - supply, 0)
        df_loss["rv_unfilled"] = np.maximum(
            df_loss["rv_searchers_adjusted"] - df_loss["rv_capacity"], 0
        )
        df_loss["tent_unfilled"] = np.maximum(
            df_loss["tent_searchers_adjusted"] - df_loss["tent_capacity"], 0
        )
        df_loss["structure_unfilled"] = np.maximum(
            df_loss["structure_searchers_adjusted"] - df_loss["structure_capacity"], 0
        )

        # Sum across categories to get total unfilled site-nights per hex
        df_loss["unfilled_site_nights"] = (
            df_loss["rv_unfilled"] 
            + df_loss["tent_unfilled"] 
            + df_loss["structure_unfilled"]
        )

        # E) Multiply by real conversion rate & real nightly rate
        df_loss["lost_revenue_per_hex"] = (
            df_loss["unfilled_site_nights"] 
            * actual_conversion_rate 
            * average_nightly_rate_se
        )

        # F) Sum across all Southeastern hexes
        total_unfilled = df_loss["unfilled_site_nights"].sum()
        # Multiply by 2 for avg booking length
        total_lost_revenue = df_loss["lost_revenue_per_hex"].sum() * 2

        # G) Display
        st.write(f"**Actual Conversion Rate (SE, 2028):** {actual_conversion_rate:.2%}")
        st.write(f"**Average Nightly Rate (SE, 2028):** ${average_nightly_rate_se:,.2f}")
        st.write(f"**Total Unfilled Demand:** {total_unfilled:,.0f}")
        st.write(f"**Estimated Lost Revenue:** ${total_lost_revenue:,.0f}")

        st.caption(r"""
        **Key Points**:
        - We treat each "searcher" as a potential **booking**, then multiply by 
          an **actual conversion rate** and an **actual average length of stay** 
          to get **demand in site-nights**.
        - Compare that to **site-night capacity** to find unfilled site-nights.
        - Multiply unfilled site-nights by the **actual average nightly rate** 
          to estimate potential revenue that was missed.
        """)


        # --------------------------------------------
        # 2) Simple Market Size / ARVC Benchmarking
        # --------------------------------------------
        st.write("---")
        st.header("Simplified Benchmarking & Potential Gains")

        # ---  A) Basic average rate & nights (still from actual transaction data) ---
        df_2028_only = df_trans_valid[df_trans_valid["partial_nights_2028"] > 0].copy()
        total_nights_2028 = df_2028_only["partial_nights_2028"].sum()
        total_revenue_2028 = df_2028_only["partial_revenue_2028"].sum()
        total_bookings_2028 = df_2028_only["booking_uuid"].nunique()

        if total_bookings_2028 > 0:
            avg_nights_per_booking = total_nights_2028 / total_bookings_2028
            avg_revenue_per_booking = total_revenue_2028 / total_bookings_2028
            avg_revenue_per_night = total_revenue_2028 / total_nights_2028 if total_nights_2028 else 0
        else:
            avg_nights_per_booking = 0
            avg_revenue_per_booking = 0
            avg_revenue_per_night = 0

        st.markdown(f"""
        **Average Revenue per Booking (2028):** 
        \\${avg_revenue_per_booking:,.0f}  
        **Average Nights per Booking (2028):** 
        {avg_nights_per_booking:,.1f}  
        **Average Revenue per Night:** 
        \\${avg_revenue_per_night:,.0f}
        """)

        # --- B) Simple assumption: flat 45% occupancy across the Southeast
        st.write("---")
        st.subheader("Assume 45% Occupancy")

        st.markdown("""
        We assume each site is open all year, and **45%** is a typical 
        annual occupancy (for simplicity).  
        > ARVC benchmarks might be higher for some site types (e.g., ~68% for RVs), 
        > but we use 45% as a conservative baseline.
        """)

        total_capacity_se = expansion_data["partial_capacity"].sum()

        # Simple 45% assumption for capacity:
        assumed_used_45 = total_capacity_se * 0.45

        # Potential revenue if we fill those 45%-occupied nights at 
        # the average nightly rate from above:
        estimated_rev_45 = assumed_used_45 * avg_revenue_per_night

        st.markdown(f"""
        **Total SE Capacity (Partial-Year):** {total_capacity_se:,.0f} site-nights  
        **At 45% Occupancy:** {assumed_used_45:,.0f} site-nights used  
        **Estimated Revenue (at 45%):** \\${estimated_rev_45:,.0f}
        """)

        st.write("""
        This quick calculation gives a **rough** market-size estimate. 
        It applies our **flat 45%** occupancy assumption to the 
        total Southeastern capacity (partial-year), multiplied by our 
        2028 average nightly rate. 
        """)

        st.write("---")
        st.markdown("""
        ### Next Steps
        - Refine occupancy estimates by state, site type, or season.
        - Compare to detailed ARVC numbers for RV vs. tent vs. structure.
        - Evaluate marketing strategies to push occupancy above 45%.
        """)





if __name__=="__main__":
    main()
