import streamlit as st
import polars as pl
from pathlib import Path


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

    return annual, commodity, mode, corridors


annual, commodity, mode, corridors = load_data()


# KPIs
tons = annual.filter(pl.col("metric_type") == "tons")
value = annual.filter(pl.col("metric_type") == "value")

latest_year = tons["year"].max()

latest_tons = tons.filter(
    pl.col("year") == latest_year
)["total_value"].item()

latest_value = value.filter(
    pl.col("year") == latest_year
)["total_value"].item()


col1, col2, col3 = st.columns(3)

col1.metric(
    "Forecast Year",
    latest_year,
)

col2.metric(
    "Freight Volume",
    f"{latest_tons:,.0f}",
)

col3.metric(
    "Freight Value",
    f"{latest_value:,.0f}",
)


st.divider()


# Annual evolution
st.subheader("Freight Volume Evolution")

annual_tons = (
    tons
    .select(["year", "total_value"])
    .sort("year")
    .to_pandas()
    .set_index("year")
)

st.line_chart(annual_tons)


# Freight modes
st.subheader("Freight Mode Mix")

mode_latest = mode.filter(
    pl.col("year") == latest_year
)

st.dataframe(
    mode_latest.to_pandas(),
    use_container_width=True,
)


# Top corridors
st.subheader("Top Freight Corridors")

top = (
    corridors
    .filter(pl.col("year") == latest_year)
    .sort("tons", descending=True)
    .head(20)
)

st.dataframe(
    top.to_pandas(),
    use_container_width=True,
)


st.caption(
    "Source: Freight Analysis Framework (FAF5), "
    "U.S. Bureau of Transportation Statistics / ORNL."
)