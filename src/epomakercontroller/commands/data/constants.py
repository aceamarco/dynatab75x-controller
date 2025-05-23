"""Constants for the EpomakerController commands module.

This module defines various constants used in the EpomakerController commands.
"""

from enum import Enum
from dataclasses import dataclass

# TODO: Add this to the config files
BUFF_LENGTH = 128 // 2  # 128 bytes / 2 bytes per int
IMAGE_DIMENSIONS = (9, 60)
MAX_NUM_PIXELS = 60 * 9
VENDOR_ID = 0x3151

PRODUCT_IDS_WIRED = [0x4010, 0x4015]
