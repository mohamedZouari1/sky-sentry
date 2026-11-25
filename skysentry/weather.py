"""Weather history and 7-day forecast from the Meteomatics Weather API.

If Meteomatics credentials are missing or a request fails, the API falls back to
clearly labelled simulated data (``data_quality: "simulated_fallback"``) so the
dashboard always renders.
"""
import logging
import math
import random
from datetime import datetime, timedelta

import requests
from flask import Blueprint, jsonify

from .cities import CITIES
from .config import Config

log = logging.getLogger(__name__)
bp = Blueprint("weather", __name__)


def _auth():
    """HTTP basic-auth tuple for Meteomatics, or None when not configured."""
    if Config.METEOMATICS_USERNAME and Config.METEOMATICS_PASSWORD:
        return (Config.METEOMATICS_USERNAME, Config.METEOMATICS_PASSWORD)
    return None

def get_current_weather(city_name):
    """Get CURRENT weather data from Meteomatics API for the map"""
    if _auth() is None:  # not configured: skip the network round-trip
        return None
    now = datetime.now()
    city_coords = CITIES[city_name]['coords']
    lat, lon = city_coords.split(',')
    
    # Get current temperature only
    temp_param = "t_2m:C"
    
    # Get data for right now
    start_date = now
    end_date = now
    
    base_url = "https://api.meteomatics.com"
    start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = f"{base_url}/{start_str}--{end_str}:PT1H/{temp_param}/{lat},{lon}/json"
    
    
    try:
        log.info(f"🌤️ Fetching CURRENT weather for {city_name}: {url}")
        response = requests.get(url, auth=_auth(), timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                coordinates = data['data'][0]['coordinates'][0]
                if 'dates' in coordinates and len(coordinates['dates']) > 0:
                    current_temp = coordinates['dates'][0]['value']
                    # Convert Kelvin to Celsius if needed
                    if current_temp > 100:
                        current_temp = current_temp - 273.15
                    log.info(f"✅ CURRENT temperature for {city_name}: {current_temp}°C")
                    return round(current_temp, 1)
        return None
    except Exception as e:
        log.warning(f"❌ Error getting current weather: {str(e)}")
        return None

def get_meteomatics_data(lat, lon, start_date, end_date, parameters):
    """Fetch weather data from Meteomatics API"""
    if _auth() is None:  # not configured: skip the network round-trip
        return None
    base_url = "https://api.meteomatics.com"
    
    start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = f"{base_url}/{start_str}--{end_str}:P1D/{parameters}/{lat},{lon}/json"
    
    
    try:
        response = requests.get(url, auth=_auth(), timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        log.warning(f"❌ Error calling Meteomatics API: {str(e)}")
        return None

def parse_meteomatics_data(api_data, data_type):
    """Parse Meteomatics API response"""
    if not api_data or 'data' not in api_data:
        return []
    
    values = []
    for item in api_data['data']:
        if 'coordinates' in item and len(item['coordinates']) > 0:
            coord_data = item['coordinates'][0]
            if 'dates' in coord_data:
                for date_point in coord_data['dates']:
                    if data_type == 'temperature':
                        value = date_point['value']
                        if value > 100:
                            value = value - 273.15
                        values.append(round(value, 1))
                    else:
                        values.append(round(date_point['value'], 1))
    return values

def get_weather_icon(temp, precip, wind):
    """Get accurate weather icon based on realistic conditions"""
    # Based on temperature and precipitation - more realistic approach
    if precip > 15:
        return "🌧️"  # Heavy rain
    elif precip > 7:
        return "🌦️"  # Rain shower
    elif precip > 2:
        return "☔"   # Light rain
    elif temp > 35:
        return "🔥"   # Extreme heat
    elif temp > 28:
        return "☀️"   # Hot and sunny
    elif temp > 22:
        return "🌤️"   # Warm and partly cloudy
    elif temp > 15:
        return "⛅"   # Mild and cloudy
    elif temp > 8:
        return "🌥️"   # Cool and overcast
    elif temp > 0:
        return "🌫️"   # Cold and misty
    else:
        # Only show snow for very cold temperatures (near freezing)
        return "🌨️"   # Freezing conditions

def get_weather_alert(temp, precip, wind):
    """Get accurate weather alert message based on realistic conditions"""
    alerts = []
    
    # Temperature-based alerts (more realistic ranges)
    if temp > 35:
        alerts.append("Extreme Heat Warning")
    elif temp > 30:
        alerts.append("Hot Day Ahead")
    elif temp > 25:
        alerts.append("Warm Weather")
    elif temp < 0:
        alerts.append("Freezing Conditions")
    elif temp < 5:
        alerts.append("Very Cold")
    elif temp < 10:
        alerts.append("Chilly Day")
    else:
        alerts.append("Mild Conditions")
    
    # Precipitation-based alerts
    if precip > 20:
        alerts.append("Heavy Rain Alert")
    elif precip > 10:
        alerts.append("Rain Expected")
    elif precip > 5:
        alerts.append("Light Rain")
    elif precip > 0:
        alerts.append("Possible Drizzle")
    
    # Wind-based alerts
    if wind > 20:
        alerts.append("Strong Winds")
    elif wind > 12:
        alerts.append("Windy Conditions")
    elif wind > 8:
        alerts.append("Breezy")
    
    return " • ".join(alerts[:2])  # Show max 2 most important alerts

def get_real_weather_data(city_name, days_back=60, days_forward=7):
    """Get weather data from Meteomatics API"""
    dates = []
    temperatures = []
    precipitation = []
    wind_speed = []
    
    now = datetime.now()
    city_coords = CITIES[city_name]['coords']
    lat, lon = city_coords.split(',')
    
    # Calculate date ranges
    start_date = now - timedelta(days=days_back)
    end_date = now + timedelta(days=days_forward)
    
    # Generate date labels
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    # Get CURRENT temperature for the map
    current_temp = get_current_weather(city_name)
    
    # Define parameters
    temp_param = "t_2m:C"
    precip_param = "precip_1h:mm"
    wind_param = "wind_speed_10m:ms"
    
    try:
        # Fetch temperature data
        temp_data = get_meteomatics_data(lat, lon, start_date, end_date, temp_param)
        temperatures = parse_meteomatics_data(temp_data, 'temperature')
        
        # Fetch precipitation data
        precip_data = get_meteomatics_data(lat, lon, start_date, end_date, precip_param)
        precipitation = parse_meteomatics_data(precip_data, 'precipitation')
        
        # Fetch wind speed data
        wind_data = get_meteomatics_data(lat, lon, start_date, end_date, wind_param)
        wind_speed = parse_meteomatics_data(wind_data, 'wind')
        
        # If any series is missing (bad credentials, quota, network), serve the
        # clearly labelled simulated dataset instead of mixing real and fake values
        if not (temperatures and precipitation and wind_speed):
            log.warning(f"Meteomatics data unavailable for {city_name} - using simulated fallback")
            return get_fallback_data(city_name, days_back, days_forward)

        # In the historical view the last point is today: use the live reading
        if current_temp is not None and days_forward == 0:
            temperatures[-1] = current_temp
        
        # Generate weather alerts for forecast period ONLY if we have future data
        weather_alerts = []
        today = datetime.now().date()
        
        if days_forward > 0:  # Only generate alerts for forecast data
            for i in range(min(7, len(dates))):
                date_str = dates[i]
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if date_obj >= today:  # Only future dates
                    temp = temperatures[i] if i < len(temperatures) else 0
                    precip = precipitation[i] if i < len(precipitation) else 0
                    wind = wind_speed[i] if i < len(wind_speed) else 0
                    
                    day_name = "Today" if date_obj == today else date_obj.strftime('%a')
                    date_display = date_obj.strftime('%m/%d')
                    
                    weather_alerts.append({
                        'day': day_name,
                        'date': date_display,
                        'temp': temp,
                        'precip': precip,
                        'wind': wind,
                        'icon': get_weather_icon(temp, precip, wind),
                        'alert': get_weather_alert(temp, precip, wind)
                    })
        
        # Ensure all arrays have the same length
        min_length = min(len(temperatures), len(precipitation), len(wind_speed))
        dates = dates[:min_length]
        temperatures = temperatures[:min_length]
        precipitation = precipitation[:min_length]
        wind_speed = wind_speed[:min_length]
        
        return {
            'dates': dates,
            'temperatures': temperatures,
            'precipitation': precipitation,
            'windSpeed': wind_speed,
            'city': city_name,
            'country': CITIES[city_name]['country'],
            'region': CITIES[city_name]['region'],
            'coordinates': CITIES[city_name]['coords'],
            'current_temperature': current_temp if current_temp else temperatures[-1] if temperatures else 0,
            'generated_at': now.isoformat(),
            'data_source': 'Meteomatics Weather API',
            'data_quality': 'real_weather_data',
            'weather_alerts': weather_alerts,
            'is_forecast': days_forward > 0  # Add flag to indicate if this is forecast data
        }
        
    except Exception as e:
        log.warning(f"❌ Error in get_real_weather_data: {str(e)}")
        return get_fallback_data(city_name, days_back, days_forward)

def get_fallback_data(city_name, days_back, days_forward):
    """Provide realistic fallback data"""
    dates = []
    now = datetime.now()
    
    for i in range(-days_back, days_forward + 1):
        date = now + timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))
    
    # Generate realistic fallback weather alerts ONLY for forecast data
    weather_alerts = []
    today = now.date()
    
    if days_forward > 0:  # Only generate alerts for forecast data
        for i in range(min(7, len(dates))):
            date_str = dates[i]
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if date_obj >= today:
                # More realistic temperature progression
                base_temp = 18 + math.sin(i * 0.5) * 6
                temp = base_temp + random.uniform(-2, 2)
                precip = 0 if i % 3 else random.uniform(2, 10)
                wind = 3 + math.sin(i * 0.3) * 3
                
                day_name = "Today" if date_obj == today else date_obj.strftime('%a')
                date_display = date_obj.strftime('%m/%d')
                
                weather_alerts.append({
                    'day': day_name,
                    'date': date_display,
                    'temp': round(temp, 1),
                    'precip': round(precip, 1),
                    'wind': round(wind, 1),
                    'icon': get_weather_icon(temp, precip, wind),
                    'alert': get_weather_alert(temp, precip, wind)
                })
    
    return {
        'dates': dates,
        'temperatures': [18 + math.sin(i * 0.1) * 6 for i in range(len(dates))],
        'precipitation': [0 if i % 4 else random.uniform(2, 8) for i in range(len(dates))],
        'windSpeed': [3 + math.sin(i * 0.2) * 3 for i in range(len(dates))],
        'city': city_name,
        'country': CITIES[city_name]['country'],
        'region': CITIES[city_name]['region'],
        'coordinates': CITIES[city_name]['coords'],
        'current_temperature': 18,
        'generated_at': now.isoformat(),
        'data_source': 'Fallback Data',
        'data_quality': 'simulated_fallback',
        'weather_alerts': weather_alerts,
        'is_forecast': days_forward > 0  # Add flag to indicate if this is forecast data
    }



@bp.route('/api/weather/<data_view>/<city_name>')
def get_weather_data(data_view, city_name):
    """API endpoint for weather data"""
    log.info(f"🌤️ API Request: {data_view} for {city_name}")
    
    if city_name not in CITIES:
        return jsonify({'error': 'City not found'}), 404
    
    try:
        if data_view == 'historical':
            data = get_real_weather_data(city_name, days_back=60, days_forward=0)
        else:
            data = get_real_weather_data(city_name, days_back=0, days_forward=7)
        
        log.info(f"✅ Returned data for {city_name}")
        log.info(f"🌡️ CURRENT TEMPERATURE: {data['current_temperature']}°C")
        return jsonify(data)
        
    except Exception as e:
        log.warning(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
