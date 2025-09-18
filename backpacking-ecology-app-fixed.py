"""
Global Backpacking + Ecology App - Streamlit Version
Requirements file (requirements.txt):
streamlit==1.29.0
folium==0.15.0
streamlit-folium==0.15.0
requests==2.31.0
pandas==2.1.3
geopy==2.4.0
openmeteo-requests==1.2.0
python-dateutil==2.8.2
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import json
import math

# Page config
st.set_page_config(
    page_title="Global Backpacking + Ecology App",
    page_icon="🏔️",
    layout="wide"
)

# Initialize session state
if 'selected_trail' not in st.session_state:
    st.session_state.selected_trail = None
if 'itinerary' not in st.session_state:
    st.session_state.itinerary = None

# Helper Functions
@st.cache_data
def get_location_coords(location_name):
    """Convert location name to coordinates"""
    geolocator = Nominatim(user_agent="backpacking_app")
    try:
        location = geolocator.geocode(location_name)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

@st.cache_data
def fetch_trails_from_osm(lat, lon, radius_km=50):
    """Fetch hiking trails from OpenStreetMap using Overpass API"""
    overpass_url = "http://overpass-api.de/api/interpreter"
    radius_m = radius_km * 1000
    
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"="path"](around:{radius_m},{lat},{lon});
      way["highway"="footway"](around:{radius_m},{lat},{lon});
      way["route"="hiking"](around:{radius_m},{lat},{lon});
      node["tourism"="camp_site"](around:{radius_m},{lat},{lon});
      node["amenity"="shelter"](around:{radius_m},{lat},{lon});
      node["natural"="spring"](around:{radius_m},{lat},{lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        response = requests.get(overpass_url, params={'data': query}, timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

@st.cache_data
def fetch_weather_data(lat, lon, days=7):
    """Fetch weather forecast from Open-Meteo"""
    base_url = "https://api.open-meteo.com/v1/forecast"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,sunrise,sunset",
        "temperature_unit": "celsius",
        "windspeed_unit": "kmh",
        "precipitation_unit": "mm",
        "timezone": "auto",
        "forecast_days": days
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

@st.cache_data
def fetch_air_quality(lat, lon):
    """Fetch air quality data from Open-Meteo"""
    base_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,us_aqi",
        "timezone": "auto"
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def calculate_daylight_hours(sunrise, sunset):
    """Calculate daylight hours from sunrise/sunset strings"""
    try:
        sunrise_time = datetime.fromisoformat(sunrise)
        sunset_time = datetime.fromisoformat(sunset)
        duration = sunset_time - sunrise_time
        return round(duration.total_seconds() / 3600, 1)
    except:
        return 12  # Default

def generate_gear_recommendations(weather_data, season, trip_days, terrain="mixed"):
    """Generate gear recommendations based on conditions"""
    gear_list = {
        "Essential": [],
        "Clothing": [],
        "Shelter & Sleep": [],
        "Cooking & Hydration": [],
        "Navigation & Safety": [],
        "Wildlife Protection": []
    }
    
    # Temperature analysis
    if weather_data:
        min_temps = weather_data.get('daily', {}).get('temperature_2m_min', [])
        max_temps = weather_data.get('daily', {}).get('temperature_2m_max', [])
        avg_min = sum(min_temps[:trip_days]) / len(min_temps[:trip_days]) if min_temps else 10
        avg_max = sum(max_temps[:trip_days]) / len(max_temps[:trip_days]) if max_temps else 20
        total_precip = sum(weather_data.get('daily', {}).get('precipitation_sum', [])[:trip_days])
    else:
        avg_min, avg_max, total_precip = 10, 20, 0
    
    # Essential gear
    gear_list["Essential"] = [
        f"Backpack (50-65L for {trip_days} days)",
        "First aid kit (wilderness rated)",
        "Multi-tool or knife",
        "Headlamp + spare batteries",
        "Emergency whistle",
        "Fire starter (waterproof matches/lighter)"
    ]
    
    # Shelter & Sleep based on temperature
    if avg_min < 0:
        gear_list["Shelter & Sleep"].extend([
            "4-season tent (MSR Access 2 or similar)",
            "Sleeping bag rated to -10°C (Western Mountaineering Alpinlite)",
            "Insulated sleeping pad (R-value 5+, Thermarest XTherm)"
        ])
        gear_list["Clothing"].append("Down jacket (800+ fill, Arc'teryx Cerium or similar)")
    elif avg_min < 10:
        gear_list["Shelter & Sleep"].extend([
            "3-season tent (Big Agnes Copper Spur HV UL2)",
            "Sleeping bag rated to 0°C (REI Magma 15)",
            "Sleeping pad (R-value 3-4, Nemo Tensor)"
        ])
        gear_list["Clothing"].append("Synthetic insulated jacket (Patagonia Nano Puff)")
    else:
        gear_list["Shelter & Sleep"].extend([
            "Ultralight tent or tarp (Zpacks Duplex)",
            "Summer quilt (20°C rating, Enlightened Equipment)",
            "Lightweight pad (R-value 2-3, Sea to Summit Ultralight)"
        ])
    
    # Clothing layers
    gear_list["Clothing"].extend([
        "Merino wool base layer (Smartwool 150)",
        "Hiking pants (convertible, Prana Stretch Zion)",
        "Moisture-wicking t-shirts (2-3)",
        f"Rain jacket (Gore-Tex, {'essential' if total_precip > 20 else 'recommended'})",
        "Fleece or soft-shell mid-layer",
        "Sun hat with brim",
        "Hiking socks (merino wool, 3-4 pairs, Darn Tough)"
    ])
    
    if avg_min < 5:
        gear_list["Clothing"].extend([
            "Insulated gloves (OR Versaliner)",
            "Warm hat (merino or fleece beanie)",
            "Long underwear (merino wool bottoms)"
        ])
    
    # Cooking & Hydration
    gear_list["Cooking & Hydration"] = [
        "Lightweight stove (MSR PocketRocket or Jetboil)",
        f"Fuel canisters ({math.ceil(trip_days/3)} x 110g)",
        "Titanium pot (750ml minimum)",
        "Spork or lightweight utensils",
        "Water filtration (Sawyer Squeeze or Katadyn BeFree)",
        "Water bottles or hydration bladder (3L capacity)",
        "Water purification tablets (backup)"
    ]
    
    # Navigation & Safety
    gear_list["Navigation & Safety"] = [
        "Topographic maps (waterproof/laminated)",
        "Compass (Silva or Suunto)",
        "GPS device or smartphone with offline maps",
        "Emergency shelter (SOL bivy or space blanket)",
        "Paracord (15m minimum)",
        "Duct tape (wrapped on trekking poles)"
    ]
    
    # Wildlife protection (region-specific)
    if season in ["spring", "summer", "fall"]:
        gear_list["Wildlife Protection"] = [
            "Bear canister (BearVault BV500) or rope for hanging",
            "Bear spray (if in grizzly country)",
            "Insect repellent (DEET or Picaridin)",
            "Head net (if heavy bug season)"
        ]
    
    return gear_list

def create_daily_itinerary(total_distance, trip_days, trail_name, waypoints=None):
    """Generate daily hiking itinerary"""
    avg_daily_distance = total_distance / trip_days
    itinerary = []
    
    for day in range(1, trip_days + 1):
        day_data = {
            "day": day,
            "distance_km": round(avg_daily_distance + ((-1)**day * avg_daily_distance * 0.1), 1),
            "estimated_hours": round(avg_daily_distance / 3.5, 1),  # Assuming 3.5 km/h pace
            "campsite": f"Campsite {day}" if not waypoints else f"Waypoint {day}",
            "water_sources": "Stream/Spring available" if day % 2 == 0 else "Carry water",
            "notes": []
        }
        
        # Add day-specific notes
        if day == 1:
            day_data["notes"].append("Start early to beat crowds")
        elif day == trip_days:
            day_data["notes"].append("Final day - arrange pickup/transport")
        
        itinerary.append(day_data)
    
    return itinerary

# Main App Layout
st.title("🏔️ Global Backpacking + Ecology App")
st.markdown("Plan multi-day backpacking trips with real-time ecological data and gear recommendations")

# Sidebar for inputs
with st.sidebar:
    st.header("Trip Planning")
    
    # Location input
    col1, col2 = st.columns(2)
    with col1:
        input_method = st.radio("Input Method", ["Location Name", "Coordinates"])
    
    if input_method == "Location Name":
        location_name = st.text_input("Enter Location", "Yosemite National Park")
        if st.button("Get Coordinates"):
            lat, lon = get_location_coords(location_name)
            if lat and lon:
                st.session_state.lat = lat
                st.session_state.lon = lon
                st.success(f"Found: {lat:.4f}, {lon:.4f}")
            else:
                st.error("Location not found")
    else:
        lat = st.number_input("Latitude", value=37.8651, min_value=-90.0, max_value=90.0)
        lon = st.number_input("Longitude", value=-119.5383, min_value=-180.0, max_value=180.0)
        st.session_state.lat = lat
        st.session_state.lon = lon
    
    st.divider()
    
    # Trip parameters
    trip_days = st.slider("Trip Duration (days)", 1, 14, 3)
    season = st.selectbox("Season", ["spring", "summer", "fall", "winter"])
    terrain = st.selectbox("Terrain Type", ["mixed", "alpine", "forest", "desert", "coastal"])
    pace = st.select_slider("Hiking Pace", ["leisurely", "moderate", "aggressive"], value="moderate")
    
    # Distance targets based on pace
    pace_distances = {
        "leisurely": 10,
        "moderate": 15,
        "aggressive": 25
    }
    daily_distance_target = pace_distances[pace]
    
    st.divider()
    search_radius = st.slider("Search Radius (km)", 10, 100, 50)
    
    if st.button("🔍 Search Trails & Generate Plan", type="primary"):
        st.session_state.search_triggered = True

# Main content area
if hasattr(st.session_state, 'search_triggered') and hasattr(st.session_state, 'lat'):
    lat, lon = st.session_state.lat, st.session_state.lon
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📍 Map & Trails", "🌤️ Weather & Ecology", "🎒 Gear List", "📅 Itinerary"])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Trail Map")
            
            # Create folium map
            m = folium.Map(location=[lat, lon], zoom_start=11)
            
            # Add center marker
            folium.Marker(
                [lat, lon],
                popup="Search Center",
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)
            
            # Fetch and display trails
            with st.spinner("Fetching trails from OpenStreetMap..."):
                osm_data = fetch_trails_from_osm(lat, lon, search_radius)
            
            if osm_data and osm_data.get('elements'):
                # Add trail waypoints to map
                trail_count = 0
                for element in osm_data['elements'][:20]:  # Limit to first 20
                    if element.get('type') == 'node' and 'lat' in element and 'lon' in element:
                        if element.get('tags', {}).get('tourism') == 'camp_site':
                            folium.Marker(
                                [element['lat'], element['lon']],
                                popup=f"Campsite: {element.get('tags', {}).get('name', 'Unnamed')}",
                                icon=folium.Icon(color="green", icon="home")
                            ).add_to(m)
                        elif element.get('tags', {}).get('amenity') == 'shelter':
                            folium.Marker(
                                [element['lat'], element['lon']],
                                popup="Shelter",
                                icon=folium.Icon(color="blue", icon="home")
                            ).add_to(m)
                        elif element.get('tags', {}).get('natural') == 'spring':
                            folium.Marker(
                                [element['lat'], element['lon']],
                                popup="Water Source",
                                icon=folium.Icon(color="lightblue", icon="tint")
                            ).add_to(m)
                    elif element.get('type') == 'way':
                        trail_count += 1
            
            # Display map
            st_folium(m, height=500, width=None, returned_objects=["last_object_clicked"])
            
            if osm_data:
                st.info(f"Found {trail_count} trails and hiking paths in the area")
        
        with col2:
            st.subheader("Trail Information")
            
            # Mock trail data for demonstration
            sample_trails = pd.DataFrame({
                'Trail Name': ['Summit Loop', 'Valley Trail', 'Ridge Route', 'Lake Circuit'],
                'Distance (km)': [daily_distance_target * trip_days, 
                                daily_distance_target * trip_days * 0.8, 
                                daily_distance_target * trip_days * 1.2,
                                daily_distance_target * trip_days * 0.9],
                'Difficulty': ['Moderate', 'Easy', 'Hard', 'Moderate'],
                'Elevation Gain (m)': [800, 200, 1500, 600]
            })
            
            st.dataframe(sample_trails, hide_index=True)
            
            selected_trail = st.selectbox("Select Trail", sample_trails['Trail Name'].tolist())
            if selected_trail:
                st.session_state.selected_trail = selected_trail
                trail_data = sample_trails[sample_trails['Trail Name'] == selected_trail].iloc[0]
                st.metric("Total Distance", f"{trail_data['Distance (km)']} km")
                st.metric("Daily Average", f"{trail_data['Distance (km)'] / trip_days:.1f} km/day")
    
    with tab2:
        st.subheader("🌤️ Weather Forecast & Ecological Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Fetch weather data
            weather_data = fetch_weather_data(lat, lon, trip_days)
            
            if weather_data:
                st.write("**Weather Forecast**")
                
                # Create weather dataframe
                weather_df = pd.DataFrame({
                    'Day': range(1, trip_days + 1),
                    'Max Temp (°C)': weather_data['daily']['temperature_2m_max'][:trip_days],
                    'Min Temp (°C)': weather_data['daily']['temperature_2m_min'][:trip_days],
                    'Precipitation (mm)': weather_data['daily']['precipitation_sum'][:trip_days],
                    'Wind (km/h)': weather_data['daily']['windspeed_10m_max'][:trip_days],
                    'Daylight Hours': [calculate_daylight_hours(
                        weather_data['daily']['sunrise'][i],
                        weather_data['daily']['sunset'][i]
                    ) for i in range(trip_days)]
                })
                
                st.dataframe(weather_df, hide_index=True)
                
                # Weather warnings
                if any(temp < 0 for temp in weather_data['daily']['temperature_2m_min'][:trip_days]):
                    st.warning("⚠️ Freezing temperatures expected - pack appropriate gear")
                if sum(weather_data['daily']['precipitation_sum'][:trip_days]) > 50:
                    st.warning("⚠️ Significant precipitation expected - ensure waterproof gear")
        
        with col2:
            # Air quality data
            air_quality = fetch_air_quality(lat, lon)
            
            st.write("**Air Quality & Environmental Conditions**")
            
            if air_quality and air_quality.get('current'):
                aqi = air_quality['current'].get('us_aqi', 'N/A')
                
                # AQI interpretation
                aqi_status = "Good"
                aqi_color = "green"
                if aqi != 'N/A':
                    if aqi > 150:
                        aqi_status = "Unhealthy"
                        aqi_color = "red"
                    elif aqi > 100:
                        aqi_status = "Unhealthy for Sensitive Groups"
                        aqi_color = "orange"
                    elif aqi > 50:
                        aqi_status = "Moderate"
                        aqi_color = "yellow"
                
                st.metric("Air Quality Index", f"{aqi} - {aqi_status}")
                
                if aqi != 'N/A' and aqi > 100:
                    st.warning("⚠️ Poor air quality - consider postponing or choosing alternative location")
            
            # Ecological alerts (mock data for demonstration)
            st.write("**Ecological Alerts**")
            
            alerts = {
                "Fire Risk": "Low" if season == "winter" else "Moderate",
                "Wildlife Activity": "High" if season in ["spring", "summer"] else "Low",
                "Trail Conditions": "Good" if season != "winter" else "Icy/Snow",
                "Water Availability": "Good" if season != "summer" else "Limited"
            }
            
            for alert, status in alerts.items():
                color = "🟢" if status in ["Low", "Good"] else "🟡" if status == "Moderate" else "🔴"
                st.write(f"{color} {alert}: {status}")
    
    with tab3:
        st.subheader("🎒 Recommended Gear List")
        
        gear_recommendations = generate_gear_recommendations(
            weather_data if 'weather_data' in locals() else None,
            season,
            trip_days,
            terrain
        )
        
        # Display gear by category
        for category, items in gear_recommendations.items():
            if items:
                with st.expander(f"**{category}** ({len(items)} items)", expanded=True):
                    for item in items:
                        st.checkbox(item, key=f"gear_{category}_{item}")
        
        # Weight estimation
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Base Weight Estimate", f"{8 + trip_days * 0.5:.1f} kg")
        with col2:
            st.metric("Food Weight", f"{0.6 * trip_days:.1f} kg")
        with col3:
            st.metric("Total Pack Weight", f"{8 + trip_days * 1.1:.1f} kg")
        
        # Export gear list
        if st.button("📥 Export Gear List"):
            gear_text = "GEAR LIST\n" + "="*50 + "\n\n"
            for category, items in gear_recommendations.items():
                if items:
                    gear_text += f"\n{category}:\n"
                    for item in items:
                        gear_text += f"  □ {item}\n"
            st.download_button(
                label="Download Gear List (TXT)",
                data=gear_text,
                file_name=f"gear_list_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
    
    with tab4:
        st.subheader("📅 Daily Itinerary")
        
        if st.session_state.selected_trail:
            # Generate itinerary
            trail_data = sample_trails[sample_trails['Trail Name'] == st.session_state.selected_trail].iloc[0]
            itinerary = create_daily_itinerary(
                trail_data['Distance (km)'],
                trip_days,
                st.session_state.selected_trail
            )
            
            # Display itinerary
            for day_info in itinerary:
                with st.expander(f"**Day {day_info['day']}** - {day_info['distance_km']} km", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"📏 Distance: {day_info['distance_km']} km")
                        st.write(f"⏱️ Estimated Time: {day_info['estimated_hours']} hours")
                        st.write(f"🏕️ Camp: {day_info['campsite']}")
                    with col2:
                        st.write(f"💧 Water: {day_info['water_sources']}")
                        if day_info['notes']:
                            st.write(f"📝 Notes: {', '.join(day_info['notes'])}")
                    
                    # Add weather for this day
                    if weather_data and day_info['day'] <= len(weather_data['daily']['temperature_2m_max']):
                        st.divider()
                        st.write("**Day Weather:**")
                        day_idx = day_info['day'] - 1
                        st.write(f"🌡️ {weather_data['daily']['temperature_2m_min'][day_idx]:.0f}°C - "
                               f"{weather_data['daily']['temperature_2m_max'][day_idx]:.0f}°C | "
                               f"💧 {weather_data['daily']['precipitation_sum'][day_idx]:.1f}mm | "
                               f"💨 {weather_data['daily']['windspeed_10m_max'][day_idx]:.0f} km/h")
            
            # Export itinerary
            st.divider()
            if st.button("📥 Export Itinerary"):
                itinerary_text = f"ITINERARY - {st.session_state.selected_trail}\n" + "="*50 + "\n\n"
                for day_info in itinerary:
                    itinerary_text += f"Day {day_info['day']}:\n"
                    itinerary_text += f"  Distance: {day_info['distance_km']} km\n"
                    itinerary_text += f"  Time: {day_info['estimated_hours']} hours\n"
                    itinerary_text += f"  Camp: {day_info['campsite']}\n"
                    itinerary_text += f"  Water: {day_info['water_sources']}\n\n"
                
                st.download_button(
                    label="Download Itinerary (TXT)",
                    data=itinerary_text,
                    file_name=f"itinerary_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
        else:
            st.info("Please select a trail from the Map & Trails tab first")

else:
    # Welcome screen
    st.info("👈 Enter your location and trip details in the sidebar to get started!")
    
    # Feature overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        ### 🗺️ Trail Discovery
        - Search trails globally
        - View campsites & shelters
        - Find water sources
        """)
    
    with col2:
        st.markdown("""
        ### 🌡️ Weather & Ecology
        - Real-time forecasts
        - Air quality monitoring
        - Wildlife activity alerts
        """)
    
    with col3:
        st.markdown("""
        ### 🎒 Smart Packing
        - Condition-based gear
        - Weight optimization
        - Brand recommendations
        """)
    
    with col4:
        st.markdown("""
        ### 📅 Trip Planning
        - Daily itineraries
        - Distance management
        - Campsite planning
        """)
    
    # Instructions
    st.markdown("---")
    st.markdown("""
    ### How to Use:
    1. Enter a location or coordinates in the sidebar
    2. Set your trip duration and preferences
    3. Click 'Search Trails & Generate Plan'
    4. Explore the tabs for maps, weather, gear, and itinerary
    5. Export your plans for offline use
    
    ### Data Sources:
    - **Trails**: OpenStreetMap via Overpass API
    - **Weather**: Open-Meteo API
    - **Air Quality**: Open-Meteo Air Quality API
    - **Geocoding**: Nominatim
    """)
