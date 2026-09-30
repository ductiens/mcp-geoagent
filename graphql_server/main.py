from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import uvicorn
from graphql_server.schema import schema

app = FastAPI(title="GraphQL Server")
app.include_router(GraphQLRouter(schema), prefix="/graphql")

if __name__ == "__main__":
    print("GraphQL Server đang chạy tại: http://127.0.0.1:8002/graphql")
    uvicorn.run("graphql_server.main:app", host="127.0.0.1", port=8002)
