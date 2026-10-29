import argparse
import logging
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
import psutil
import platform
import shutil
import os
import painel


@asynccontextmanager
async def lifespan(application):
    painel.init_db()
    with painel.LOCK:
        painel.LATEST = None
    stop = threading.Event()
    collector = threading.Thread(target=painel.collect, args=(stop,), daemon=True)
    collector.start()
    try:
        yield
    finally:
        stop.set()
        collector.join(timeout=5)


app = FastAPI(title="Extract-Raspberry", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(painel.ROOT / "index.html", media_type="text/html")


@app.get("/api")
def latest_sample():
    """Última leitura do coletor, sem disparar uma nova coleta."""
    with painel.LOCK:
        sample = painel.LATEST
    if sample is None:
        return JSONResponse(status_code=503, content={"error": "Aguardando primeira coleta"})
    return sample


@app.get("/api/history")
def historical_samples(period: Literal["1h", "24h", "7d", "30d"] = "1h"):
    """Médias do histórico no período solicitado."""
    try:
        return painel.history(period)
    except Exception:
        logging.exception("Erro ao consultar o histórico")
        return JSONResponse(status_code=500, content={"error": "Não foi possível ler o histórico"})

def get_disk_usage():
    total, used, free = shutil.disk_usage("/")
    return {"total": total, "used": used, "free": free}

def bytes_to_gb(value):
    return round(value / (1024**3), 2)  # Transforming data to GB


@app.get("/status")
def system_status():
    """Leitura sob demanda, preservando o contrato da API original."""
    temperatures = getattr(psutil, "sensors_temperatures", lambda: {})()
    cpu_temp = temperatures.get("cpu_thermal", [])
    cpu_temp_value = cpu_temp[0].current if cpu_temp else "N/A"

    memory = psutil.virtual_memory()
    disk = get_disk_usage()

    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory": {
            "total": bytes_to_gb(memory.total),
            "used": bytes_to_gb(memory.used),
            "free": bytes_to_gb(memory.available),
            "percent": memory.percent,
        },
        "disk": {
            "total": bytes_to_gb(disk["total"]),
            "used": bytes_to_gb(disk["used"]),
            "free": bytes_to_gb(disk["free"]),
        },
        "temperature": cpu_temp_value,
        "power": "Battery" if os.path.exists("/sys/class/power_supply/BAT0") else "Plugged In",
        "os": platform.system(),
        "os_version": platform.release(),
    }


def run(default_port=8000):
    import uvicorn
    parser = argparse.ArgumentParser(description="Extract-Raspberry: API, dashboard e histórico")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=default_port)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    run()
