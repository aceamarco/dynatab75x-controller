from PIL import Image, ImageDraw, ImageFont
from epomakercontroller import EpomakerController
import os
import argparse


def render_text_on_canvas(
    text_segments,
    font=ImageFont.load_default(),
    align="left",
    canvas_width=60,
    canvas_height=9,
    debug=False,
):
    """
    Renders multicolor text segments on a canvas.

    Parameters:
    - text_segments: List of tuples like [(text1, color1), (text2, color2), ...].
    - font: PIL ImageFont object.
    - align: 'left', 'center', or 'right'.
    - canvas_width: Width of the canvas.
    - canvas_height: Height of the canvas.
    - debug: If True, saves the image to disk.

    Returns:
    - image: PIL Image object with rendered text.
    """

    image = Image.new("RGB", (canvas_width, canvas_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Compute total text width
    total_width = sum(draw.textlength(text, font=font) for text, _ in text_segments)

    # Determine starting x position based on alignment
    if align == "left":
        x = 0
    elif align == "center":
        x = (canvas_width - total_width) // 2
    elif align == "right":
        x = canvas_width - total_width
    else:
        raise ValueError("Alignment must be 'left', 'center', or 'right'")

    y = 0  # top-aligned

    # Draw each text segment
    for segment_text, color in text_segments:
        draw.text((x, y), segment_text, font=font, fill=color, anchor="lt")
        x += draw.textlength(segment_text, font=font)

    if debug:
        output_directory = "debug_images"
        os.makedirs(output_directory, exist_ok=True)
        image.save(os.path.join(output_directory, "rendered_text.png"))
        print("Debug image saved.")

    return image


def send_text(colored_text=[("Hello, World!", (0, 0, 255))], font=None, debug=False):
    if font is None:
        font = ImageFont.load_default()

    image = render_text_on_canvas(colored_text, font=font, align="center", debug=debug)

    controller = EpomakerController()
    if controller.open_device():
        controller.send_image(image)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send text to Epomaker LCD.")
    parser.add_argument(
        "--text", type=str, default="Hello, World!", help="Text to display"
    )
    parser.add_argument(
        "--color", type=str, default="0,0,255", help="Text color as R,G,B"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Parse color input
    try:
        color = tuple(map(int, args.color.split(",")))
        assert len(color) == 3 and all(0 <= c <= 255 for c in color)
    except Exception:
        raise ValueError("Color must be in R,G,B format with values from 0 to 255.")

    send_text(colored_text=[(args.text, color)], debug=args.debug)
