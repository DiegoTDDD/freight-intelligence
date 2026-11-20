from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboards/app.py"


def test_weekly_review_examples_missing_data_translation_and_invalid_json():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key="workspace").select("Trip cost and breaks").run()
    app.radio(key="trip_planning_view").set_value("Seven-day duty review").run()
    assert not app.exception and not app.error
    assert any(m.label == "Covered hours" and m.value == "168.00" for m in app.metric)
    assert any(m.label == "Declared work hours" and m.value == "44.00" for m in app.metric)
    for name in ("short_daily_rest", "seven_workdays"):
        app.selectbox(key="weekly_example").select(name).run()
        assert not app.exception and not app.error
        assert any(i.value == "Selected planning limits exceeded" for i in app.info)
    app.selectbox(key="weekly_example").select("night_shift").run()
    assert not app.exception and not app.error
    assert any(m.label == "Actual night work hours" and m.value == "6.00" for m in app.metric)
    assert any(m.label == "Base-window equivalent work hours" and m.value == "7.86" for m in app.metric)
    assert any(i.value == "Separate review required" for i in app.info)
    app.selectbox(key="language").select("pt").run()
    assert any(m.label == "Horas reais de trabalho noturno" and m.value == "6.00" for m in app.metric)
    app.selectbox(key="language").select("en").run()
    app.selectbox(key="weekly_example").select("incomplete_week").run()
    assert any(i.value == "Separate review required" for i in app.info)
    app.selectbox(key="language").select("pt").run()
    assert app.selectbox(key="weekly_example").label == "Exemplo semanal"
    assert any("Nenhum resultado autoriza despacho" in i.value for i in app.warning)
    app.text_area(key="weekly_json_incomplete_week").set_value("{}")
    app.button[0].click().run()
    assert not app.exception and app.error and not app.metric
