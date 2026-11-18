"""Per-render localization adapter; never mutate Streamlit or session values."""

import streamlit as st

from freight_intelligence.dashboard_modal_i18n import COLUMNS, LABELS


class LocalizedUI:
    def __init__(self, translate):
        self.translate = translate

    def __getattr__(self, name):
        command = getattr(st, name)
        if name == "dataframe":
            def table(data, **kwargs):
                if hasattr(data, "columns"):
                    kwargs.setdefault("column_config", {column: self.translate(COLUMNS.get(column, column))
                                                        for column in data.columns})
                return command(data, **kwargs)
            return table
        text_commands = {"title", "header", "subheader", "caption", "text", "write", "markdown",
                         "info", "warning", "error", "success", "selectbox", "radio", "checkbox",
                         "number_input", "button", "download_button", "expander", "metric"}
        if name not in text_commands:
            return command

        def localized(*args, **kwargs):
            if args and isinstance(args[0], str):
                args = (self.translate(args[0]), *args[1:])
            if isinstance(kwargs.get("help"), str):
                kwargs["help"] = self.translate(kwargs["help"])
            if name in {"selectbox", "radio"}:
                formatter = kwargs.get("format_func", str)
                def label(value):
                    formatted = formatter(value)
                    return self.translate(LABELS.get(formatted, formatted))
                kwargs["format_func"] = label
            return command(*args, **kwargs)

        return localized
