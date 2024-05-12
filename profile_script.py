import cProfile
import pstats
import signal
import sys
import penrose_generator

def save_profile(profiler):
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.dump_stats("penrose_generator_profile.prof")
    print("Profile data has been saved to 'penrose_generator_profile.prof'.")
    sys.exit(0)

def setup_signal_handlers(profiler):
    def signal_handler(signum, frame):
        save_profile(profiler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def main():
    penrose_generator.main()

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    setup_signal_handlers(profiler)
    main()

