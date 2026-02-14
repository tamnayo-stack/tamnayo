from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="Delivery Review Automation")
app.include_router(router, prefix="/api")
