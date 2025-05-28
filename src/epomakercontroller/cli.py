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


def _upload_file(file_path: str, is_animation: bool) -> None:
    """Helper function to upload an image or animation to the Epomaker device."""
    controller = None
    upload_type = "animation" if is_animation else "image"
    logging.debug(f"Starting upload for {upload_type}: {file_path}")

    try:
        controller = EpomakerController()
        logging.debug("EpomakerController initialized.")

        if controller.open_device():
            logging.debug("Device opened successfully.")
            print(
                f"Uploading {upload_type}, you should see the status on the keyboard screen.\n"
                "The keyboard will be unresponsive during this process."
            )
            if is_animation:
                controller.send_animation(file_path)
            else:
                controller.send_image(file_path)

            logging.info(f"{upload_type.capitalize()} uploaded successfully.")
            click.echo(f"{upload_type.capitalize()} uploaded successfully.")
        else:
            logging.warning("Failed to open device.")
            click.echo("Failed to open device.")
    except Exception as e:
        logging.exception(f"Exception occurred during {upload_type} upload.")
        click.echo(f"Failed to upload {upload_type}: {e}")
    finally:
        if controller:
            logging.debug("Closing device.")
            controller.close_device()
            logging.debug("Device closed.")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def upload_image(file_path: str) -> None:
    """Upload an image to the Epomaker device."""
    _upload_file(file_path, is_animation=False)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def upload_animation(file_path: str) -> None:
    """Upload an animation to the Epomaker device."""
    _upload_file(file_path, is_animation=True)


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
