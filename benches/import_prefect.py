import cProfile
import pstats


def profile_import():
    # Profile the import
    profiler = cProfile.Profile()
    profiler.enable()
    import prefect  # noqa: F401

    profiler.disable()

    # Output the top 10 functions by cumulative time
    stats = pstats.Stats(profiler)
    stats.strip_dirs().sort_stats("cumtime").print_stats(10)


if __name__ == "__main__":
    profile_import()
