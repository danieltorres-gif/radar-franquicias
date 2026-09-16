import streamlit as st
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# 1. CONFIGURACIÓN DE LA INTERFAZ
st.set_page_config(page_title="Radar Comercial | Franquicias que Crecen", layout="wide")
st.title("🎯 Radar de Inteligencia Comercial")
st.markdown("Herramienta de análisis de localización para expansión de franquicias.")

# Diccionario interno de rubros
diccionario_osm = {
    "Cafetería": '"amenity"="cafe"',
    "Restaurante": '"amenity"="restaurant"',
    "Farmacia": '"amenity"="pharmacy"',
    "Banco": '"amenity"="bank"',
    "Supermercado": '"shop"="supermarket"',
    "Gimnasio": '"leisure"="fitness_centre"',
    "Escuela/Colegio": '"amenity"="school"',
    "Estética/Peluquería": '"shop"="beauty"',
    "Tienda de Ropa": '"shop"="clothes"',
    "Fast Food": '"amenity"="fast_food"'
}

# 2. PANEL LATERAL (CONTROLES)
st.sidebar.header("📍 Parámetros de Búsqueda")
direccion = st.sidebar.text_input("Dirección (Ej: Av San Martin 700, Mendoza):", "Av San Martin 700, Mendoza")
rubros_seleccionados = st.sidebar.multiselect(
    "Selecciona los rubros a escanear:",
    options=list(diccionario_osm.keys()),
    default=["Cafetería", "Restaurante", "Supermercado"]
)
radio_metros = st.sidebar.slider("Radio de búsqueda (metros):", min_value=100, max_value=1500, value=600, step=100)
boton_buscar = st.sidebar.button("🔍 Escanear Zona", use_container_width=True)

# 3. MOTOR DEL SISTEMA (Se activa al presionar el botón)
if boton_buscar:
    if no rubros_seleccionados:
        st.warning("Por favor, selecciona al menos un rubro.")
    else:
        with st.spinner('Conectando a los satélites y descargando datos comerciales...'):
            # Geocodificación
            geolocalizador = Nominatim(user_agent="FranquiciasApp")
            try:
                ubicacion = geolocalizador.geocode(direccion)
                if not ubicacion:
                    st.error("❌ Dirección no encontrada. Intenta agregar la ciudad y provincia.")
                    st.stop()
                latitud, longitud = ubicacion.latitude, ubicacion.longitude
            except:
                st.error("❌ Error de conexión satelital.")
                st.stop()

            # Descarga de datos
            consultas_nodos = ""
            for rubro in rubros_seleccionados:
                etiqueta = diccionario_osm[rubro]
                consultas_nodos += f'node[{etiqueta}](around:{radio_metros},{latitud},{longitud});\n'

            overpass_url = "https://overpass-api.de/api/interpreter"
            overpass_query = f"[out:json];( {consultas_nodos} );out center;"
            
            try:
                respuesta = requests.get(overpass_url, params={'data': overpass_query}, headers={'User-Agent': 'FranquiciasApp/1.0'})
                competidores = respuesta.json().get('elements', [])
            except:
                st.error("❌ Servidor de datos saturado. Intenta de nuevo en unos segundos.")
                st.stop()

            # Mostrar Métricas Rápidas
            col1, col2, col3 = st.columns(3)
            col1.metric("Puntos de Interés Encontrados", len(competidores))
            col2.metric("Radio Analizado", f"{radio_metros} metros")
            col3.metric("Ubicación", f"{round(latitud, 4)}, {round(longitud, 4)}")

            # Dibujar el Mapa
            mapa = folium.Map(location=[latitud, longitud], zoom_start=15, tiles="Cartodb Dark_Matter")
            
            # Capa de Calor
            if competidores:
                coordenadas_calor = [[c['lat'], c['lon']] for c in competidores]
                HeatMap(coordenadas_calor, radius=25, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(mapa)

            # Marcador Central
            folium.Marker([latitud, longitud], popup="📍 PUNTO EVALUADO", icon=folium.Icon(color="white", icon="star")).add_to(mapa)
            folium.Circle(radius=radio_metros, location=[latitud, longitud], color="white", fill=True, fill_opacity=0.05).add_to(mapa)

            # Pines de Competidores
            for comp in competidores:
                tags = comp.get('tags', {})
                nombre = tags.get('name', 'Local (Nombre no registrado)')
                tipo_local = "Comercio"
                if 'amenity' in tags: tipo_local = tags['amenity'].upper()
                elif 'shop' in tags: tipo_local = tags['shop'].upper()

                tarjeta_html = f"<div style='font-family: Arial; min-width: 150px;'><h4>{nombre}</h4><span style='background-color: #eee; padding: 3px; font-size: 10px;'>Rubro: {tipo_local}</span></div>"
                folium.Marker([comp['lat'], comp['lon']], popup=folium.Popup(tarjeta_html, max_width=300), icon=folium.Icon(color="red", icon="info-sign")).add_to(mapa)
            
            # Renderizar mapa en la página web
            st_folium(mapa, width=1200, height=600)
            
            st.success("✅ Análisis completado con éxito.")
