
from pathlib import Path

import polars as pl
import streamlit as st

BASE = Path("data/gold/faf5")

st.set_page_config(
    page_title="Freight Intelligence",
    page_icon="🚚",
    layout="wide",
)

st.title("🚚 Freight Intelligence")
st.caption("FAF5 Freight Flow Analytics")


@st.cache_data
def load_data():
    annual = pl.read_parquet(BASE / "annual_kpis.parquet")
    commodity = pl.read_parquet(BASE / "commodity_mix.parquet")
    mode = pl.read_parquet(BASE / "mode_mix.parquet")
    corridors = pl.read_parquet(BASE / "top_corridors.parquet")
    growth = pl.read_parquet(BASE / "annual_growth.parquet")
    cagr = pl.read_parquet(BASE / "annual_cagr.parquet")
    commodity_growth = pl.read_parquet(BASE / "commodity_growth.parquet")
    share_change = pl.read_parquet(BASE / "commodity_share_change.parquet")

    return (
        annual,
        commodity,
        mode,
        corridors,
        growth,
        cagr,
        commodity_growth,
        share_change,
    )


(
    annual,
    commodity,
    mode,
    corridors,
    growth,
    cagr,
    commodity_growth,
    share_change,
) = load_data()

METRICS = {
    "Tons": "tons",
    "Freight value": "value",
    "Ton-miles": "tmiles",
}

metric_label = st.selectbox("Primary metric", list(METRICS))
metric_type = METRICS[metric_label]

# KPIs
selected_annual = annual.filter(pl.col("metric_type") == metric_type)
latest_year = selected_annual["year"].max()
latest = selected_annual.filter(pl.col("year") == latest_year)

latest_total = latest["total_value"].item()
latest_growth = growth.filter(
    (pl.col("metric_type") == metric_type)
    & (pl.col("year") == latest_year)
)

growth_rate = (
    latest_growth["growth_rate"].item() * 100
    if latest_growth.height
    and latest_growth["growth_rate"].item() is not None
    else None
)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Forecast year", latest_year)
kpi2.metric(metric_label, f"{latest_total:,.0f}")
kpi3.metric(
    "Annual growth",
    f"{growth_rate:+.2f}%" if growth_rate is not None else "N/A",
)

st.divider()

# Annual evolution
st.subheader("Annual Freight Evolution")

annual_chart = (
    selected_annual
    .select(["year", "total_value"])
    .sort("year")
    .to_pandas()
    .set_index("year")
)
st.line_chart(annual_chart)

# Annual growth
st.subheader("Annual Growth Analysis")

selected_growth = (
    growth.filter(pl.col("metric_type") == metric_type)
    .sort("year")
)

growth_chart = (
    selected_growth
    .select(["year", "absolute_change"])
    .drop_nulls()
    .to_pandas()
    .set_index("year")
)
st.caption("Absolute year-over-year change")
st.bar_chart(growth_chart)

growth_table = (
    selected_growth
    .select(
        [
            "year",
            "total_value",
            "previous_total_value",
            "absolute_change",
            "growth_rate",
        ]
    )
    .with_columns(
        (pl.col("growth_rate") * 100).alias("growth_rate_pct")
    )
    .drop("growth_rate")
    .rename({"growth_rate_pct": "growth_rate_percent"})
)
st.dataframe(growth_table.to_pandas(), width="stretch")

# CAGR
st.subheader("Compound Annual Growth Rate (CAGR)")

cagr_table = (
    cagr
    .with_columns((pl.col("cagr") * 100).alias("cagr_percent"))
    .select(
        [
            "metric_type",
            "start_year",
            "end_year",
            "start_value",
            "end_value",
            "cagr_percent",
        ]
    )
)
st.dataframe(cagr_table.to_pandas(), width="stretch")

# Commodity growth
st.subheader("Commodity Growth")

top_n = st.slider("Number of commodities", min_value=5, max_value=20, value=10)
top_commodities = commodity_growth.sort("cagr", descending=True).head(top_n)

commodity_chart = (
    top_commodities
    .select(["commodity_name", "cagr"])
    .with_columns((pl.col("cagr") * 100).alias("cagr_percent"))
    .select(["commodity_name", "cagr_percent"])
    .to_pandas()
    .set_index("commodity_name")
)
st.bar_chart(commodity_chart)

commodity_table = top_commodities.with_columns(
    (pl.col("cagr") * 100).alias("cagr_percent")
)
st.dataframe(commodity_table.to_pandas(), width="stretch")

# Commodity share changes
st.subheader("Change in Commodity Share")

share_direction = st.radio(
    "Show",
    ["All", "Share gained", "Share lost"],
    horizontal=True,
)

filtered_shares = share_change
if share_direction == "Share gained":
    filtered_shares = filtered_shares.filter(pl.col("share_change") > 0)
elif share_direction == "Share lost":
    filtered_shares = filtered_shares.filter(pl.col("share_change") < 0)

share_table = (
    filtered_shares
    .sort("share_change", descending=True)
    .with_columns(
        (pl.col("start_share") * 100).alias("start_share_percent"),
        (pl.col("end_share") * 100).alias("end_share_percent"),
        (pl.col("share_change") * 100).alias("share_change_pp"),
    )
)
st.dataframe(share_table.to_pandas(), width="stretch")

# Freight modes
st.subheader("Freight Mode Mix")
mode_latest = mode.filter(pl.col("year") == latest_year)
st.dataframe(mode_latest.to_pandas(), width="stretch")

# Top corridors
st.subheader("Top Freight Corridors")
top = (
    corridors
    .filter(pl.col("year") == latest_year)
    .sort("tons", descending=True)
    .head(20)
)
st.dataframe(top.to_pandas(), width="stretch")

# Commodity mix
st.subheader("Commodity Mix")

commodity_years = sorted(commodity["year"].unique().to_list())
selected_year = st.selectbox(
    "Commodity mix year",
    commodity_years,
    index=len(commodity_years) - 1,
)

commodity_latest = commodity.filter(pl.col("year") == selected_year)
st.dataframe(commodity_latest.to_pandas(), width="stretch")

st.caption(
    "Source: Freight Analysis Framework (FAF5), "
    "U.S. Bureau of Transportation Statistics / ORNL."
)
