import aircraftlib as aclib

# pull data, store to DB
# pull data periodically (hourly), append to DB
# sqlalchemy for ORM to sqlite local DB (build engine, session, and query objects)
# store raw vectors? or normallize in another way?
# pandas read to dataframe: df = pd.read_sql(query.statement, query.session.bind)

# ETL:
#   - progress to parameters:
#       - Fetch within an area (position, radius, disable)
#       - Enable/Disable update reference data

# analysis:
#   - how many AC from each airline are in the sky right now?
#   - Frequency management via clustering
#   - Plot current flights (just dots)
#   - Plot current routes (great circle distance)
#   - Correlate current flights with known routes
#   - Plot pariclar AC path over time (requires historical data)


def main():
    # Get the live AC vector data around Dulles airport
    dulles_airport_position = aclib.Position(lat=38.9519444444, long=-77.4480555556)
    area_surrounding_dulles = aclib.bounding_box(
        position=dulles_airport_position, radius_km=200
    )

    print("fetching reference data...")
    ref_data = aclib.fetch_reference_data()

    print("fetching live aircraft data...")
    raw_aircraft_data = aclib.fetch_live_aircraft_data(area=area_surrounding_dulles)

    print("cleaning & transform aircraft data...")
    live_aircraft_data = []
    for raw_vector in raw_aircraft_data:
        vector = aclib.clean_vector(raw_vector)
        if vector:
            aclib.add_airline_info(vector, ref_data.airlines)
            live_aircraft_data.append(vector)

    print("saving live aircraft data...")
    db = aclib.Database()
    db.add_live_aircraft_data(live_aircraft_data)

    print("saving reference data...")
    db.update_reference_data(ref_data)

    print("complete!")


if __name__ == "__main__":
    main()

# what is a vector
# goto logs ???
# small snippits of data

# DE portion:
# schedules
# cache & resulthandlers --> this is not useful without a good remote store
# parallelization (different executor)
# triggers


# DS portion:
# mapping
