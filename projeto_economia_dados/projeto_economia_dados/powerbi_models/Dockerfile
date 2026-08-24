FROM python:3.9-slim
WORKDIR /app
COPY dashboard_completo.py .
RUN pip install streamlit pandas sqlalchemy psycopg2-binary plotly
EXPOSE 8501
CMD ["streamlit", "run", "dashboard_completo.py", "--server.port=8501", "--server.address=0.0.0.0"]
