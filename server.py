import argparse
import logging
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from starlette.concurrency import run_in_threadpool
import psutil
import platform
import shutil
import os
import painel
from security import Authentication


@asynccontextmanager
async def lifespan(application):
    application.state.authentication = Authentication.load()
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


app = FastAPI(title="Extract-Raspberry", version="2.1.0", lifespan=lifespan)


def secured_openapi():
    if not app.openapi_schema:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema.setdefault('components', {})['securitySchemes'] = {
            'BasicAuth': {'type': 'http', 'scheme': 'basic'},
            'BearerAuth': {'type': 'http', 'scheme': 'bearer'}}
        schema['security'] = [{'BasicAuth': []}, {'BearerAuth': []}]
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = secured_openapi


@app.middleware("http")
async def response_headers(request, call_next):
    if request.url.scheme != 'https':
        response = JSONResponse(status_code=400, content={'error': 'Use HTTPS para acessar o monitor.'})
    else:
        status = await run_in_threadpool(request.app.state.authentication.authenticate,
            request.headers.get('authorization'), request.client.host if request.client else 'unknown')
        if status == 200:
            response = await call_next(request)
        else:
            response = JSONResponse(status_code=status,
                content={'error': 'Muitas tentativas. Aguarde 60 segundos.' if status == 429 else 'Autenticação necessária.'},
                headers={'Retry-After': '60'} if status == 429 else
                    {'WWW-Authenticate': 'Basic realm="Extract-Raspberry", charset="UTF-8"'})
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
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


def run(default_port=8443):
    import uvicorn
    parser = argparse.ArgumentParser(description="Extract-Raspberry: API, dashboard e histórico")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument('--ssl-certfile', default=str(painel.ROOT / 'certs/cert.pem'))
    parser.add_argument('--ssl-keyfile', default=str(painel.ROOT / 'certs/key.pem'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host=args.host, port=args.port, workers=1,
                ssl_certfile=args.ssl_certfile, ssl_keyfile=args.ssl_keyfile,
                proxy_headers=False, server_header=False)


if __name__ == "__main__":
    run()
