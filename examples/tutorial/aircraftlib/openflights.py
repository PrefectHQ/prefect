import pathlib
import collections
import csv
from typing import Dict, List, Any


def _capture_path(source: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent.absolute() / "data" / "openflights" / source


def fetch_routes() -> List[Dict[str, Any]]:
    capture_path = _capture_path("routes.dat")
    result = []
    with open(capture_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        row = None
        for row in reader:
            result.append(dict(row))
    return result


def fetch_airlines() -> Dict[str, str]:
    capture_path = _capture_path("airlines.dat")
    result = {}  # { airline IATA/ICAO code: airline name }
    with open(capture_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            result[row["airline-id"]] = row["airline-name"]
    return result


def fetch_equipment() -> Dict[str, str]:
    capture_path = _capture_path("equipment.dat")
    result = {}  # { equipment code: equipment name }
    with open(capture_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            result[row["equipment-id"]] = row["equipment-name"]
    return result


def fetch_airports() -> Dict[str, Dict[str, Any]]:
    capture_path = _capture_path("airports.dat")
    result = {}  # { airport code: { field: value } }
    with open(capture_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            airport_id = row["airport-id"]
            del row["airport-id"]
            result[airport_id] = dict(row)

    return result


OpenFlightsData = collections.namedtuple("OpenFlightsData", "routes airlines airports")


def fetch_reference_data() -> OpenFlightsData:
    return OpenFlightsData(
        routes=fetch_routes(), airlines=fetch_airlines(), airports=fetch_airports()
    )
