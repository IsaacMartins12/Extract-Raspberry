from fastapi import FastAPI
import psutil
import platform
import shutil
import os

app = FastAPI()

def get_disk_usage():
    total, used, free = shutil.disk_usage("/")
    return {"total": total, "used": used, "free": free}

def bytes_to_gb(value):
    return round(value / (1024**3), 2)  # Transforming data to GB


@app.get("/status")
def system_status():
    temperatures = psutil.sensors_temperatures()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
