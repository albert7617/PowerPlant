import traceback
import re
import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import logging
import requests
from pprint import pprint


from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import FileResponse, PlainTextResponse, JSONResponse
import db_helper

try:
    from data import env
    TRMNL_PLUGIN_ID = env.TRMNL_PLUGIN_ID
except:
    TRMNL_PLUGIN_ID = None

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

def send_to_trmnl():

    payload = {}
    # TODO: Populate "merge_variables"
    payload['merge_variables'] = ""
    payload['merge_strategy'] = "stream"
    payload['stream_limit'] = 512


    # print(json.dumps(payload))
    # print("json size: %d" % len(json.dumps(payload)))

    if TRMNL_PLUGIN_ID is None:
        return
    url = "https://usetrmnl.com/api/custom_plugins/" + TRMNL_PLUGIN_ID
    response = requests.post(url, json=payload)
    logger.warning(response)
    logger.warning(response.text)
    if response.status_code == 200:
        with open(os.path.join("data", "trmnl.json"), "w") as fp:
            json.dump({
                "last_update": datetime.now().isoformat(),
                "last_datatime": "",
            }, fp, indent=2)


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
        get_power_generation()
        send_to_trmnl()
        await asyncio.sleep(180)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Startup: Create database pool
    db_helper.init_db()
    app.state.conn = db_helper.get_db_connection()
    print("Database pool created")

    task = asyncio.create_task(updater())

    yield  # Application runs here

    task.cancel()

app = FastAPI(lifespan=lifespan)

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


@app.get("/api/summary")
@app.get("/api/summary.json")
async def power_plant_summary():
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
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
