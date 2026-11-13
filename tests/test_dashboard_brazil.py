from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboards/app.py"


def test_english_default_and_optional_portuguese_brazil_evaluation(monkeypatch):
    monkeypatch.delenv("LOGINEXUS_LANGUAGE", raising=False)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert app.selectbox(key="language").value == "en"
    assert app.selectbox(key="workspace").label == "Workspace"
    app.selectbox(key="language").select("pt").run()
    app.selectbox(key="workspace").select("Brazilian freight").run()
    assert not app.exception and not app.error
    assert any(item.value == "Transporte ferroviário de cargas no Brasil" for item in app.subheader)
    assert any(item.label == "Anos completos" and item.value == "20" for item in app.metric)
    assert any("2023–2025" in item.value for item in app.caption)
    app.selectbox(key="brazil_metric").select("tonne_km").run()
    assert not app.exception
    assert "TKU" in app.metric[0].value
    app.selectbox(key="language").select("en").run()
    assert any(item.value == "Brazilian railway freight" for item in app.subheader)


def test_saved_real_route_and_consent_before_live_requests(monkeypatch):
    monkeypatch.delenv("LOGINEXUS_LANGUAGE", raising=False)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="language").select("pt").run()
    app.selectbox(key="workspace").select("Real road routes").run()
    app.button[0].click().run()
    assert any("Confirme" in item.value for item in app.error)
    assert not app.metric
    app.button[1].click().run()
    assert not app.exception
    assert any(
        item.label == "Distância da rota (km)" and item.value == "93.17" for item in app.metric
    )
    assert "OSRM" in app.get("json")[0].value


def test_truck_form_and_saved_truck_itinerary():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="workspace").select("Real road routes").run()
    app.selectbox(key="routing_engine").select("Truck (Valhalla)").run()
    assert not app.exception
    assert app.number_input(key="truck_Urban rigid truck (example)_weight").value == 16.0
    app.selectbox(key="truck_profile").select("Articulated truck (example)").run()
    assert not app.exception
    assert app.number_input(key="truck_Articulated truck (example)_weight").value == 40.0
    app.button[2].click().run()
    assert not app.exception and not app.error
    assert app.metric[0].value == "98.77"
    assert any("Calculated profile: truck" in item.value for item in app.caption)


def test_all_five_modal_views_load_with_explicit_scope():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="workspace").select("Brazilian freight").run()
    app.selectbox(key="brazil_view").select("All five modes").run()
    for mode in ("road", "rail", "water", "air", "pipeline"):
        app.selectbox(key="brazil_mode").select(mode).run()
        assert not app.exception and not app.error
        assert app.metric and app.dataframe
        assert any("not comparable modal shares" in item.value for item in app.info)
    assert any(item.label == "Missing daily cells" and item.value == "2" for item in app.metric)
    app.selectbox(key="brazil_gas_point_type").select("receipt").run()
    assert not app.exception and not app.error
    assert any(item.label == "Missing daily cells" and item.value == "31" for item in app.metric)


def test_water_navigation_and_regional_reference_views():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="workspace").select("Brazilian freight").run()
    app.selectbox(key="brazil_view").select("All five modes").run()
    app.selectbox(key="brazil_mode").select("water").run()
    for dataset in ("navigation_totals", "inland_commodities",
                    "coastal_state_endpoints", "grain_regions"):
        app.selectbox(key="brazil_water_dataset").select(dataset).run()
        assert not app.exception and not app.error
        assert any("State endpoints do not identify paired routes" in item.value for item in app.warning)
    app.selectbox(key="water_year_grain_regions").select(2024).run()
    assert not app.exception


def test_regional_road_filters_and_unlisted_pairs():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="workspace").select("Brazilian freight").run()
    app.selectbox(key="brazil_view").select("All five modes").run()
    app.selectbox(key="brazil_mode").select("road").run()
    assert not app.exception and not app.error
    assert any(item.label == "MDF-e tonnes · sum of 12 published months"
               and item.value == "1,368,699,651" for item in app.metric)
    assert any("consistent with" in item.value for item in app.success)
    assert any(item.label == "Published flows matching filters" and item.value == "16" for item in app.metric)
    app.selectbox(key="road_origin_state").select("PA").run()
    assert any(item.label == "Published flows matching filters" and item.value == "2" for item in app.metric)
    app.selectbox(key="road_destination_state").select("SP").run()
    assert not app.exception and not app.error
    assert any("Unlisted flows are unavailable, not zero" in item.value for item in app.info)
