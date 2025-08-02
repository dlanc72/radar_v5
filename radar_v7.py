import requests
from PIL import Image
from waveshare_epd import epd7in3e
import time
from io import BytesIO

# Coordinates for the map
LAT = 29.68
LON = -95.17
ZOOM = 6
API_KEY = "YOUR_GEOAPIFY_API_KEY"  # insert your Geoapify key here

# Use NOAA radar tile source (through OpenWeather for simplicity)
def get_radar_image(size):
    tile_url = "https://tilecache.rainviewer.com/v2/radar/nowcast/0/6/22/37/1_1.png"  # Replace with computed tile if needed
    response = requests.get(tile_url, stream=True, timeout=10)
    response.raise_for_status()
    radar = Image.open(BytesIO(response.content)).convert("RGBA")
    return radar.resize(size, Image.BILINEAR)

def get_static_map(lat, lon, zoom):
    url = (
        f"https://maps.geoapify.com/v1/staticmap?style=osm-bright-smooth"
        f"&width=800&height=480&center=lonlat:{lon},{lat}&zoom={zoom}&apiKey={API_KEY}"
    )
    response = requests.get(url, stream=True, timeout=10)
    response.raise_for_status()
    return Image.open(response.raw).convert("RGBA")

def prepare_for_epd(image):
    """Convert full-color RGBA image to an image suitable for 6-color display"""
    # Convert to RGB first
    rgb_img = image.convert("RGB")

    # Optional: Dither or map to a 6-color palette
    # Define 6-color palette: white, black, red, yellow, green, blue
    palette = [
        (255, 255, 255), (0, 0, 0), (255, 0, 0),
        (255, 255, 0), (0, 255, 0), (0, 0, 255)
    ]

    def closest_color(pixel):
        return min(palette, key=lambda c: sum((p - q) ** 2 for p, q in zip(pixel, c)))

    dithered = Image.new("RGB", rgb_img.size)
    pixels = rgb_img.load()
    out_pixels = dithered.load()

    for y in range(rgb_img.height):
        for x in range(rgb_img.width):
            out_pixels[x, y] = closest_color(pixels[x, y])

    return dithered

def main():
    try:
        print("Fetching base map...")
        base_map = get_static_map(LAT, LON, ZOOM)
        size = base_map.size

        print("Fetching radar overlay...")
        radar_overlay = get_radar_image(size)

        print("Compositing map and radar...")
        combined = Image.alpha_composite(base_map, radar_overlay)

        print("Preparing for EPD display...")
        epd_ready = prepare_for_epd(combined)

        print("Initializing ePaper display...")
        epd = epd7in3e.EPD()
        epd.init()
        epd.Clear()

        print("Displaying image...")
        buf = epd.getbuffer(epd_ready)
        epd.display(buf)
        epd.sleep()
        print("Weather radar display updated.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
