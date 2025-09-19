from fastapi import FastAPI
from backend.routes import router as routes_router

app = FastAPI(title="Lucky Signals Backend")

# Register routes (prefix /api)
app.include_router(routes_router, prefix="/api", tags=["signals"])

@app.get("/")
def root():
    return {"message": "Backend is running successfully"}
