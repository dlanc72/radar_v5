import requests
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd7in3e
from io import BytesIO
from datetime import datetime

# Config
LAT = 29.6165
LON = -95.1696
ZOOM = 6.5
WIDTH, HEIGHT = 800, 480
GEOAPIFY_KEY = "YOUR_GEOAPIFY_API_KEY"  # Replace this

def get_map_bounds():
    delta = 5.0
    return (LAT - delta, LON - delta, LAT + delta, LON + delta)

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

def reduce_opacity(image, alpha_factor):
    """Lower the opacity of an RGBA image."""
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
        bounds = get_map_bounds()
        print("Downloading base map...")
        base = get_static_map(LAT, LON, ZOOM)

        print("Downloading NOAA radar...")
        radar = get_noaa_radar(bounds)

        print("Reducing radar opacity...")
        radar = reduce_opacity(radar, 0.7)  # 70% transparency

        # Composite in the right order to lose less detail
        base = get_static_map(LAT, LON, ZOOM)
        radar = reduce_opacity(get_noaa_radar(bounds), 0.3)

        # Create a transparent overlay image for annotations
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
