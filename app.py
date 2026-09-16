import streamlit as st
import requests
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
import io

# 1. CONFIGURACIÓN DE LA INTERFAZ
st.set_page_config(page_title="Radar Comercial | Franquicias que Crecen", layout="wide")

# Mensaje oculto que solo se ve al imprimir en PDF
st.markdown("""
    <style>
        @media print {
            .css-1d391kg, .css-1lcbmhc, .stSidebar {display: none;}
            .stApp {background-color: white;}
        }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Reporte de Inteligencia Comercial")
st.markdown("**Franquicias que Crecen** - Análisis de localización y competencia.")
st.markdown("---")

diccionario_osm = {
    "Cafetería": '"amenity"="cafe"', "Restaurante": '"amenity"="restaurant"',
    "Farmacia": '"amenity"="pharmacy"', "Banco": '"amenity"="bank"',
    "Supermercado": '"shop"="supermarket"', "Gimnasio": '"leisure"="fitness_centre"',
    "Escuela/Colegio": '"amenity"="school"', "Estética/Peluquería": '"shop"="beauty"',
    "Tienda de Ropa": '"shop"="clothes"', "Fast Food": '"amenity"="fast_food"'
}

# 2. PANEL LATERAL (CONTROLES)
st.sidebar.header("📍 Parámetros de Búsqueda")
direccion = st.sidebar.text_input("Dirección:", "Av San Martin 700, Mendoza")
rubros_seleccionados = st.sidebar.multiselect("Rubros a escanear:", options=list(diccionario_osm.keys()), default=["Cafetería"])
radio_metros = st.sidebar.slider("Radio (m):", min_value=100, max_value=1500, value=600, step=100)
mostrar_solo_calor = st.sidebar.checkbox("🔥 Ocultar pines (Solo Calor)", value=False)
boton_buscar = st.sidebar.button("🔍 Generar Reporte", use_container_width=True)
st.sidebar.info("💡 **Tip para PDF:** Para exportar el mapa y las métricas, presiona Ctrl+P (o Cmd+P en Mac) y selecciona 'Guardar como PDF'.")

# 3. MOTOR DEL SISTEMA
if boton_buscar:
    if not rubros_seleccionados:
        st.warning("Selecciona al menos un rubro.")
    else:
        with st.spinner('Procesando datos espaciales...'):
            geolocalizador = Nominatim(user_agent="FranquiciasApp")
            try:
                ubicacion = geolocalizador.geocode(direccion)
                if not ubicacion:
                    st.error("❌ Dirección no encontrada.")
                    st.stop()
                latitud, longitud = ubicacion.latitude, ubicacion.longitude
            except:
                st.error("❌ Error satelital.")
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
                st.error("❌ Servidor saturado.")
                st.stop()

            # PROCESAMIENTO MATEMÁTICO
            datos_reporte = []
            distancias = []
            for comp in competidores:
                dist = geodesic((latitud, longitud), (comp['lat'], comp['lon'])).meters
                distancias.append(dist)
                tags = comp.get('tags', {})
                nombre = tags.get('name', 'Local sin nombre')
                tipo_local = "COMERCIO"
                if 'amenity' in tags: tipo_local = tags['amenity'].upper()
                elif 'shop' in tags: tipo_local = tags['shop'].upper()
                
                datos_reporte.append({
                    "Rubro": tipo_local,
                    "Nombre Comercial": nombre,
                    "Distancia Exacta (m)": round(dist, 1)
                })

            if datos_reporte:
                df_reporte = pd.DataFrame(datos_reporte).sort_values("Distancia Exacta (m)")
                df_reporte.index += 1 # Las filas empiezan en 1
                df_reporte.index.name = "Nº" # Nombre para la columna de las filas
                competidor_mas_cercano = f"{round(min(distancias))} m"
                locales_a_menos_de_200m = len([d for d in distancias if d <= 200])
            else:
                df_reporte = pd.DataFrame()
                competidor_mas_cercano = "Ninguno"
                locales_a_menos_de_200m = 0

            # RESUMEN EJECUTIVO (Diseñado para el PDF)
            st.markdown(f"### 📍 Análisis para: {direccion}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Puntos Encontrados", len(competidores))
            col2.metric("Más Cercano a", competidor_mas_cercano)
            col3.metric("Competencia Crítica (<200m)", locales_a_menos_de_200m)
            col4.metric("Radio Evaluado", f"{radio_metros} metros")

            # MAPA VISUAL
            mapa = folium.Map(location=[latitud, longitud], zoom_start=15, tiles="Cartodb Dark_Matter")
            if competidores:
                coordenadas_calor = [[c['lat'], c['lon']] for c in competidores]
                HeatMap(coordenadas_calor, radius=25, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(mapa)
            
            folium.Marker([latitud, longitud], popup="PUNTO EVALUADO", icon=folium.Icon(color="white", icon="star")).add_to(mapa)
            folium.Circle(radius=radio_metros, location=[latitud, longitud], color="white", fill=True, fill_opacity=0.05, weight=2).add_to(mapa)
            folium.Circle(radius=radio_metros*0.66, location=[latitud, longitud], color="gray", fill=False, weight=1, dash_array="5, 5").add_to(mapa)
            folium.Circle(radius=radio_metros*0.33, location=[latitud, longitud], color="gray", fill=False, weight=1, dash_array="5, 5").add_to(mapa)

            if not mostrar_solo_calor:
                for comp in competidores:
                    dist = geodesic((latitud, longitud), (comp['lat'], comp['lon'])).meters
                    tags = comp.get('tags', {})
                    nombre = tags.get('name', 'Local')
                    folium.Marker(
                        [comp['lat'], comp['lon']],
                        popup=f"<b>{nombre}</b><br>A {round(dist)}m",
                        icon=folium.Icon(color="red", icon="info-sign")
                    ).add_to(mapa)
            
            folium_static(mapa, width=1200, height=500)

            # EXPORTACIÓN Y TABLA
            if not df_reporte.empty:
                st.markdown("### 📋 Detalle de Competidores")
                
                # Creamos el archivo Excel en la memoria
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_reporte.to_excel(writer, index=True, sheet_name='Competencia')
                excel_data = output.getvalue()
                
                # Botón gigante verde para descargar Excel
                st.download_button(
                    label="📥 Descargar Base de Datos Completa (Excel)",
                    data=excel_data,
                    file_name='Reporte_Franquicias.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary"
                )
                
                # Mostramos la tabla ordenada en pantalla también
                st.dataframe(df_reporte, use_container_width=True)
