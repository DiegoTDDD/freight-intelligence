from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboards/app.py"


def test_trip_planner_cost_waiting_limits_and_translation():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="workspace").select("Trip cost and breaks").run()
    assert not app.exception and not app.error
    assert any(m.label == "Reviewed toll estimate (BRL)" and m.value == "57.60" for m in app.metric)
    assert any(m.label == "Work including waiting (min)" and m.value == "240" for m in app.metric)
    app.number_input(key="trip_waiting_minutes").set_value(421)
    app.checkbox(key="trip_overtime").check()
    app.button[0].click().run()
    assert not app.exception and not app.error
    assert any(item.value == "Selected planning limits exceeded" for item in app.info)
    app.selectbox(key="language").select("pt").run()
    assert app.number_input(key="trip_axles").label == "Eixos cobrados do caminhão carregado"
    assert any("não autoriza despacho" in item.value for item in app.warning)
    app.number_input(key="trip_origin").set_value(100.0)
    app.button[0].click().run()
    assert not app.exception and app.error and not app.metric
