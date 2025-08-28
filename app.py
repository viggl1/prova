import pandas as pd
import numpy as np
import streamlit as st
from rapidfuzz import fuzz
import os, sys, re, unicodedata

# fallback opzionale per streamlit-javascript (mobile detect)
try:
    from streamlit_javascript import st_javascript
except Exception:
    def st_javascript(_code: str):
        return None

# ---------------- CONFIGURAZIONE ----------------
st.set_page_config(page_title="Ricerca Ricambi", layout="wide")

# ---------------- UTILS ----------------
def get_path(filename: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

def _normalize_text(x: str) -> str:
    if pd.isna(x):
        return ""
    x = str(x).strip().lower()
    x = unicodedata.normalize("NFKD", x)
    x = "".join(c for c in x if not unicodedata.combining(c))
    return x

@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    try:
        excel_path = get_path("Ubicazione ricambi.xlsx")
        if os.path.exists(excel_path):
            return pd.read_excel(excel_path)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()

def evidenzia_testo_multi(testo: str, query: str) -> str:
    if not query or not isinstance(testo, str):
        return str(testo)
    words = [re.escape(w) for w in query.split() if w.strip()]
    if not words:
        return testo
    pattern = re.compile(r"(" + "|".join(words) + r")", re.IGNORECASE)
    return pattern.sub(r"<mark>\1</mark>", testo)

def tokenize_query(q: str):
    return [w for w in _normalize_text(q).split() if w]

def apply_filters(df: pd.DataFrame, s) -> pd.DataFrame:
    """
    Filtraggio ottimizzato:
    - maschere NumPy combinate in un solo pass
    - contains con regex=False dove possibile
    - prefiltra Descrizione per parole, poi fuzzy solo su sottoinsieme (limite configurabile)
    """
    n = len(df)
    if n == 0:
        return df

    mask = np.ones(n, dtype=bool)

    # Codice
    if s.codice:
        code_q = _normalize_text(s.codice)
        mask &= df["Codice_norm"].str.contains(code_q, na=False, regex=False).to_numpy()

    # Categoria
    if s.categoria != "Tutte":
        cat_q = _normalize_text(s.categoria)
        mask &= (df["Categoria_norm"].to_numpy() == cat_q)

    # Ubicazione
    if s.ubicazione:
        ubic_q = _normalize_text(s.ubicazione)
        mask &= df["Ubicazione_norm"].str.contains(ubic_q, na=False, regex=False).to_numpy()

    # Applica maschere base
    res = df.loc[mask]

    # Descrizione: prefiltra per parole
    if s.descrizione:
        words = tokenize_query(s.descrizione)
        if words:
            if s.match_all_words:
                # tutte le parole (regex=False => più veloce)
                for w in words:
                    res = res[res["Descrizione_norm"].str.contains(w, na=False, regex=False)]
            else:
                # almeno una parola (qui usiamo regex True ma limitato a un'unica contains)
                pattern = "|".join(map(re.escape, words))
                res = res[res["Descrizione_norm"].str.contains(pattern, na=False, regex=True)]

            # Fuzzy solo se il sottoinsieme è "gestibile"
            limit = int(s.fuzzy_row_limit)
            if len(res) <= limit:
                qn = _normalize_text(s.descrizione)
                # calcolo punteggi solo sulle righe candidate
                scores = res["Descrizione_norm"].apply(lambda x: fuzz.partial_ratio(qn, x))
                res = res.loc[scores >= s.soglia_fuzzy]

    return res

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

# Colonne normalizzate (una volta sola)
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
    "auto_apply": True,          # ← nuovo
    "fuzzy_row_limit": 800,      # ← nuovo: max righe su cui applicare fuzzy
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

def reset_filtri():
    st.session_state.update({
        "codice": "",
        "descrizione": "",
        "ubicazione": "",
        "categoria": "Tutte",
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
    st.number_input("Limite righe per fuzzy", min_value=100, max_value=5000, step=100, key="fuzzy_row_limit")

    st.divider()
    st.toggle("Applica automaticamente", key="auto_apply")
    apply_now = st.button("⚡ Applica filtri adesso", disabled=st.session_state.auto_apply)
    st.button("🔄 Reset filtri", on_click=reset_filtri)

# ---------------- FILTRAGGIO (ottimizzato) ----------------
should_apply = st.session_state.auto_apply or apply_now
if should_apply:
    filtro = apply_filters(df, st.session_state)
else:
    filtro = df

# ---------------- RISULTATI ----------------
total = len(filtro)
st.markdown(f"### 📦 {total} risultato(i) trovati")

download_cols = ["Codice", "Descrizione", "Ubicazione", "Categoria"]

# download SOLO su desktop/tablet (non mobile)
if total > 0 and not is_mobile:
    cols = [c for c in download_cols if c in df.columns]
    st.download_button(
        "📥 Scarica tutti i risultati (CSV)",
        filtro[cols].to_csv(index=False),
        "risultati.csv",
        "text/csv",
    )

# ---------------- VISUALIZZAZIONE ----------------
if is_mobile:
    keyword = st.session_state.descrizione
    for _, row in filtro.iterrows():
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
    st.dataframe(filtro[download_cols], use_container_width=True, height=480)
