import sys
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import uvicorn
from graphql_server.schema import schema
from tracing import setup_tracer, instrument_fastapi_app
from config import GRAPHQL_SERVER_HOST, GRAPHQL_SERVER_PORT, GRAPHQL_URL

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

tracer = setup_tracer("graphql-server")
app = FastAPI(title="GraphQL Server")
instrument_fastapi_app(app)
app.include_router(GraphQLRouter(schema), prefix="/graphql")

if __name__ == "__main__":
    print(f"GraphQL Server đang chạy tại: {GRAPHQL_URL}")
    uvicorn.run("graphql_server.main:app", host=GRAPHQL_SERVER_HOST, port=GRAPHQL_SERVER_PORT)
