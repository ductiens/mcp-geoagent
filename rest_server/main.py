from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import uvicorn

app = FastAPI(title="REST API")

# Schema
class WeatherResponse(BaseModel):
    city: str
    temperature: float
    humidity: int
    wind_speed: float

class MusicTrackResponse(BaseModel):
    track_name: str
    artist_name: str
    album_name: str
    preview_url: Optional[str] = None

# Endpoints 
@app.get("/api/weather", response_model=WeatherResponse)
def get_weather(city: str):
    # 1. Tìm tọa độ theo tên thành phố
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    ).json()
    if not geo.get("results"):
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thành phố: {city}")
    loc = geo["results"][0]

    # 2. Lấy thời tiết từ tọa độ
    cur = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        },
        timeout=10,
    ).json()["current"]

    return {
        "city": loc["name"],
        "temperature": cur["temperature_2m"],
        "humidity": cur["relative_humidity_2m"],
        "wind_speed": cur["wind_speed_10m"],
    }

@app.get("/api/music", response_model=List[MusicTrackResponse])
def search_music(query: str, limit: int = 3):
    try:
        rows = requests.get(
            "https://itunes.apple.com/search",
            params={"term": query, "entity": "song", "country": "VN", "limit": limit},
            timeout=10,
        ).json().get("results", [])
    except Exception:
        rows = []

    return [
        {
            "track_name": r.get("trackName", ""),
            "artist_name": r.get("artistName", ""),
            "album_name": r.get("collectionName", ""),
            "preview_url": r.get("previewUrl"),
        }
        for r in rows
    ]

if __name__ == "__main__":
    uvicorn.run("rest_server.main:app", host="127.0.0.1", port=8001)
