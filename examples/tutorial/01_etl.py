import aircraftlib as aclib


def main():
    # Get the live aircraft vector data around Dulles airport
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
