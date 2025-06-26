from fastapi import FastAPI, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, text
import pandas as pd
import os
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
import io

load_dotenv()
app = FastAPI()
engine = create_engine(os.getenv("DATABASE_URL"))
templates = Jinja2Templates(directory="templates")

@app.get("/")
def dashboard(request: Request):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM "AirQualityRecord"
            ORDER BY timestamp DESC
            LIMIT 100
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    avg_aqi = float(round(df['aqi'].mean(), 1))
    avg_pm25 = float(round(df['pm25'].mean(), 1))
    top_city = str(df.loc[df['aqi'].idxmax(), 'city_id'])

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "df": df.to_dict(orient="records"),
        "avg_aqi": avg_aqi,
        "avg_pm25": avg_pm25,
        "top_city": top_city
    })

@app.get("/air-quality")
def get_latest_air_quality():
    query = 'SELECT * FROM "AirQualityRecord" ORDER BY timestamp DESC LIMIT 100'
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/kpi-summary")
def kpi_summary():
    query = 'SELECT aqi, pm25, city_id FROM "AirQualityRecord" ORDER BY timestamp DESC LIMIT 100'
    df = pd.read_sql(query, engine)
    return {
        "avg_aqi": float(round(df['aqi'].mean(), 1)),
        "avg_pm25": float(round(df['pm25'].mean(), 1)),
        "top_city_id": str(df.loc[df['aqi'].idxmax(), 'city_id'])
    }

@app.get("/cities")
def get_cities():
    query = 'SELECT DISTINCT city_id FROM "AirQualityRecord"'
    df = pd.read_sql(query, engine)
    return df['city_id'].tolist()

@app.get("/province-summary")
def get_province_summary():
    query = '''
        SELECT c.province, AVG(a.aqi) as avg_aqi
        FROM "AirQualityRecord" a
        JOIN "City" c ON a.city_id = c.city_id
        GROUP BY c.province
        ORDER BY avg_aqi DESC
    '''
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/time-series")
def time_series(city_id: int = Query(...)):
    query = f'''
        SELECT timestamp, aqi
        FROM "AirQualityRecord"
        WHERE city_id = {city_id}
        ORDER BY timestamp ASC
    '''
    df = pd.read_sql(query, engine)
    df['timestamp'] = df['timestamp'].astype(str)
    return df.to_dict(orient="records")

@app.get("/map-data")
def get_map_data():
    query = '''
        SELECT aqi, c.city_name, c.latitude, c.longitude
        FROM "AirQualityRecord" a
        JOIN "City" c ON a.city_id = c.city_id
        ORDER BY timestamp DESC
        LIMIT 200
    '''
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/source-breakdown")
def get_source_summary():
    query = '''
        SELECT s.source_name, COUNT(*) as total
        FROM "AirQualityRecord" a
        JOIN "Source" s ON a.source_id = s.source_id
        GROUP BY s.source_name
    '''
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/filter")
def filter_data(
    city_id: int = Query(None),
    source_id: int = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None)
):
    filters = []
    if city_id:
        filters.append(f"city_id = {city_id}")
    if source_id:
        filters.append(f"source_id = {source_id}")
    if start_time and end_time:
        filters.append(f"timestamp BETWEEN '{start_time}' AND '{end_time}'")

    filter_clause = " AND " .join(filters)
    if filter_clause:
        query = f'SELECT * FROM "AirQualityRecord" WHERE {filter_clause} ORDER BY timestamp DESC LIMIT 200'
    else:
        query = 'SELECT * FROM "AirQualityRecord" ORDER BY timestamp DESC LIMIT 100'

    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/table/{table_name}")
def get_entire_table(table_name: str):
    try:
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql(query, engine)
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@app.get("/realtime-tab")
def realtime_tab():
    query = '''
        SELECT * FROM "AirQualityRecord"
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY timestamp DESC
    '''
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")

@app.get("/calculation-tab")
def calculation_tab():
    query = '''
        SELECT city_id, date_trunc('day', timestamp) as day, AVG(aqi) as avg_aqi, MAX(aqi) as max_aqi
        FROM "AirQualityRecord"
        GROUP BY city_id, day
        ORDER BY day DESC, city_id
        LIMIT 200
    '''
    df = pd.read_sql(query, engine)
    df['day'] = df['day'].astype(str)
    return df.to_dict(orient="records")

@app.get("/latest-by-city")
def latest_by_city():
    query = """
        SELECT DISTINCT ON (city_id) *
        FROM "AirQualityRecord"
        ORDER BY city_id, timestamp DESC
    """
    df = pd.read_sql(query, engine)
    return df.to_dict(orient="records")
