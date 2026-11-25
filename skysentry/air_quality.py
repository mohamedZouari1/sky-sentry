"""Real-time air quality: WAQI API integration, AQI scale and health guidance."""
import logging
from datetime import datetime

import requests
from flask import Blueprint, jsonify

from .cities import CITIES
from .config import Config

log = logging.getLogger(__name__)
bp = Blueprint("air_quality", __name__)

WAQI_BASE_URL = "https://api.waqi.info/feed/"
# AQI Health Guidelines and Recommendations
AQI_SCALE = {
    (0, 50): {
        "level": "Good",
        "emoji": "✅",
        "color": "#00e400",
        "health_effects": "Air quality is satisfactory with little to no risk",
        "caution": "None",
        "recommendations": [
            "Perfect day for outdoor activities",
            "Great for exercise and sports",
            "Ideal for opening windows for fresh air"
        ]
    },
    (51, 100): {
        "level": "Moderate", 
        "emoji": "⚠️",
        "color": "#ffff00",
        "health_effects": "Acceptable quality but slight concern for sensitive groups",
        "caution": "Unusually sensitive people should consider reducing prolonged outdoor exertion",
        "recommendations": [
            "Sensitive groups should reduce prolonged outdoor exercise",
            "Generally okay for most activities",
            "Monitor symptoms if you have respiratory conditions"
        ]
    },
    (101, 150): {
        "level": "Unhealthy for Sensitive Groups",
        "emoji": "🚨",
        "color": "#ff7e00",
        "health_effects": "General public not affected but sensitive groups may experience health effects",
        "caution": "Children, elderly, and people with lung disease should reduce outdoor exertion",
        "recommendations": [
            "Sensitive groups should avoid prolonged outdoor activities",
            "Everyone should watch for symptoms like coughing or difficulty breathing",
            "Consider moving activities indoors",
            "Keep rescue medication handy if you have asthma"
        ]
    },
    (151, 200): {
        "level": "Unhealthy",
        "emoji": "🔴",
        "color": "#ff0000",
        "health_effects": "Everyone may begin to experience health effects",
        "caution": "Everyone should reduce outdoor exertion",
        "recommendations": [
            "Avoid prolonged outdoor activities",
            "Sensitive groups should avoid all outdoor exertion",
            "Close windows to keep polluted air out",
            "Use air purifiers if available",
            "Wear N95 masks if going outside is necessary"
        ]
    },
    (201, 300): {
        "level": "Very Unhealthy",
        "emoji": "💀",
        "color": "#8f3f97",
        "health_effects": "Health alert - everyone may experience more serious health effects",
        "caution": "Everyone should avoid all outdoor exertion",
        "recommendations": [
            "Stay indoors as much as possible",
            "Avoid all outdoor exercise",
            "Use high-efficiency air purifiers",
            "Wear N95 masks if you must go outside",
            "Keep windows and doors closed",
            "Consider relocating if conditions persist"
        ]
    },
    (301, 500): {
        "level": "Hazardous",
        "emoji": "☠️",
        "color": "#7e0023",
        "health_effects": "Health warnings of emergency conditions - entire population affected",
        "caution": "Everyone should remain indoors and avoid physical activity",
        "recommendations": [
            "EMERGENCY CONDITIONS - Stay indoors",
            "Use air purifiers continuously",
            "Avoid any outdoor exposure",
            "Wear N95 masks even indoors if air quality is poor",
            "Consider temporary relocation",
            "Follow emergency service instructions"
        ]
    }
}

# Pollutant Information
POLLUTANT_INFO = {
    "pm25": {
        "name": "PM2.5",
        "description": "Fine inhalable particles, 2.5 micrometers and smaller",
        "sources": "Vehicle emissions, power plants, wildfires, industrial processes",
        "health_effects": "Can penetrate deep into lungs and enter bloodstream, causing heart and lung diseases"
    },
    "pm10": {
        "name": "PM10", 
        "description": "Inhalable particles, 10 micrometers and smaller",
        "sources": "Dust, pollen, mold, construction sites, agriculture",
        "health_effects": "Can irritate eyes, nose, throat and lungs"
    },
    "o3": {
        "name": "Ozone (O3)",
        "description": "Ground-level ozone, main component of smog",
        "sources": "Chemical reactions between pollutants in sunlight",
        "health_effects": "Chest pain, coughing, throat irritation, worsened bronchitis and asthma"
    },
    "no2": {
        "name": "Nitrogen Dioxide (NO2)",
        "description": "Reddish-brown gas with sharp odor",
        "sources": "Vehicle emissions, power plants, industrial processes",
        "health_effects": "Respiratory infections, asthma, lung tissue damage"
    },
    "so2": {
        "name": "Sulfur Dioxide (SO2)",
        "description": "Colorless gas with sharp odor",
        "sources": "Burning fossil fuels, industrial processes",
        "health_effects": "Breathing difficulties, respiratory illness, cardiovascular disease"
    },
    "co": {
        "name": "Carbon Monoxide (CO)",
        "description": "Colorless, odorless gas",
        "sources": "Vehicle exhaust, incomplete combustion",
        "health_effects": "Headaches, dizziness, heart strain, reduced oxygen delivery"
    }
}

def get_aqi_info(aqi_value):
    """Get AQI level information based on AQI value"""
    if aqi_value == "No Data":
        return {
            "level": "No Data",
            "emoji": "❓", 
            "color": "#666666",
            "health_effects": "Real-time air quality data not available",
            "caution": "Check local air quality reports",
            "recommendations": ["Data currently unavailable - check back later"]
        }
    
    for (low, high), info in AQI_SCALE.items():
        if low <= aqi_value <= high:
            return info
    return AQI_SCALE[(0, 50)]  # Default to Good

def get_realtime_air_quality(city_name):
    """Get REAL-TIME air quality data from WAQI API - 100% REAL DATA ONLY"""
    if city_name not in CITIES:
        return None
    
    coords = CITIES[city_name]['coords']
    lat, lon = coords.split(',')
    
    # Construct WAQI API URL for geo coordinates
    url = f"{WAQI_BASE_URL}geo:{lat};{lon}/"
    
    if not Config.WAQI_API_TOKEN:
        log.warning("WAQI_API_TOKEN is not set - returning 'No Data' (see .env.example)")
        return generate_no_data_response(city_name)

    try:
        log.info(f"🌫️ Fetching 100% REAL air quality for {city_name}")
        response = requests.get(url, params={'token': Config.WAQI_API_TOKEN}, timeout=15)
        data = response.json()
        
        if data.get('status') == 'ok':
            log.info(f"✅ SUCCESS: Got REAL data for {city_name}")
            return parse_waqi_data(data, city_name)
        else:
            log.warning(f"❌ NO REAL DATA for {city_name}: {data.get('data', 'Unknown error')}")
            return generate_no_data_response(city_name)
            
    except Exception as e:
        log.warning(f"❌ Error fetching air quality: {str(e)}")
        return generate_no_data_response(city_name)

def parse_waqi_data(api_data, city_name):
    """Parse WAQI API response - ONLY USE REAL DATA"""
    data = api_data['data']
    
    # Extract REAL data from API
    aqi = data.get('aqi', "No Data")
    # WAQI reports "-" when a station has no current reading
    if not isinstance(aqi, (int, float)):
        aqi = "No Data"
    city_info = data.get('city', {})
    dominant_pollutant = data.get('dominentpol', 'Unknown')
    
    # Extract ONLY REAL pollutant values
    pollutants = {}
    iaqi = data.get('iaqi', {})
    for poll, info in iaqi.items():
        pollutants[poll] = info.get('v', "No Data")
    
    # Get REAL time data
    time_data = data.get('time', {})
    measured_time = time_data.get('s', datetime.now().isoformat())
    
    # Get AQI level information
    aqi_info = get_aqi_info(aqi)
    
    # Generate health recommendations based on REAL data
    recommendations = generate_health_recommendations(aqi, pollutants, dominant_pollutant)
    
    return {
        'city': city_name,
        'city_display': city_info.get('name', city_name.replace('_', ' ').title()),
        'country': CITIES[city_name]['country'],
        'region': CITIES[city_name]['region'],
        'coordinates': CITIES[city_name]['coords'],
        
        # AQI Data - REAL or "No Data"
        'aqi': aqi,
        'aqi_level': aqi_info['level'],
        'aqi_emoji': aqi_info['emoji'],
        'aqi_color': aqi_info['color'],
        'dominant_pollutant': dominant_pollutant,
        
        # Pollutant Data - ONLY REAL VALUES
        'pollutants': pollutants,
        
        # Health Information
        'health_effects': aqi_info['health_effects'],
        'caution': aqi_info['caution'],
        'recommendations': recommendations,
        
        # Data Quality Info
        'measured_time': measured_time,
        'generated_at': datetime.now().isoformat(),
        'data_source': 'WAQI Air Quality API',
        'data_quality': '100_percent_real',
        'has_real_data': aqi != "No Data",
        
        # For charts and alerts
        'current_aqi': aqi,
        'pollutant_levels': pollutants
    }

def generate_no_data_response(city_name):
    """Generate response when no real data is available"""
    return {
        'city': city_name,
        'city_display': city_name.replace('_', ' ').title(),
        'country': CITIES[city_name]['country'],
        'region': CITIES[city_name]['region'],
        'coordinates': CITIES[city_name]['coords'],
        
        'aqi': "No Data",
        'aqi_level': "No Data",
        'aqi_emoji': "❓",
        'aqi_color': "#666666",
        'dominant_pollutant': "Unknown",
        
        'pollutants': {
            'pm25': "No Data",
            'pm10': "No Data", 
            'o3': "No Data",
            'no2': "No Data",
            'so2': "No Data",
            'co': "No Data"
        },
        
        'health_effects': "Real-time air quality data not available",
        'caution': "Check local air quality reports for current conditions",
        'recommendations': [
            "Real-time data is currently unavailable",
            "Check official local air quality sources",
            "Use general air quality precautions",
            "Data should be available again soon"
        ],
        
        'measured_time': datetime.now().isoformat(),
        'generated_at': datetime.now().isoformat(),
        'data_source': 'WAQI Air Quality API - Data Temporarily Unavailable',
        'data_quality': 'no_data_available',
        'has_real_data': False,
        
        'current_aqi': "No Data",
        'pollutant_levels': {}
    }

def generate_health_recommendations(aqi, pollutants, dominant_pollutant):
    """Generate health recommendations based on REAL data"""
    if aqi == "No Data":
        return [
            "Real-time air quality data is currently unavailable",
            "Check local weather and air quality reports",
            "Use general air pollution precautions",
            "Sensitive groups should be cautious outdoors"
        ]
    
    recommendations = []
    aqi_info = get_aqi_info(aqi)
    
    # Base recommendations from AQI level
    recommendations.extend(aqi_info['recommendations'])
    
    # Only add specific recommendations if we have real pollutant data
    if dominant_pollutant != 'Unknown':
        if dominant_pollutant == 'pm25':
            recommendations.extend([
                "Use high-efficiency air purifiers with HEPA filters",
                "Avoid burning candles or incense indoors",
                "Consider using an N95 mask for outdoor activities"
            ])
        elif dominant_pollutant == 'o3':
            recommendations.extend([
                "Schedule outdoor activities for morning when ozone levels are lower",
                "Avoid vigorous outdoor exercise during afternoon hours",
                "Stay indoors during peak sunlight hours"
            ])
        elif dominant_pollutant == 'no2':
            recommendations.extend([
                "Avoid high-traffic areas when possible",
                "Use exhaust fans when cooking with gas stoves",
                "Ensure proper ventilation in garages"
            ])
    
    # Additional recommendations for sensitive groups
    recommendations.extend([
        "People with asthma should keep rescue inhalers accessible",
        "Elderly and children should limit outdoor exposure",
        "Consult doctor if experiencing breathing difficulties"
    ])
    
    return recommendations

def get_historical_trends(city_name, days=7):
    """Get historical trend data - SIMPLIFIED FOR REAL DATA"""
    # For real data approach, we'll just return current data
    # since historical data requires premium API access
    current_data = get_realtime_air_quality(city_name)
    
    if not current_data or not current_data['has_real_data']:
        return {
            'dates': [],
            'aqi_trend': [],
            'pm25_trend': [],
            'current_aqi': "No Data",
            'trend_direction': 'unknown',
            'data_quality': 'no_historical_data'
        }
    
    # Create simple trend with current data only
    dates = [datetime.now().strftime('%Y-%m-%d')]
    aqi_values = [current_data['aqi']] if current_data['aqi'] != "No Data" else ["No Data"]
    pm25_value = current_data['pollutants'].get('pm25', "No Data")
    pm25_values = [pm25_value] if pm25_value != "No Data" else ["No Data"]
    
    return {
        'dates': dates,
        'aqi_trend': aqi_values,
        'pm25_trend': pm25_values,
        'current_aqi': current_data['aqi'],
        'trend_direction': 'current_only',
        'data_quality': 'current_data_only'
    }



@bp.route('/api/air-quality/<city_name>')
def get_air_quality_data(city_name):
    """API endpoint for real-time air quality data - 100% REAL DATA"""
    log.info(f"🌫️ API Request: Air quality for {city_name}")
    
    if city_name not in CITIES:
        return jsonify({'error': 'City not found'}), 404
    
    try:
        air_quality_data = get_realtime_air_quality(city_name)
        return jsonify(air_quality_data)
        
    except Exception as e:
        log.warning(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/historical/<city_name>')
def get_historical_data(city_name):
    """API endpoint for historical air quality trends"""
    if city_name not in CITIES:
        return jsonify({'error': 'City not found'}), 404
    try:
        historical_data = get_historical_trends(city_name, days=7)
        return jsonify(historical_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
