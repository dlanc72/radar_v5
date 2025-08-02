Weather Radar displayed on a Waveshare epd7in3e using a Raspberry Pi Zero WH. Pulls the map from Geoapify (with free API key) and weather radar from NOAA. Allows for adjustable lat/long/zoom, and weather is displayed in color depending on severity. Currently set to sleep the display between refreshes, but you can remove that if the refresh time is bothersome.

I have this running every 10 minutes via cron.

Waveshare fresh install insctructions:
https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_(E)_Manual#Working_With_Raspberry_Pi
