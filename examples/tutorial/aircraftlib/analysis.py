import collections
from typing import List, Any, Dict

from .opensky import AIRCRAFT_VECTOR_FIELDS

FIELS_OF_INTEREST = (
    "icao",
    "callsign",
    "time_position",
    "last_contact",
    "longitude",
    "latitude",
    "baro_altitude",
    "on_ground",
    "velocity",
    "true_track",
    "vertical_rate",
    "geo_altitude",
)


def clean_vector(raw_vector: List[Any]):
    clean = dict(zip(AIRCRAFT_VECTOR_FIELDS, raw_vector[:]))

    if None in (clean["longitude"], clean["latitude"]):
        # this is an invalid vector, ignore it
        return None

    return {key: clean[key] for key in FIELS_OF_INTEREST}


def add_airline_info(vector: Dict[str, Any], airlines: Dict[str, str]) -> None:
    airline = None
    callsign = vector["callsign"]

    if callsign:
        if callsign[:3] in airlines.keys():
            airline = callsign[:3]
        elif callsign[:2] in airlines.keys():
            airline = callsign[:2]

    vector["airline"] = airline
