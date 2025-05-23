# src/epomakercontroller/cli.py
"""Simple CLI for the EpomakerController package."""

import click
import tkinter as tk
import logging

from .epomakercontroller import EpomakerController


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s"
)


@click.group()
def cli() -> None:
    """A simple CLI for the EpomakerController."""
    pass


@cli.command()
@click.argument("image_path", type=click.Path(exists=True))
def upload_image(image_path: str) -> None:
    """Upload an image to the Epomaker device.

    Args:
        image_path (str): The path to the image file to upload.
    """
    logging.debug(f"Starting upload_image command with image_path: {image_path}")
    controller = None
    try:
        controller = EpomakerController()
        logging.debug("EpomakerController initialized.")

        if controller.open_device():
            logging.debug("Device opened successfully.")
            print(
                "Uploading, you should see the status on the keyboard screen.\n"
                "The keyboard will be unresponsive during this process."
            )
            logging.debug(f"Sending image: {image_path}")
            controller.send_image(image_path)
            logging.info("Image uploaded successfully.")
            click.echo("Image uploaded successfully.")
        else:
            logging.warning("Failed to open device.")
            click.echo("Failed to open device.")
    except Exception as e:
        logging.exception("Exception occurred during image upload.")
        click.echo(f"Failed to upload image: {e}")
    finally:
        if controller:
            logging.debug("Closing device.")
            controller.close_device()
            logging.debug("Device closed.")


@cli.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Start daemon in test mode, sending random data.",
)
@click.argument("temp_key", type=str, required=False)
def start_daemon(temp_key: str | None, test_mode: bool) -> None:
    """Start a daemon to update the CPU usage and optionally a temperature.

    Args:
        temp_key (str): A label corresponding to the device to monitor.
        test_mode (bool): Send random ints instead of real values.
    """
    try:
        controller = EpomakerController()
        if not controller.open_device():
            click.echo("Failed to open device.")
            return
        controller.start_daemon(temp_key, test_mode)

    except KeyboardInterrupt:
        click.echo("Daemon interrupted by user.")
    except Exception as e:
        click.echo(f"Error in start-daemon: {e}")
    controller.close_device()


@cli.command()
@click.option(
    "--print",
    "print_info",
    is_flag=True,
    help="Print all available information about the connected keyboard.",
)
@click.option(
    "--udev",
    "generate_udev",
    is_flag=True,
    help="Generate a udev rule for the connected keyboard.",
)
def dev(print_info: bool, generate_udev: bool) -> None:
    """Various dev tools.

    Args:
        print_info (bool): Print information about the connected keyboard.
        generate_udev (bool): Generate a udev rule for the connected keyboard.
    """
    if print_info:
        click.echo("Printing all available information about the connected keyboard.")
        controller = EpomakerController()
        if not controller.open_device(only_info=True):
            click.echo("Failed to open device.")
            return
    elif generate_udev:
        click.echo("Generating udev rule for the connected keyboard.")
        # Init controller to get the PID
        controller = EpomakerController()
        if not controller.open_device(only_info=True):
            click.echo("Failed to open device.")
            return
        controller.generate_udev_rule()
    else:
        click.echo("No dev tool specified.")


if __name__ == "__main__":
    cli()
