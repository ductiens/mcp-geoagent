import requests

REST_API_URL = "http://127.0.0.1:8001"


def get_weather(city: str) -> dict:
    """Gọi REST Server nội bộ tại cổng 8001 để lấy thông tin thời tiết."""
    res = requests.get(
        f"{REST_API_URL}/api/weather",
        params={"city": city},
        timeout=10,
    )
    if res.status_code == 404:
        raise ValueError(f"Không tìm thấy thành phố: {city}")
    res.raise_for_status()
    return res.json()


def search_music(query: str, limit: int = 3) -> list:
    """Gọi REST Server nội bộ tại cổng 8001 để tìm kiếm bài hát."""
    res = requests.get(
        f"{REST_API_URL}/api/music",
        params={"query": query, "limit": limit},
        timeout=10,
    )
    res.raise_for_status()
    return res.json()
