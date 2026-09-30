from typing import List, Optional
import strawberry
from graphql_server.rest_client import get_weather, search_music

# 1. Weather Data Type
@strawberry.type
class Weather:
    city: str
    temperature: float
    humidity: int
    wind_speed: float


# 2. Music Track Data Type
@strawberry.type
class MusicTrack:
    track_name: str
    artist_name: str
    album_name: str
    preview_url: Optional[str] = ""


# 3. GraphQL Root Query
@strawberry.type
class Query:
    @strawberry.field(description="Get real-time weather by city name")
    def weather(self, city: str) -> Weather:
        data = get_weather(city)
        return Weather(**data)

    @strawberry.field(description="Search songs by title or artist keyword")
    def search_music(self, query: str, limit: int = 3) -> List[MusicTrack]:
        tracks = search_music(query, limit)
        return [MusicTrack(**t) for t in tracks]


schema = strawberry.Schema(query=Query)
