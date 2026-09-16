import streamlit as st
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd

# 1. CONFIGURACIÓN DE LA INTERFAZ
st.set_page_config(page_title="Radar Comercial | Franquicias que Crecen", layout="wide")
st.title("🎯 Radar de Inteligencia Comercial V6.0")
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
radio_metros = st.sidebar.slider("Radio máximo de búsqueda (m):", min_value=100, max_value=1500, value=600, step=100)

st.sidebar.markdown("---")
mostrar_solo_calor = st.sidebar.checkbox("🔥 Ver solo Mapa de Calor", value=False)
boton_buscar = st.sidebar.button("🔍 Escanear Zona", use_container_width=True)

# 3. MOTOR DEL SISTEMA
if boton_buscar:
    if not rubros_seleccionados:
        st.warning("Por favor, selecciona al menos un rubro.")
    else:
        with st.spinner('Conectando a los satélites y descargando datos comerciales...'):
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

            # --- NUEVO: PROCESAMIENTO MATEMÁTICO DE DISTANCIAS ---
            datos_reporte = []
            distancias = []

            for comp in competidores:
                # Calculamos los metros exactos
                dist = geodesic((latitud, longitud), (comp['lat'], comp['lon'])).meters
                distancias.append(dist)
                
                tags = comp.get('tags', {})
                nombre = tags.get('name', 'Local (Sin nombre registrado)')
                tipo_local = "COMERCIO"
                if 'amenity' in tags: tipo_local = tags['amenity'].upper()
                elif 'shop' in tags: tipo_local = tags['shop'].upper()
                
                # Guardamos los datos para el archivo Excel
                datos_reporte.append({
                    "Rubro": tipo_local,
                    "Nombre": nombre,
                    "Distancia (m)": round(dist, 1),
                    "Latitud": comp['lat'],
                    "Longitud": comp['lon']
                })

            # Analizamos los resultados para mostrar en pantalla
            if datos_reporte:
                df_reporte = pd.DataFrame(datos_reporte).sort_values("Distancia (m)")
                competidor_mas_cercano = f"{round(min(distancias))} metros"
                locales_a_menos_de_200m = len([d for d in distancias if d <= 200])
            else:
                df_reporte = pd.DataFrame()
                competidor_mas_cercano = "Ninguno"
                locales_a_menos_de_200m = 0

            # --- NUEVAS MÉTRICAS VISUALES ---
            st.markdown("### 📊 Resumen Ejecutivo")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Puntos Encontrados", len(competidores))
            col2.metric("Más Cercano a", competidor_mas_cercano)
            col3.metric("Competencia Crítica (<200m)", locales_a_menos_de_200m)
            col4.metric("Ubicación Evaluada", f"{round(latitud, 4)}, {round(longitud, 4)}")

            # --- NUEVO: BOTÓN DE DESCARGA PARA EL INVERSOR ---
            if not df_reporte.empty:
                csv = df_reporte.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte de Competencia (CSV para Excel)",
                    data=csv,
                    file_name='reporte_franquicias.csv',
                    mime='text/csv',
                )

            st.markdown("---")

            # --- NUEVO MAPA CON ANILLOS ---
            mapa = folium.Map(location=[latitud, longitud], zoom_start=15, tiles="Cartodb Dark_Matter")
            
            # Capa de Calor
            if competidores:
                coordenadas_calor = [[c['lat'], c['lon']] for c in competidores]
                HeatMap(coordenadas_calor, radius=25, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(mapa)

            # Marcador de nuestro local
            folium.Marker([latitud, longitud], popup="📍 PUNTO EVALUADO", icon=folium.Icon(color="white", icon="star")).add_to(mapa)
            
            # Anillos de distancias (Borde externo, 66% y 33%)
            folium.Circle(radius=radio_metros, location=[latitud, longitud], color="white", fill=True, fill_opacity=0.05, weight=2).add_to(mapa)
            folium.Circle(radius=radio_metros*0.66, location=[latitud, longitud], color="gray", fill=False, weight=1, dash_array="5, 5").add_to(mapa)
            folium.Circle(radius=radio_metros*0.33, location=[latitud, longitud], color="gray", fill=False, weight=1, dash_array="5, 5").add_to(mapa)

            # Capa de Competidores con nueva tarjeta
            if not mostrar_solo_calor:
                for idx, row in df_reporte.iterrows():
                    tarjeta_html = f"<div style='font-family: Arial; min-width: 150px;'><h4>{row['Nombre']}</h4><span style='background-color: #eee; padding: 3px; font-size: 10px;'>Rubro: {row['Rubro']}</span><br><br><b>A {row['Distancia (m)']} metros de distancia</b></div>"
                    folium.Marker([row['Latitud'], row['Longitud']], popup=folium.Popup(tarjeta_html, max_width=300), icon=folium.Icon(color="red", icon="info-sign")).add_to(mapa)
            
            folium_static(mapa, width=1200, height=600)
