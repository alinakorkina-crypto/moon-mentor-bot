import unittest

from reading_engine_v51 import generate_personal_reading_v51
from reading_engine_v52 import generate_personal_reading_v52


class ReadingEngineV52Tests(unittest.TestCase):
    def test_engine_logic_is_unchanged_from_v51(self):
        self.assertIs(generate_personal_reading_v52, generate_personal_reading_v51)


if __name__ == "__main__":
    unittest.main()
