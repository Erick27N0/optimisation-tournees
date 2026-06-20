import streamlit as st
import pandas as pd
import time
from geopy.geocoders import Nominatim
import openrouteservice
from openrouteservice import optimization
import folium
from streamlit_folium import st_folium
import io  # Ajouté pour générer le fichier Excel final

# --- FONCTIONS DE BASE ---

geolocator = Nominatim(user_agent="optimisation_tournees_technicien_66")

@st.cache_data
def geocoder_donnees(df):
    latitudes = []
    longitudes = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_lignes = len(df)

    for index, row in df.iterrows():
        adresse_complete = f"{row['Adresse']}, {row['Code Postal']} {row['Ville']}, France"
        status_text.text(f"Recherche GPS pour : {row['Client']}...")
        try:
            location = geolocator.geocode(adresse_complete)
            if location:
                latitudes.append(location.latitude)
                longitudes.append(location.longitude)
            else:
                latitudes.append(None)
                longitudes.append(None)
        except Exception:
            latitudes.append(None)
            longitudes.append(None)

        time.sleep(1)
        progress_bar.progress((index + 1) / total_lignes)

    df["Latitude"] = latitudes
    df["Longitude"] = longitudes
    status_text.empty()
    progress_bar.empty()
    return df

@st.cache_data
def optimiser_trajet(df, api_key):
    df_clean = df.dropna(subset=['Latitude', 'Longitude']).copy()
    if len(df_clean) < 2:
        return df_clean

    client = openrouteservice.Client(key=api_key)
    depot_lon = float(df_clean.iloc[0]['Longitude'])
    depot_lat = float(df_clean.iloc[0]['Latitude'])

    vehicles = [
        openrouteservice.optimization.Vehicle(
            id=1, profile='driving-car',
            start=[depot_lon, depot_lat], end=[depot_lon, depot_lat]
        )
    ]

    jobs = []
    for index, row in df_clean.iloc[1:].iterrows():
        jobs.append(openrouteservice.optimization.Job(
            id=int(index), location=[float(row['Longitude']), float(row['Latitude'])]
        ))

    result = client.optimization(jobs=jobs, vehicles=vehicles)
    etapes = result['routes'][0]['steps']

    ordre_index = []
    for etape in etapes:
        if etape['type'] == 'start':
            ordre_index.append(df_clean.index[0])
        elif etape['type'] == 'job':
            ordre_index.append(etape['job'])

    df_optimise = df_clean.loc[ordre_index].copy()
    df_optimise.insert(0, 'Ordre de passage', range(1, len(df_optimise) + 1))
    return df_optimise

# --- FONCTION CARTE ---
def creer_carte(df_optimise):
    start_lat = float(df_optimise.iloc[0]['Latitude'])
    start_lon = float(df_optimise.iloc[0]['Longitude'])

    m = folium.Map(location=[start_lat, start_lon], zoom_start=11)
    points_parcours = []

    for index, row in df_optimise.iterrows():
        lat, lon = float(row['Latitude']), float(row['Longitude'])
        points_parcours.append([lat, lon])

        ordre = row['Ordre de passage']
        client = row['Client']
        adresse = row['Adresse']

        # Le lien ciblé 100% sur Waze
        url_waze = f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"

        html_popup = f"""
        <div style="width:200px; font-family:sans-serif;">
            <h4 style="margin-bottom:5px;">Étape {ordre} : {client}</h4>
            <p style="margin-top:0;"><i>{adresse}</i></p>
            <hr>
            <a href="{url_waze}" target="_blank" style="display:block; padding:10px; background:#33ccff; color:white; text-align:center; border-radius:5px; text-decoration:none; font-weight:bold;">🚗 GO AVEC WAZE</a>
        </div>
        """

        couleur = 'green' if ordre == 1 else 'blue'
        icone = 'home' if ordre == 1 else 'wrench'

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(html_popup, max_width=300),
            tooltip=f"Étape {ordre} : {client}",
            icon=folium.Icon(color=couleur, icon=icone, prefix='fa')
        ).add_to(m)

    points_parcours.append([start_lat, start_lon])
    folium.PolyLine(points_parcours, color="red", weight=3, opacity=0.8).add_to(m)

    return m

# --- INTERFACE UTILISATEUR PRINCIPALE ---

st.set_page_config(layout="wide")
st.title("📍 Optimisation de Tournées - Bureau")

uploaded_file = st.file_uploader("1. Importez l'Excel de la journée (.xlsx)", type=["xlsx", "xls"])

if uploaded_file is not None:
    df_brut = pd.read_excel(uploaded_file)

    if 'df_geocode' not in st.session_state:
        st.session_state.df_geocode = None
    if 'df_final' not in st.session_state:
        st.session_state.df_final = None

    if st.button("2. Lancer la recherche GPS"):
        with st.spinner('Géocodage en cours...'):
            st.session_state.df_geocode = geocoder_donnees(df_brut)
            st.session_state.df_final = None

    if st.session_state.df_geocode is not None:

        api_key = st.text_input("3. Clé API OpenRouteService :", type="password")

        if api_key and st.button("4. Calculer la tournée idéale"):
            with st.spinner('Optimisation du trajet...'):
                try:
                    st.session_state.df_final = optimiser_trajet(st.session_state.df_geocode, api_key)
                except Exception as e:
                    st.error(f"Erreur d'optimisation : {e}")

        # SI LA TOURNÉE EST CALCULÉE
        if st.session_state.df_final is not None:
            st.success("✅ Tournée calculée avec succès !")

            carte = creer_carte(st.session_state.df_final)

            # --- NOUVEAU : ÉTAPE 5 (EXPORTS) ---
            st.write("---")
            st.subheader("Étape 5 : Exporter pour le Technicien")
            st.write("Téléchargez les fichiers ci-dessous et envoyez-les au technicien sur son smartphone (via WhatsApp, Email, etc.) :")

            col_exp1, col_exp2 = st.columns(2)

            with col_exp1:
                # Export de la carte HTML
                html_map = carte.get_root().render()
                st.download_button(
                    label="🗺️ Télécharger la Carte Magique (.html)",
                    data=html_map,
                    file_name="Tournee_Waze_Interactive.html",
                    mime="text/html"
                )
                st.caption("Fichier à ouvrir sur le navigateur du smartphone. Contient la carte et les boutons Waze.")

            with col_exp2:
                # Export de l'Excel propre
                df_export = st.session_state.df_final.copy()
                df_export['Lien Waze (Cliquez)'] = df_export.apply(
                    lambda row: f"https://waze.com/ul?ll={row['Latitude']},{row['Longitude']}&navigate=yes",
                    axis=1
                )

                # On ne garde que les colonnes utiles pour le technicien
                colonnes_a_garder = ['Ordre de passage', 'Client', 'Adresse', 'Code Postal', 'Ville', 'Lien Waze (Cliquez)']
                df_export = df_export[colonnes_a_garder]

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Tournée Optimisée')

                st.download_button(
                    label="📊 Télécharger la Feuille de Route (.xlsx)",
                    data=buffer.getvalue(),
                    file_name="Tournee_Ordre_Optimise.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.caption("Fichier Excel épuré avec l'ordre de passage et un lien Waze par ligne.")

            st.write("---")

            # Affichage visuel sur le PC du bureau
            col1, col2 = st.columns([1, 2])
            with col1:
                st.write("**Aperçu de la tournée :**")
                df_affichage = st.session_state.df_final[['Ordre de passage', 'Client', 'Ville']]
                st.dataframe(df_affichage, use_container_width=True, hide_index=True)
            with col2:
                st.write("**Aperçu de la Carte :**")
                st_folium(carte, width=800, height=500, returned_objects=[])
