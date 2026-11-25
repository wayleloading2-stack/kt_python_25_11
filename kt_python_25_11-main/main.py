import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="Currency Monitor")
EXPORT_DIR = Path(__file__).resolve().parent / "exports"


@app.on_event("startup")
async def create_export_folder():
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


async def get_currency_rates(include_rub=False):
    if include_rub:
        url = "https://api.frankfurter.dev/v2/rates?base=EUR&quotes=USD,GBP,RUB"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                "base": "EUR",
                "rates": {item["quote"]: item["rate"] for item in data},
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

    url = (
        "https://api.frankfurter.dev/v1/latest"
        "?base=EUR&symbols=USD,GBP,CHF,JPY,CAD"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        return {
            "base": data["base"],
            "rates": data["rates"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

@app.get("/events")
async def currency_events(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                rates = await get_currency_rates()

                yield {
                    "event": "currency_update",
                    "data": json.dumps(rates)
                }

            except Exception as error:
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": str(error)
                    })
                }

            await asyncio.sleep(10)
    return EventSourceResponse(event_generator())


def csv_row(values):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(values)
    return buffer.getvalue()


def open_export_file():
    try:
        return (EXPORT_DIR / "rates.csv").open("x", encoding="utf-8", newline="")
    except FileExistsError:
        return (EXPORT_DIR / f"rates_{uuid4().hex}.csv").open(
            "x", encoding="utf-8", newline=""
        )


@app.get("/export")
async def export_rates(request: Request, interval: int = Query(10, ge=1, le=60)):
    async def csv_generator():
        with open_export_file() as file:
            header = csv_row(["timestamp", "base", "USD", "GBP", "RUB"])
            file.write(header)
            file.flush()
            yield header

            while not await request.is_disconnected():
                try:
                    data = await get_currency_rates(include_rub=True)
                    rates = data["rates"]
                    row = csv_row([
                        data["updated_at"], data["base"],
                        rates.get("USD", ""), rates.get("GBP", ""),
                        rates.get("RUB", "")
                    ])
                except Exception:
                    row = csv_row([
                        datetime.now(timezone.utc).isoformat(), "EUR", "", "", ""
                    ])

                if await request.is_disconnected():
                    break

                file.write(row)
                file.flush()
                yield row
                await asyncio.sleep(interval)

    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rates.csv"'}
    )
