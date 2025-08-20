import requests
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd7in3e
from io import BytesIO
from datetime import datetime
import math

# Config
LAT = XX.XXXX
LON = -YY.YYYY
ZOOM = 6.5
WIDTH, HEIGHT = 800, 480
GEOAPIFY_KEY = "YOUR_GEOAPIFY_API_KEY"  # Replace this

# --- Radar adjustment (tweak these) ---
RADAR_SCALE = 1.05     # >1 zoom in, <1 zoom out
RADAR_OFFSET_X = 0    # positive = shift right, negative = left
RADAR_OFFSET_Y = -0    # positive = shift down, negative = up
# --------------------------------------

def get_map_bounds_from_zoom(lat, lon, zoom, width, height):
    # Web Mercator projection
    def lon_to_x(lon): return (lon + 180) / 360 * 256 * 2**zoom
    def lat_to_y(lat):
        rad = math.radians(lat)
        return (1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * 256 * 2**zoom

    center_x = lon_to_x(lon)
    center_y = lat_to_y(lat)

    half_w = width / 2
    half_h = height / 2

    def x_to_lon(x): return x / (256 * 2**zoom) * 360 - 180
    def y_to_lat(y):
        n = math.pi - 2 * math.pi * y / (256 * 2**zoom)
        return math.degrees(math.atan(math.sinh(n)))

    min_lon = x_to_lon(center_x - half_w)
    max_lon = x_to_lon(center_x + half_w)
    max_lat = y_to_lat(center_y - half_h)
    min_lat = y_to_lat(center_y + half_h)

    return min_lat, min_lon, max_lat, max_lon

def get_static_map(lat, lon, zoom):
    url = (
        f"https://maps.geoapify.com/v1/staticmap"
        f"?style=toner-grey&width={WIDTH}&height={HEIGHT}"
        f"&center=lonlat:{lon},{lat}&zoom={zoom}&apiKey={GEOAPIFY_KEY}"
    )
    r = requests.get(url, stream=True, timeout=10)
    r.raise_for_status()
    return Image.open(r.raw).convert("RGBA")

def get_noaa_radar(bounds):
    min_lat, min_lon, max_lat, max_lon = bounds
    wms_url = "https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows"
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": "conus:conus_bref_qcd",
        "bbox": f"{min_lat},{min_lon},{max_lat},{max_lon}",
        "crs": "EPSG:4326",
        "width": WIDTH,
        "height": HEIGHT,
        "format": "image/png",
        "transparent": "true"
    }
    r = requests.get(wms_url, params=params, timeout=10)
    r.raise_for_status()
    return Image.open(BytesIO(r.content)).convert("RGBA")

def adjust_radar(radar):
    """Scale and offset radar overlay for better alignment."""
    # Scale
    new_size = (int(WIDTH * RADAR_SCALE), int(HEIGHT * RADAR_SCALE))
    radar = radar.resize(new_size, Image.BICUBIC)

    # Center back onto a blank canvas
    offset_x = (WIDTH - radar.width) // 2 + RADAR_OFFSET_X
    offset_y = (HEIGHT - radar.height) // 2 + RADAR_OFFSET_Y

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    canvas.paste(radar, (offset_x, offset_y), radar)
    return canvas

def reduce_opacity(image, alpha_factor):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    alpha = image.split()[3]
    alpha = alpha.point(lambda p: int(p * alpha_factor))
    image.putalpha(alpha)
    return image

def latlon_to_pixel(lat, lon, bounds, image_size):
    min_lat, min_lon, max_lat, max_lon = bounds
    width, height = image_size
    x = (lon - min_lon) / (max_lon - min_lon) * width
    y = (max_lat - lat) / (max_lat - min_lat) * height
    return int(x), int(y)

def prepare_for_epd(image):
    palette = [
        (255, 255, 255), (0, 0, 0), (255, 0, 0),
        (255, 255, 0), (0, 255, 0), (0, 0, 255)
    ]
    def closest(c):
        return min(palette, key=lambda p: sum((x - y) ** 2 for x, y in zip(c, p)))
    rgb = image.convert("RGB")
    result = Image.new("RGB", image.size)
    for y in range(image.height):
        for x in range(image.width):
            result.putpixel((x, y), closest(rgb.getpixel((x, y))))
    return result

def main():
    try:
        print("Getting map bounds...")
        bounds = get_map_bounds_from_zoom(LAT, LON, ZOOM, WIDTH, HEIGHT)

        print("Downloading base map...")
        base = get_static_map(LAT, LON, ZOOM)

        print("Downloading NOAA radar...")
        radar = get_noaa_radar(bounds)

        print("Adjusting radar position/scale...")
        radar = adjust_radar(radar)  # <-- new step

        print("Reducing radar opacity...")
        radar = reduce_opacity(radar, 0.7)

        # Create overlay for crosshair + timestamp
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Crosshair
        x, y = latlon_to_pixel(LAT, LON, bounds, base.size)
        size = 10
        draw.line([(x - size, y), (x + size, y)], fill=(255, 0, 0, 255), width=2)
        draw.line([(x, y - size), (x, y + size)], fill=(255, 0, 0, 255), width=2)

        # Timestamp
        timestamp = datetime.now().strftime("Last updated: %Y-%m-%d %H:%M")
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
        bbox = draw.textbbox((0, 0), timestamp, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        padding = 5
        tx = padding
        ty = overlay.height - text_height - padding
        draw.rectangle(
            [tx - 2, ty - 2, tx + text_width + 2, ty + text_height + 2],
            fill=(255, 255, 255, 200)
        )
        draw.text((tx, ty), timestamp, font=font, fill=(255, 0, 0, 255))

        # Composite base + radar + overlay
        combined = Image.alpha_composite(base, radar)
        combined = Image.alpha_composite(combined, overlay)

        print("Preparing for EPD...")
        epd_ready = prepare_for_epd(combined)

        print("Initializing ePaper...")
        epd = epd7in3e.EPD()
        epd.init()
        epd.Clear()

        print("Displaying image...")
        buf = epd.getbuffer(epd_ready)
        epd.display(buf)
        epd.sleep()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
