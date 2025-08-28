import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
import os
import sys

# Configura la pagina Streamlit
st.set_page_config(page_title="Ricerca Ricambi", layout="wide")

def get_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

@st.cache_data
def load_data():
    try:
        excel_path = get_path("Ubicazione ricambi.xlsx")
        return pd.read_excel(excel_path)
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()

def filter_contains_all_words(df, column, query):
    words = query.lower().split()
    mask = pd.Series(True, index=df.index)
    for w in words:
        mask &= df[column].astype(str).str.lower().str.contains(w, na=False)
    return df[mask]

def fuzzy_search_balanced(df, column, query, threshold=70):
    subset = filter_contains_all_words(df, column, query)
    if not subset.empty:
        mask = subset[column].astype(str).apply(
            lambda x: fuzz.partial_ratio(query.lower(), x.lower()) >= threshold
        )
        return subset[mask]
    else:
        mask = df[column].astype(str).apply(
            lambda x: fuzz.partial_ratio(query.lower(), x.lower()) >= threshold
        )
        return df[mask]

df = load_data()
if df.empty:
    st.stop()

df.columns = df.columns.str.strip().str.title()

st.title("🔍 Ricerca Ricambi in Magazzino")

with st.sidebar:
    st.header("Filtri ricerca")
    codice_input = st.text_input("🔢 Codice", placeholder="Inserisci codice...")
    descrizione_input = st.text_input("📄 Descrizione", placeholder="Inserisci descrizione...")
    posizione_input = st.text_input("📍 Ubicazione", placeholder="Inserisci ubicazione...")

    categorie_uniche = ["Tutte"] + sorted(df["Categoria"].dropna().unique().tolist())
    macchinario_input = st.selectbox("🛠️ Categoria", categorie_uniche)

filtro = df.copy()

if codice_input:
    filtro["Codice_str"] = filtro["Codice"].astype(str).str.strip()
    filtro = filtro[filtro["Codice_str"].str.contains(codice_input.strip(), case=False, na=False)]

if descrizione_input:
    filtro = fuzzy_search_balanced(filtro, "Descrizione", descrizione_input.strip(), threshold=70)

if posizione_input:
    filtro = filtro[filtro["Ubicazione"].astype(str).str.contains(posizione_input.strip(), case=False, na=False)]

if macchinario_input != "Tutte":
    filtro = filtro[filtro["Categoria"].astype(str).str.lower() == macchinario_input.lower()]

st.markdown(f"### 📦 {len(filtro)} risultato(i) trovati")
st.dataframe(filtro, use_container_width=True)
