"""Reading Engine v5.2.

The engine and validation are intentionally identical to v5.1. The only
experimental change lives in ai_reader_v52: the editor output limit is 4096.
"""

from reading_engine_v51 import generate_personal_reading_v51


generate_personal_reading_v52 = generate_personal_reading_v51
