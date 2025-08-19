import traceback
import re
import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
import requests

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.responses import FileResponse, JSONResponse
import db_helper

from draw import plot_generation, PlotType

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level = logging.INFO)

POWER_GEN_TYPES = [
    "nuclear",
    "coal",
    "cogen",
    "ippcoal",
    "lng",
    "ipplng",
    "oil",
    "diesel",
    "hydro",
    "wind",
    "solar",
    "OtherRenewableEnergy",
    "EnergyStorageSystem",
    "EnergyStorageSystemLoad",
]

TRMNL_POWER_GEN_TYPES = [
    "nuclear",
    "coal",
    "cogen",
    "ippcoal",
    "lng",
    "ipplng",
    "oil",
    "diesel",
    "hydro",
    "wind",
    "solar",
    "OtherRenewableEnergy",
    "EnergyStorageSystem",
]

def send_to_trmnl():

    try:
        TRMNL_API_KEY = os.environ['TRMNL_PLUGIN_API_KEY']
    except KeyError:
        logger.error("[send_to_trmnl] TRMNL_PLUGIN_API_KEY not set in environment variables.")
        return

    TRNML_HISTORY_PATH = os.path.join("data", "trmnl.json")
    trnml_stat = {}
    payload = {}
    plot_info = {}

    latest_data = db_helper.get_latest_summary_record()
    sum = 0
    for data in latest_data:
        sum += data['generation']

    plot_info = {
        "total_generation": int(sum),
        "timestamp": latest_data[0]['timestamp'],
    }

    curr = latest_data[0]["timestamp"]

    payload['merge_variables'] = plot_info

    # print(len(json.dumps(payload)))
    # print(payload)

    try:
        with open(TRNML_HISTORY_PATH, 'r') as file:
            trnml_stat = json.load(file)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        logger.error(f"[send_to_trmnl] invalid JSON file '{TRNML_HISTORY_PATH}'")
    except Exception as e:
        logger.error(f"[send_to_trmnl] {traceback.format_exc()}")

    if "last_datatime" in trnml_stat:
        if trnml_stat["last_datatime"] == curr:
            logger.info("[send_to_trmnl] PASS")
            return

    # print(json.dumps(payload))
    # print("json size: %d" % len(json.dumps(payload)))

    url = "https://usetrmnl.com/api/custom_plugins/" + TRMNL_API_KEY
    response = requests.post(url, json=payload)
    logger.info(response)
    if response.status_code == 200:
        with open(TRNML_HISTORY_PATH, "w") as fp:
            json.dump({
                "last_datatime": curr,
            }, fp, indent=2)
    else:
        logger.error(response.text)

def get_power_generation():
    # Basic GET request
    response = requests.get('https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genary.json')
    data = None
    pattern = r"<A NAME='(?P<type>.*)'"

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        logger.info("taipower request successful!")
        data = response.json()
    else:
        logger.warning(f"taipower request failed with status code: {response.status_code}")

    if data is None:
        return False

    try:
        datetime_obj  = datetime.strptime(data[""], "%Y-%m-%d %H:%M")
        timestamp_str = datetime_obj.isoformat()
    except Exception as e:
        logger.warning(f"Invalid datetime: {data['']}")
        return False


    # ["<A NAME='coal'></A><b>燃煤(Coal)</b>", '', '台中#1', '550.0', '504.1', '91.655%', '環保限制', '']
    # ["<A NAME='coal'></A><b>燃煤(Coal)</b>", '', '小計', '10600.0(18.371%)', '8341.8(25.632%)', '', '', '']
    # Two definiation of this data:
    # if row[2] == "小計":
    #   row[0] => HTML element
    #   row[1] => ???
    #   row[2] => Literal "小計"
    #   row[3] => Installed capacity (in MW) and its percentage share of the total power grid.
    #             Format: "<capacity>(<percentage>%)"
    #   row[4] => Current net power generation (in MW) and its percentage share of total grid capacity.
    #             Format: "<net_power_generation_MW>(<percentage_of_grid_capacity>%)"
    #   row[5] => ???
    #   row[6] => ???
    #   row[7] => ???
    # else:
    #   row[0] => HTML element
    #   row[1] => ???
    #   row[2] => Power plant name
    #   row[3] => Installed capacity (in MW)
    #   row[4] => Current net power generation (in MW)
    #   row[5] => Current capacity factor of power plant
    #   row[6] => Notes
    #   row[7] => ???
    for row in data['aaData']:
        is_sum = False
        capacity = None
        capacity_percentage = None
        generation = None
        generation_percentage = None
        if '小計' in row[2]:
            is_sum = True
        match = re.search(pattern, row[0])
        if not match:
            print(f"re.search fail to match `{row[0]}` with pattern `{pattern}`. Skip this row...")
            continue
        power_gen_type = match.group("type")
        if power_gen_type not in POWER_GEN_TYPES:
            print(f"New power_gen_type `{power_gen_type}`. Skip this row...")
            continue

        if is_sum:
            sum_pattern = r"(?P<value>.*)\((?P<percentage>.*)\%\)"

            match = re.search(sum_pattern, row[3])
            if not match:
                print(f"is_sum: re.search fail to match `{row[3]}` with pattern `{sum_pattern}`. Skip this row...")
                continue
            capacity_str = match.group("value")
            capacity_percentage_str = match.group("percentage")

            match = re.search(sum_pattern, row[4])
            if not match:
                print(f"is_sum: re.search fail to match `{row[4]}` with pattern `{sum_pattern}`. Skip this row...")
                continue
            generation_str = match.group("value")
            generation_percentage_str = match.group("percentage")

            try:
                capacity = float(capacity_str)
                capacity_percentage = float(capacity_percentage_str)
                generation = float(generation_str)
                generation_percentage = float(generation_percentage_str)
            except Exception as e:
                print(traceback.format_exc())
                continue
        else:
            try:
                capacity = float(row[3])
            except Exception as e:
                pass
            try:
                generation = float(row[4])
            except Exception as e:
                pass
            try:
                generation_percentage = float(row[5][:-1])
            except Exception as e:
                pass

        record = db_helper.PowerGenerationRecord(
            name = row[2],
            type = power_gen_type,
            timestamp = timestamp_str,
            is_sum = is_sum,
            capacity = capacity,
            capacity_percentage = capacity_percentage,
            generation = generation,
            generation_percentage = generation_percentage,
        )

        db_helper.insert_record(record)

async def updater():
    while True:
        try:
            get_power_generation()
            send_to_trmnl()
        except Exception as e:
            logger.error(f"[updater] {traceback.format_exc()}")
        await asyncio.sleep(150)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Startup: Create database pool
    db_helper.init_db()
    app.state.conn = db_helper.get_db_connection()
    print("Database pool created")

    task = asyncio.create_task(updater())

    yield  # Application runs here

    task.cancel()

def get_summary():
    today = datetime.now().date()
    yesterday = today - timedelta(days=2)
    tomorrow = today + timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    data = db_helper.get_sum_records_by_time_range(yesterday_str, tomorrow_str)
    curr = data[0]["timestamp"]
    grand_arr = {}
    arr = []
    grand_arr.setdefault(curr, {})
    for d in data:
        if curr != d["timestamp"]:
            grand_arr.setdefault(d["timestamp"], {})
            curr = d["timestamp"]
        grand_arr[d["timestamp"]].setdefault(d["type"], d["generation"])
    return grand_arr

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def strip_path_prefix(request: Request, call_next):
    prefix = "/power"
    prefix_len = len(prefix)
    if request.url.path.startswith(prefix):
        request.scope["path"] = request.scope["path"][prefix_len:]

    response = await call_next(request)
    return response

# Disable detailed validation errors in production
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request parameters"},  # Generic error
    )

app.mount("/img", StaticFiles(directory="www/img"))
app.mount("/lib", StaticFiles(directory="www/lib"))

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("www/favicon.png", media_type="image/x-icon")


@app.get("/")
@app.get("/index.html")
async def static_file(request: Request):
    path = request.url.path
    if path == '/':
        path = '/index.html'

    return FileResponse(f'www{path}')


@app.get("/api/plot.svg")
async def power_plant_plot(width: int = 780, height: int = 460, plot_type: PlotType = PlotType.SHOW_ALL):
    grand_arr = get_summary()
    return FileResponse(plot_generation(grand_arr, plot_type, width, height))

@app.get("/api/plot_info")
async def power_plant_plot_info():
    latest_data = db_helper.get_latest_summary_record()
    sum = 0
    for data in latest_data:
        sum += data['generation']
    return JSONResponse({
        "total_generation": int(sum),
        "timestamp": latest_data[0]['timestamp'],
    })


@app.get("/api/summary")
@app.get("/api/summary.json")
async def power_plant_summary():
    grand_arr = get_summary()
    return JSONResponse(grand_arr)

if __name__ == '__main__':
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    import uvicorn
    uvicorn.run("main:app",
                port=80,
                host='0.0.0.0',
                reload=True,
                log_level='debug',
                workers=1)
