import streamlit as st
import pandas as pd

# Titre de l'application
st.title("Optimisation de Tournées - Technicien")
st.write("Bienvenue ! Veuillez importer votre fichier Excel contenant la liste des clients de la journée.")

# Composant pour charger le fichier (limité aux formats Excel)
uploaded_file = st.file_uploader("Choisissez un fichier Excel (.xlsx ou .xls)", type=["xlsx", "xls"])

# Vérifie si un fichier a bien été chargé
if uploaded_file is not None:
    try:
        # Lecture du fichier Excel avec Pandas
        df = pd.read_excel(uploaded_file)
        
        # Message de succès
        st.success("Fichier chargé avec succès ! Voici un aperçu des données :")
        
        # Affichage du contenu du fichier sous forme de tableau interactif
        st.dataframe(df)
        
    except Exception as e:
        # Affichage d'une erreur si le fichier est corrompu ou illisible
        st.error(f"Une erreur s'est produite lors de la lecture du fichier : {e}")