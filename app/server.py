from fastapi import FastAPI
from sqlalchemy import text
from app.main.db.session import engine

app = FastAPI(title="JU Prototype", version="0.1.0")


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
