"""EpomakerController module.

This module contains the EpomakerController class, which represents a controller
for an Epomaker USB HID device.
"""

import dataclasses
from json import dumps
import os
import time
from typing import Any, Union, Optional
import hid  # type: ignore[import-not-found]
import signal
import subprocess
from types import FrameType
import re
from PIL import Image, UnidentifiedImageError, ImageSequence
import logging
from pathlib import Path
from .commands.data.constants import (
    BUFF_LENGTH,
    VENDOR_ID,
    PRODUCT_IDS_WIRED,
    MAX_NUM_PIXELS,
    IMAGE_DIMENSIONS,
)

CONST_HEADER = bytes([0x29, 0x00, 0x01, 0x00])
BASE_ADDRESS = 0x0000389D
HEADER_SIZE = 4 + 2 + 2  # constant + incrementing nibble + decrementing nibble
MAX_PACKET_SIZE = 64
PAYLOAD_SIZE = MAX_PACKET_SIZE - HEADER_SIZE  # 56 bytes for pixel data
FIRST_PACKET = bytes.fromhex(
    "a9000100540600fb00003c0900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
)

# TODO: confirm is the second 4 bytes means anything
FIRST_ANIMATION_PACKET = bytes.fromhex(
    "a9000932540600c100003c0900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
)

logger = logging.getLogger(__name__)


class EpomakerController:
    """EpomakerController class represents a controller for an Epomaker USB HID device.

    Attributes:
        vendor_id (int): The vendor ID of the USB HID device.
        product_id (int): The product ID of the USB HID device.
        device (hid.device): The HID device object.
        dry_run (bool): Whether to run in dry run mode.

    Methods:
        open_device: Opens the USB HID device and prints device information.
        send_basic_command: Sends a command to the HID device.
        close_device: Closes the USB HID device.
        format_current_time: Gets the current time and formats it into the required
            byte string format.
    """

    def __init__(self, dry_run=False) -> None:
        """Initializes the EpomakerController object.

        Args:
            vendor_id (int): The vendor ID of the USB HID device.
            dry_run (bool): Whether to run in dry run mode (default: False).
        """
        self.dry_run = dry_run
        self.vendor_id = VENDOR_ID
        self.use_wireless = False
        self.product_ids: list[int] = PRODUCT_IDS_WIRED
        self.device_description = ""
        self.device = hid.device()
        self.device_list: list[dict[str, Any]] = []
        print(
            """WARNING: If this program errors out or you cancel early, the keyboard
              may become unresponsive. It should work fine again if you unplug and plug
               it back in!"""
        )

        # Set up signal handling
        self._setup_signal_handling()

    def _setup_signal_handling(self) -> None:
        """Sets up signal handling to close the HID device on termination."""
        signal.signal(signal.SIGINT, self._signal_handler)  # Handle Ctrl+C
        signal.signal(signal.SIGTERM, self._signal_handler)  # Handle termination

    def _signal_handler(self, sig: int, frame: Optional[FrameType]) -> None:
        """Handles signals to ensure the HID device is closed."""
        self.close_device()
        os._exit(0)  # Exit immediately after closing the device

    def __del__(self) -> None:
        """Destructor to ensure the device is closed."""
        self.close_device()

    def open_device(self, only_info: bool = False) -> bool:
        """Opens the USB HID device and prints device information.

        Args:
            only_info (bool): Print device information and exit (default: False).

        Raises:
            ValueError: If no device is found with the specified interface number.

        Returns:
            bool: True if the device is opened successfully, False otherwise.
        """

        product_id = self._find_product_id()
        if not product_id:
            raise ValueError("No Epomaker devices found")

        if only_info:
            self._print_device_info()
            return True

        # Find the device with the specified interface number so we can open by path
        # This way we don't block usage of the keyboard whilst the device is open
        device_path = self._find_device_path()
        if device_path is None:
            raise ValueError("No device found")
        self._open_device(device_path)

        return self.device is not None

    def _find_product_id(self) -> int | None:
        """Finds the product ID of the device using a list of possible product IDs.

        Returns:
            int | None: The product ID if found, None otherwise.
        """
        for pid in self.product_ids:
            self.device_list = hid.enumerate(self.vendor_id, pid)
            if self.device_list:
                return pid
        return None

    def _open_device(self, device_path: bytes) -> None:
        """Opens the USB HID device.

        Args:
            device_path (bytes): The path to the device.
        """
        try:
            self.device = hid.device()
            self.device.open_path(device_path)
        except IOError as e:
            print(
                f"Failed to open device: {e}\n"
                "Please make sure the device is connected\n"
                "and you have the necessary permissions.\n\n"
                "You may need to run this program as root or with sudo, or\n"
                "set up a udev rule to allow access to the device.\n\n"
            )
            self.device = None

        assert self.device is not None

    def generate_udev_rule(self) -> None:
        """Generates a udev rule for the connected keyboard."""
        rule_content = (
            f"# Epomaker RT100 keyboard\n"
            f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{self.vendor_id:04x}", '
            f'ATTRS{{idProduct}}=="{self._find_product_id():04x}", MODE="0666", '
            'GROUP="plugdev"\n\n'
        )

        rule_file_path = "/etc/udev/rules.d/99-epomaker-rt100.rules"

        print("Generating udev rule for Epomaker RT100 keyboard")
        print(f"Rule content:\n{rule_content}")
        print(f"Rule file path: {rule_file_path}")
        print("Please enter your password if prompted")

        # Write the rule to a temporary file
        temp_file_path = "/tmp/99-epomaker-rt100.rules"
        with open(temp_file_path, "w", encoding="utf-8") as temp_file:
            temp_file.write(rule_content)

        # Move the file to the correct location, reload rules

        move_command = ["mv", temp_file_path, rule_file_path]
        reload_command = ["udevadm", "control", "--reload-rules"]
        trigger_command = ["udevadm", "trigger"]

        if os.geteuid() != 0:
            # Use sudo if not root
            move_command = ["sudo"] + move_command
            reload_command = ["sudo"] + reload_command
            trigger_command = ["sudo"] + trigger_command

        subprocess.run(move_command, check=True)
        subprocess.run(reload_command, check=True)
        subprocess.run(trigger_command, check=True)

        print("Rule generated successfully")

    def _print_device_info(self) -> None:
        """Prints device information."""
        devices = self.device_list.copy()
        for device in devices:
            device["path"] = device["path"].decode("utf-8")
            device["vendor_id"] = f"0x{device['vendor_id']:04x}"
            device["product_id"] = f"0x{device['product_id']:04x}"
        print(
            dumps(
                devices,
                indent="  ",
            )
        )

    @dataclasses.dataclass
    class HIDInfo:
        device_name: str
        event_path: str
        hid_path: Optional[str] = None

    def _find_device_path(self) -> Optional[bytes]:
        """Finds the device path with the specified interface number.

        Returns:
            Optional[bytes]: The device path if found, None otherwise.
        """
        for device in self.device_list:
            if (
                device["usage_page"] == 65535 and device["usage"] == 2
            ):  # Likely LED device
                return device["path"]

        return None

    @staticmethod
    def _get_hid_infos(input_dir: str, description: str) -> list[HIDInfo]:
        """Retrieve HID information based on the given description."""
        hid_infos = []
        for event in os.listdir(input_dir):
            if event.startswith("event"):
                device_name_path = os.path.join(input_dir, event, "device", "name")
                try:
                    with open(device_name_path, "r", encoding="utf-8") as f:
                        device_name = f.read().strip()
                        if re.search(description, device_name):
                            event_path = os.path.join(input_dir, event)
                            hid_infos.append(
                                EpomakerController.HIDInfo(device_name, event_path)
                            )
                except FileNotFoundError:
                    continue
        return hid_infos

    @staticmethod
    def _populate_hid_paths(hid_infos: list[HIDInfo]) -> None:
        """Populate the HID paths for each HIDInfo object in the list."""
        for hi in hid_infos:
            device_symlink = os.path.join(hi.event_path, "device")
            if not os.path.islink(device_symlink):
                print(f"No 'device' symlink found in {hi.event_path}")
                continue

            hid_device_path = os.path.realpath(device_symlink)
            match = re.search(r"\b\d+-[\d.]+:\d+\.\d+\b", hid_device_path)
            hi.hid_path = match.group(0) if match else None

    def _select_device_path(self, hid_infos: list[HIDInfo]) -> Optional[bytes]:
        """Select the appropriate device path based on interface preference."""
        device_name_filter = "Wireless" if self.use_wireless else "Wired"
        filtered_devices = [h for h in hid_infos if device_name_filter in h.device_name]

        if not filtered_devices:
            print(f"Could not find {device_name_filter} interface")
            return None

        selected_device = filtered_devices[0]
        return (
            selected_device.hid_path.encode("utf-8")
            if selected_device.hid_path
            else None
        )

    @staticmethod
    def _assert_range(value: int, r: range | None = None) -> bool:
        """Asserts that a value is within a specified range.

        Args:
            value (int): The value to check.
            r (range): The range to check against (default: None).

        Returns:
            bool: True if the value is within the range, False otherwise.
        """
        if not r:
            r = range(0, 100)  # 0 to 99
        return value in r

    def _rgb_to_hex(self, rgb: tuple) -> bytes:
        """Converts an RGB tuple to a bytes object representing a hexadecimal color."""
        hex_str = "{:02x}{:02x}{:02x}".format(*rgb)
        return bytes.fromhex(hex_str)

    def _encode_image(
        self, image_input: Union[str, Path, Image.Image], debug: bool = False
    ) -> bytearray:
        """
        Encodes an image to a bytearray suitable for the Epomaker device.

        Args:
            image_input (Union[str, Path, Image.Image]): Path to the image file or a PIL image object.
            debug (bool): If True, return a dummy image with fixed pixel data.

        Returns:
            bytearray: Encoded image data.
        """
        if debug:
            logging.debug("Debug mode active. Returning dummy image data.")
            return bytearray.fromhex("7e7321" * MAX_NUM_PIXELS)

        if isinstance(image_input, (str, Path)):
            logging.debug(f"Opening image from path: {image_input}")
            image = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            logging.debug("Using provided PIL.Image object.")
            image = image_input
        else:
            raise TypeError("image_input must be a file path or PIL.Image.Image")

        logging.debug(f"Original image mode: {image.mode}, size: {image.size}")
        image = image.convert("RGB")

        if (image.height, image.width) != IMAGE_DIMENSIONS:
            # todo fix this so you dont have to reverse the tuple
            logging.debug(
                f"Resizing image from {image.size} to {IMAGE_DIMENSIONS[::-1]}"
            )
            image = image.resize(IMAGE_DIMENSIONS[::-1])

        pixel_data = bytearray()
        rows, cols = IMAGE_DIMENSIONS

        logging.debug(f"Encoding image pixels in column-major order ({cols}x{rows})")
        for col in range(cols):
            for row in range(rows):
                rgb = image.getpixel((col, row))
                pixel_data.extend(self._rgb_to_hex(rgb))

        logging.debug(f"Encoded {len(pixel_data)} bytes of pixel data")
        return pixel_data

    def _chunk_data(
        self,
        data: list[bytearray] | bytearray,
        base_address: int,
        final_packet_overrides: list[tuple[int, int]] = None,
        per_frame_override: bool = False,
        is_animation: bool = False,
    ) -> list[bytearray]:
        if isinstance(data, bytearray):
            data = [data]

        packets = []

        for frame_index, frame_data in enumerate(data):
            incrementing_nibble = 0
            decrementing_nibble = base_address

            logger.debug(
                f"Processing frame {frame_index}, data length: {len(frame_data)}"
            )

            for offset in range(0, len(frame_data), PAYLOAD_SIZE):
                chunk = frame_data[offset : offset + PAYLOAD_SIZE]
                packet = bytearray(MAX_PACKET_SIZE)

                # Header: byte 0 is fixed, byte 1 is frame counter, bytes 2-3 depend on image vs animation
                packet[0] = 0x29
                packet[1] = frame_index
                # todo: check that animation does not have more than 255 frames
                packet[2] = len(data) if is_animation else 0x01
                packet[3] = 0x32 if is_animation else 0x00

                # Incrementing nibble (2 bytes)
                packet[4:6] = incrementing_nibble.to_bytes(2, byteorder="little")

                # Decrementing nibble (2 bytes)
                packet[6:8] = decrementing_nibble.to_bytes(2, byteorder="big")

                # Pixel payload
                packet[8 : 8 + len(chunk)] = chunk

                # Pad if payload is smaller than max
                data_size = 8 + len(chunk)
                if data_size < MAX_PACKET_SIZE:
                    packet[data_size + 1 :] = b"\x00" * (
                        MAX_PACKET_SIZE - data_size - 1
                    )

                logger.debug(
                    f"Packet #{len(packets)} | Frame: {frame_index} | Offset: {offset} "
                    f"| Inc: {incrementing_nibble:04x} | Dec: {decrementing_nibble:04x} | Chunk size: {len(chunk)}"
                )

                incrementing_nibble += 1
                decrementing_nibble -= 1

                packets.append(packet)

            # Override last packet decrementing nibble if needed
            if per_frame_override and final_packet_overrides:
                override_value = final_packet_overrides[frame_index]
                packets[-1][6:8] = bytearray(override_value)
                logger.debug(
                    f"Applied final packet override to frame {frame_index}: "
                    f"{override_value[0]:02x} {override_value[1]:02x}"
                )

        logger.info(f"Total packets generated: {len(packets)}")
        return packets

    def _chunk_image_data(self, image_data: bytearray) -> list[bytearray]:
        return self._chunk_data(
            data=image_data,
            base_address=BASE_ADDRESS,
            final_packet_overrides=[(0x34, 0x85)],
            per_frame_override=True,
            is_animation=False,
        )

    def _chunk_animation_data(self, animation_data: list[bytearray]) -> list[bytearray]:
        overrides = [(0x34, 0x49 - i) for i in range(len(animation_data))]
        return self._chunk_data(
            data=animation_data,
            base_address=0x00003861,
            final_packet_overrides=overrides,
            per_frame_override=True,
            is_animation=True,
        )

    def _set_packet(self, packet):
        if self.dry_run:
            print(f"Dry run: skipping command send: {packet!r}")
        else:
            self.device.send_feature_report(bytes.fromhex("00") + packet)
            time.sleep(0.005)

    def _get_packet(self, id=0x00):
        if self.dry_run:
            print(f"Dry run: skipping get_feature_report({id}, 64)")
        else:
            self.device.get_feature_report(0, MAX_PACKET_SIZE + 1)
            time.sleep(0.005)

    # TODO: Make a script that imports this module and sends text to the LED display
    def send_image(self, image_path: str) -> None:
        image_raw_data = self._encode_image(image_path, debug=False)

        assert self.device, "Device is not set!"
        try:
            self.device.get_product_string()
        except:
            raise IOError("Could not communicate with device")

        commands = self._chunk_image_data(image_raw_data)

        self._set_packet(FIRST_PACKET)

        self._get_packet()

        for packet in commands:
            if self.dry_run:
                print(f"Dry run: skipping command send: {packet!r}")
            else:
                self._set_packet(packet)

    def send_animation(self, file_path: str = None, debug: bool = False):
        if not self.device:
            raise ValueError("Device is not set!")

        try:
            self.device.get_product_string()
        except Exception as e:
            raise IOError("Could not communicate with device") from e

        if debug or not file_path:
            # Load default test animation (TODO: replace with actual default path)
            file_path = "assets/debug_animation.gif"
            logger.info(f"Debug mode active. Using debug animation: {file_path}")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Animation file not found: {file_path}")

        try:
            with Image.open(file_path) as img:
                logger.info(f"Opened animation: {file_path}")
                frames = []
                for i, frame in enumerate(ImageSequence.Iterator(img)):
                    logger.debug(
                        f"Processing frame {i} - mode: {frame.mode}, size: {frame.size}"
                    )
                    # Convert to RGB to ensure consistency
                    converted = frame.convert("RGB")
                    frames.append(self._encode_image(converted))
        except UnidentifiedImageError:
            raise ValueError(f"Unsupported image format: {file_path}")
        except Exception as e:
            logger.error(f"Failed to process animation: {e}")
            raise

        if not frames:
            raise ValueError("No frames extracted from animation")

        packets = self._chunk_animation_data(frames)

        logger.info(f"Sending {len(packets)} animation packets")
        first_packet = FIRST_PACKET
        # todo: fix TypeError: 'bytes' object does not support item assignment
        first_packet[2] = len(frames)
        # todo: check that gif has at least two frames
        first_packet[7] = 0xC8 - (len(frames) - 2)
        self._set_packet(first_packet)
        self._get_packet()

        for i, packet in enumerate(packets):
            if self.dry_run:
                logger.debug(f"Dry run: Skipping packet #{i}")
            else:
                logger.debug(f"Sending packet #{i}")
                self._set_packet(packet)

    def close_device(self) -> None:
        """Closes the USB HID device."""
        if self.device:
            self.device.close()
            self.device = None
