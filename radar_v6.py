import requests
from PIL import Image, ImageDraw
from waveshare_epd import epd7in3e
import time

# Coordinates for the map
LAT = 29.68  # Your latitude
LON = -95.17  # Your longitude
ZOOM = 6  # Map zoom level


# Geoapify static map provider URL (replace with your preferred static map API)
def get_static_map(lat, lon, zoom):
    # Using Static Map Lite (free with limitations)
    url = f"https://maps.geoapify.com/v1/staticmap?style=osm-bright-smooth&width=800&height=480&center=lonlat:{LON},{LAT}&zoom={ZOOM}&apiKey="
    response = requests.get(url, stream=True)
    response.raise_for_status()
    try:
        return Image.open(response.raw)
        print(f"Map image generated.")
    except Exception as e:
        print(f"Failed to open map image: {e}")
        return Image.new('RGBA', (800, 480), (255, 255, 255, 255))  # fallback blank image


def fetch_weather_alerts():
    """Fetch active weather alerts from weather.gov; no API key needed."""
    headers = {'User-Agent': 'weather_monitor/1.0'}
    url = f'https://api.weather.gov/alerts/active?point={LAT},{LON}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def parse_alerts_and_severity(alerts_json):
    """Parse weather alerts and determine severity for overlay."""
    severity_overlays = []
    if 'features' in alerts_json:
        for feature in alerts_json['features']:
            properties = feature['properties']
            severity = properties.get('severity', 'Unknown')
            geometry = feature['geometry']
            # Map severity to RGBA color with transparency
            if severity == 'Minor':
                color = (0, 255, 0, 128)  # Green
            elif severity == 'Moderate':
                color = (255, 255, 0, 128)  # Yellow
            elif severity == 'Severe':
                color = (255, 0, 0, 128)  # SRed
            elif severity == 'Extreme':
                color = (0, 0, 255, 128)  # Blue for extreme
            else:
                continue  # Skip unknown
            if geometry:
                severity_overlays.append((color, geometry))
    return severity_overlays


def latlon_to_xy(coord, map_bounds, size):
    """
    Transform geo-coordinates (lon, lat) into pixel positions on the map.
    GeoJSON uses [lon, lat] order.
    """
    min_lat, min_lon, max_lat, max_lon = map_bounds
    width, height = size
    lon, lat = coord
    x = (lon - min_lon) / (max_lon - min_lon) * width
    y = (max_lat - lat) / (max_lat - min_lat) * height
    return (x, y)


def get_map_bounds():
    """
    Estimate wide enough map bounds to include local weather alerts.
    Using ±5 degrees from the center to ensure visibility of large alert areas.
    """
    delta_lat = 5.0
    delta_lon = 5.0
    return (
        LAT - delta_lat, LON - delta_lon,
        LAT + delta_lat, LON + delta_lon
    )


def create_alert_overlay(overlays, map_bounds, size):
    """Create RGBA overlay for alert polygons."""
    overlay = Image.new('RGBA', size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    for color, geom in overlays:
        if geom['type'] == 'Polygon':
            coords_list = [latlon_to_xy(coord, map_bounds, size) for coord in geom['coordinates'][0]]
            draw.polygon(coords_list, fill=color)
        elif geom['type'] == 'MultiPolygon':
            for poly in geom['coordinates']:
                coords_list = [latlon_to_xy(coord, map_bounds, size) for coord in poly[0]]
                draw.polygon(coords_list, fill=color)
        # Add support for other geometry types as needed

    return overlay


def main():
    # Step 1: Fetch static map background
    base_map = get_static_map(LAT, LON, ZOOM).convert('RGBA')
    size = base_map.size

    # Step 2: Fetch weather alerts
    alerts_json = fetch_weather_alerts()

    # Step 3: Parse alert geometries and severity
    overlays_info = parse_alerts_and_severity(alerts_json)

    # Step 4: Get map bounds for coordinate conversion
    bounds = get_map_bounds()

    # Step 5: Create overlay image from alert geometries
    overlay = create_alert_overlay(overlays_info, bounds, size)

    # Step 6: Combine overlay with the base map
    try:
        combined = Image.alpha_composite(base_map, overlay)
        print("Radar image created.")
        # Step 7: Display on ePD
        epd = epd7in3e.EPD()
        epd.init()
        epd.Clear()
        # Convert PIL image to buffer compatible with the display
        buf = epd.getbuffer(combined)
        epd.display(buf)
        epd.sleep()
        print("Weather display updated.")
    except Exception as e:
        print(f"Error: {e}")
if __name__ == "__main__":
    main()