from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.channels.service import start_channel_service
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 定义启动和关闭的逻辑。
    print("Application startup")
    await start_channel_service()
    yield
    print("Application shutdown")


app = FastAPI(

    lifespan=lifespan,

)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Service health status information.
    """
    return {"status": "healthy", "service": "deer-flow-gateway"}
