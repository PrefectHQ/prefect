from typing import List, Any, Dict, Tuple

from sqlalchemy import Column, DateTime, String, Integer, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .openflights import OpenFlightsData

Base = declarative_base()


class AircraftVector(Base):
    # PK: a physical AC at a specific time
    __tablename__ = "aircraft_vector"

    icao = Column(String, primary_key=True)
    callsign = Column(String)
    time_position = Column(Integer)
    last_contact = Column(Integer, primary_key=True)
    longitude = Column(Float)
    latitude = Column(Float)
    baro_altitude = Column(String)
    on_ground = Column(Boolean)
    velocity = Column(Float)
    true_track = Column(Float)
    vertical_rate = Column(Float)
    geo_altitude = Column(Float)
    airline = Column(String)


class Airline(Base):
    __tablename__ = "airline"
    id = Column(String, primary_key=True)
    name = Column(String)


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(String, primary_key=True)
    name = Column(String)


class Airport(Base):
    __tablename__ = "airport"
    id = Column(String, primary_key=True)
    name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)


class Route(Base):
    __tablename__ = "route"
    id = Column(Integer, primary_key=True, autoincrement=True)
    airline = Column(String)
    source = Column(String)
    destination = Column(String)
    codeshare = Column(String)
    stops = Column(Integer)
    equipment = Column(String)


class Database:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite:///aircraft-db.sqlite")
        session_maker = sessionmaker()
        session_maker.configure(bind=self.engine)
        Base.metadata.create_all(self.engine)
        self.session = session_maker()

    def add_live_aircraft_data(self, vectors: List[Dict[str, Any]]) -> None:
        for entry in vectors:
            vec = AircraftVector(
                **{k: entry[k] for k in AircraftVector.__table__.columns.keys()}
            )
            # insert or update vector
            self.session.merge(vec)
        self.session.commit()

    def update_airlines(self, airlines: Dict[str, str]) -> None:
        Base.metadata.tables[Airline.__tablename__].drop(bind=self.engine)
        Base.metadata.tables[Airline.__tablename__].create(bind=self.engine)

        objects = []
        for identity, name in airlines.items():
            objects.append(Airline(id=identity, name=name))
        self.session.bulk_save_objects(objects)
        self.session.commit()

    def update_equipment(self, equipment: Dict[str, str]) -> None:
        Base.metadata.tables[Equipment.__tablename__].drop(bind=self.engine)
        Base.metadata.tables[Equipment.__tablename__].create(bind=self.engine)

        objects = []
        for identity, name in equipment.items():
            objects.append(Equipment(id=identity, name=name))
        self.session.bulk_save_objects(objects)
        self.session.commit()

    def update_airports(self, airports: Dict[str, Dict[str, Any]]) -> None:
        Base.metadata.tables[Airport.__tablename__].drop(bind=self.engine)
        Base.metadata.tables[Airport.__tablename__].create(bind=self.engine)

        objects = []
        for identity, fields in airports.items():
            objects.append(
                Airport(
                    id=identity,
                    latitude=fields["latitude"],
                    longitude=fields["longitude"],
                    name=fields["airport-name"],
                )
            )
        self.session.bulk_save_objects(objects)
        self.session.commit()

    def update_routes(self, routes: List[Dict[str, Any]]) -> None:
        Base.metadata.tables[Route.__tablename__].drop(bind=self.engine)
        Base.metadata.tables[Route.__tablename__].create(bind=self.engine)

        objects = []
        for route in routes:
            route["source"] = route["from"]
            route["destination"] = route["to"]
            del route["from"]
            del route["to"]
            objects.append(Route(**route))
        self.session.bulk_save_objects(objects)
        self.session.commit()

    def update_reference_data(self, ref_data: OpenFlightsData) -> None:
        self.update_routes(ref_data.routes)
        self.update_airports(ref_data.airports)
        self.update_airlines(ref_data.airlines)
