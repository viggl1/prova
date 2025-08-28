import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
import os
import sys
import re
import unicodedata
from streamlit_javascript import st_javascript

# ---------------- CONFIGURAZIONE ----------------
st.set_page_config(page_title="Ricerca Ricambi", layout="wide")

# ---------------- UTILS ----------------
def get_path(filename: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

def _normalize_text(x: str) -> str:
    """Normalizza testo per confronti case/accent-insensitive."""
    if pd.isna(x):
        return ""
    x = str(x).strip().lower()
    x = unicodedata.normalize("NFKD", x)
    x = "".join(c for c in x if not unicodedata.combining(c))
    return x

@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Carica 'Ubicazione ricambi.xlsx' dal bundle/cartella; altrimenti DataFrame vuoto."""
    try:
        excel_path = get_path("Ubicazione ricambi.xlsx")
        if os.path.exists(excel_path):
            return pd.read_excel(excel_path)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()

def filter_contains_all_words(df: pd.DataFrame, column: str, query: str, require_all: bool) -> pd.DataFrame:
    """Filtra su 'column' usando tutte o almeno una parola della query (accent-insensitive)."""
    if not query:
        return df
    words = [_normalize_text(w) for w in query.split() if w.strip()]
    if not words:
        return df
    col_norm = f"{column}_norm"
    s = df[col_norm] if col_norm in df.columns else df[column].astype(str).map(_normalize_text)

    if require_all:
        mask = pd.Series(True, index=df.index)
        for w in words:
            mask &= s.str.contains(re.escape(w), na=False)
    else:
        pattern = "|".join(re.escape(w) for w in words)
        mask = s.str.contains(pattern, na=False)
    return df[mask]

def fuzzy_search_balanced(df: pd.DataFrame, column: str, query: str, threshold: int = 70) -> pd.DataFrame:
    """Fuzzy partial_ratio sul testo normalizzato."""
    if not query:
        return df
    qn = _normalize_text(query)
    col_norm = f"{column}_norm"
    s = df[col_norm] if col_norm in df.columns else df[column].astype(str).map(_normalize_text)
    mask = s.apply(lambda x: fuzz.partial_ratio(qn, x) >= threshold)
    return df[mask]

def evidenzia_testo_multi(testo: str, query: str) -> str:
    """Evidenzia tutte le parole della query nel testo (case-insensitive)."""
    if not query or not isinstance(testo, str):
        return str(testo)
    words = [re.escape(w) for w in query.split() if w.strip()]
    if not words:
        return testo
    pattern = re.compile(r"(" + "|".join(words) + r")", re.IGNORECASE)
    return pattern.sub(r"<mark>\1</mark>", testo)

# ---------------- CSS ----------------
st.markdown("""
    <style>
    body, .stApp { font-family: 'Segoe UI', sans-serif; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 14px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        border-left: 5px solid #007bff;
    }
    .card h4 { margin: 0 0 8px; font-size: 18px; color: #007bff; }
    .card p { margin: 4px 0; font-size: 14px; color: #333; }
    mark { background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; }
    .top-btn {
        position: fixed; bottom: 20px; right: 20px;
        background-color: #007bff; color: white;
        border-radius: 50%; width: 45px; height: 45px;
        text-align: center; font-size: 20px; cursor: pointer;
        line-height: 45px; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        z-index: 100;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------- CARICA DATI ----------------
df = load_data()

# Fallback: uploader se non trovato
if df.empty:
    up = st.file_uploader("Carica 'Ubicazione ricambi.xlsx'", type=["xlsx"])
    if up is not None:
        try:
            df = pd.read_excel(up)
        except Exception as e:
            st.error(f"Errore lettura file caricato: {e}")
            st.stop()

if df.empty:
    st.error("Nessun dato disponibile.")
    st.stop()

# Pulizia colonne
df.columns = df.columns.str.strip().str.title()

# Verifica colonne minime
required_cols = {"Codice", "Descrizione", "Ubicazione", "Categoria"}
missing = required_cols - set(df.columns)
if missing:
    st.error(f"Mancano le colonne richieste: {', '.join(sorted(missing))}")
    st.stop()

# Colonne normalizzate
for col in ["Codice", "Descrizione", "Ubicazione", "Categoria"]:
    df[f"{col}_norm"] = df[col].astype(str).map(_normalize_text)

# ---------------- SESSION STATE ----------------
defaults = {
    "codice": "",
    "descrizione": "",
    "ubicazione": "",
    "categoria": "Tutte",
    "soglia_fuzzy": 70,
    "match_all_words": True,
    "page_size": 50,
    "page_idx": 1,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

def reset_filtri():
    st.session_state.update({
        "codice": "",
        "descrizione": "",
        "ubicazione": "",
        "categoria": "Tutte",
        "page_idx": 1
    })

# ---------------- DETECT MOBILE ----------------
screen_width = st_javascript("window.innerWidth")
is_mobile = bool(screen_width is not None and screen_width < 768)

# ---------------- UI ----------------
st.title("🔍 Ricerca Ricambi in Magazzino")

sidebar_container = st.expander("📌 Filtri", expanded=not is_mobile) if is_mobile else st.sidebar
with sidebar_container:
    if is_mobile:
        st.info("📱 Modalità Mobile attiva")
    st.text_input("🔢 Codice", placeholder="Inserisci codice...", key="codice")
    st.text_input("📄 Descrizione", placeholder="Inserisci descrizione...", key="descrizione")
    st.text_input("📍 Ubicazione", placeholder="Inserisci ubicazione...", key="ubicazione")
    categorie_uniche = ["Tutte"] + sorted(df["Categoria"].dropna().unique().tolist())
    st.selectbox("🛠️ Categoria", categorie_uniche, key="categoria")

    st.divider()
    st.checkbox("Richiedi tutte le parole (più restrittivo)", key="match_all_words")
    st.slider("Soglia fuzzy", min_value=50, max_value=100, value=st.session_state.soglia_fuzzy, step=1, key="soglia_fuzzy")
    st.divider()
    st.number_input("Righe per pagina", 10, 500, value=st.session_state.page_size, step=10, key="page_size")
    st.button("🔄 Reset filtri", on_click=reset_filtri)

# ---------------- FILTRAGGIO ----------------
filtro = df

if st.session_state.codice:
    code_q = _normalize_text(st.session_state.codice)
    filtro = filtro[filtro["Codice_norm"].str.contains(re.escape(code_q), na=False)]

if st.session_state.descrizione:
    filtro = filter_contains_all_words(
        filtro, "Descrizione", st.session_state.descrizione.strip(), require_all=st.session_state.match_all_words
    )
    filtro = fuzzy_search_balanced(
        filtro, "Descrizione", st.session_state.descrizione.strip(), threshold=st.session_state.soglia_fuzzy
    )

if st.session_state.ubicazione:
    ubic_q = _normalize_text(st.session_state.ubicazione)
    filtro = filtro[filtro["Ubicazione_norm"].str.contains(re.escape(ubic_q), na=False)]

if st.session_state.categoria != "Tutte":
    cat_q = _normalize_text(st.session_state.categoria)
    filtro = filtro[filtro["Categoria_norm"] == cat_q]

# ---------------- RISULTATI + PAGINAZIONE ----------------
total = len(filtro)
st.markdown(f"### 📦 {total} risultato(i) trovati")

page_size = int(st.session_state.page_size)
max_pages = max(1, (total + page_size - 1) // page_size)
st.session_state.page_idx = max(1, min(st.session_state.page_idx, max_pages))

# ✅ Patch: nessun vertical_alignment qui
col_a, col_b, col_c = st.columns([1, 1, 2])
with col_a:
    prev = st.button("⬅️ Pagina prec.")
with col_b:
    next_ = st.button("➡️ Pagina succ.")
with col_c:
    st.number_input("Vai a pagina", min_value=1, max_value=max_pages, value=st.session_state.page_idx, key="page_idx")

if prev and st.session_state.page_idx > 1:
    st.session_state.page_idx -= 1
if next_ and st.session_state.page_idx < max_pages:
    st.session_state.page_idx += 1

start = (st.session_state.page_idx - 1) * page_size
end = start + page_size
page_df = filtro.iloc[start:end].copy()

# ---------------- DOWNLOAD ----------------
download_cols = ["Codice", "Descrizione", "Ubicazione", "Categoria"]
if total > 0:
    cols = [c for c in download_cols if c in df.columns]
    st.download_button(
        "📥 Scarica risultati filtrati (CSV)",
        page_df[cols].to_csv(index=False),
        "risultati_filtrati.csv",
        "text/csv",
    )
    st.download_button(
        "📥 Scarica tutti i risultati (CSV)",
        filtro[cols].to_csv(index=False),
        "risultati.csv",
        "text/csv",
    )

# ---------------- VISUALIZZAZIONE ----------------
if is_mobile:
    keyword = st.session_state.descrizione
    for _, row in page_df.iterrows():
        descrizione_html = evidenzia_testo_multi(str(row["Descrizione"]), keyword)
        st.markdown(f"""
            <div class="card">
                <h4>🔢 {row['Codice']}</h4>
                <p><strong>📄 Descrizione:</strong> {descrizione_html}</p>
                <p><strong>📍 Ubicazione:</strong> {row['Ubicazione']}</p>
                <p><strong>🛠️ Categoria:</strong> {row['Categoria']}</p>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="top-btn" onclick="window.scrollTo({top: 0, behavior: \'smooth\'});">⬆️</div>', unsafe_allow_html=True)
else:
    st.dataframe(page_df[download_cols], use_container_width=True, height=480)
