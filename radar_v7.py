import requests
from PIL import Image
from waveshare_epd import epd7in3e
from io import BytesIO

# Config
LAT = 29.68
LON = -95.17
ZOOM = 6
WIDTH, HEIGHT = 800, 480
GEOAPIFY_KEY = "YOUR_GEOAPIFY_API_KEY"  # Replace this

def get_map_bounds():
    delta = 5.0
    return (LAT - delta, LON - delta, LAT + delta, LON + delta)

def get_static_map(lat, lon, zoom):
    url = (
        f"https://maps.geoapify.com/v1/staticmap"
        f"?style=osm-bright-smooth&width={WIDTH}&height={HEIGHT}"
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

        print("Compositing...")
        combined = Image.alpha_composite(base, radar)

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
