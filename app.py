import pandas as pd
import streamlit as st
import os, sys, re, unicodedata

# fallback per streamlit-javascript (detect mobile)
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
    return pattern.sub(r"<mark>\\1</mark>", testo)

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
    .toolbar { display:flex; gap:.5rem; justify-content:flex-end; align-items:center; }
    .muted { color:#666; font-size:12px; }
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

# Pulizia colonne + requisiti
df.columns = df.columns.str.strip().str.title()
required_cols = {"Codice", "Descrizione", "Ubicazione", "Categoria"}
missing = required_cols - set(df.columns)
if missing:
    st.error(f"Mancano le colonne richieste: {', '.join(sorted(missing))}")
    st.stop()

# Colonne normalizzate
for col in required_cols:
    df[f"{col}_norm"] = df[col].astype(str).map(_normalize_text)

# ---------------- SESSION STATE ----------------
defaults = {"codice": "", "descrizione": "", "ubicazione": "", "categoria": "Tutte"}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("filters_applied", False)  # flag per bottone Applica

def reset_filtri():
    for k, v in defaults.items():
        st.session_state[k] = v
    st.session_state["filters_applied"] = True  # forza refresh

# ---------------- DETECT MOBILE ----------------
screen_width = st_javascript("window.innerWidth")
is_mobile = bool(screen_width is not None and screen_width < 768)

# ---------------- HEADER + POP-UP FILTRI ----------------
c1, c2 = st.columns([1, 1])
with c1:
    st.title("🔍 Ricerca Ricambi in Magazzino")
with c2:
    # toolbar a destra con popover/expander
    st.markdown('<div class="toolbar"> </div>', unsafe_allow_html=True)
    # usa st.popover se esiste, altrimenti fallback a expander
    popover = getattr(st, "popover", None)
    if popover is not None:
        with st.popover("⚙️ Filtri"):
            with st.form("filters_form"):
                st.text_input("🔢 Codice", placeholder="Inserisci codice…", key="codice")
                st.text_input("📄 Descrizione", placeholder="Inserisci descrizione…", key="descrizione")
                st.text_input("📍 Ubicazione", placeholder="Inserisci ubicazione…", key="ubicazione")
                categorie_uniche = ["Tutte"] + sorted(df["Categoria"].dropna().unique().tolist())
                st.selectbox("🛠️ Categoria", categorie_uniche, key="categoria")
                colf1, colf2 = st.columns(2)
                with colf1:
                    apply_click = st.form_submit_button("✅ Applica")
                with colf2:
                    reset_click = st.form_submit_button("🔄 Reset", on_click=reset_filtri)
                if apply_click:
                    st.session_state["filters_applied"] = True
    else:
        with st.expander("⚙️ Filtri", expanded=is_mobile):
            with st.form("filters_form_fallback"):
                st.text_input("🔢 Codice", placeholder="Inserisci codice…", key="codice")
                st.text_input("📄 Descrizione", placeholder="Inserisci descrizione…", key="descrizione")
                st.text_input("📍 Ubicazione", placeholder="Inserisci ubicazione…", key="ubicazione")
                categorie_uniche = ["Tutte"] + sorted(df["Categoria"].dropna().unique().tolist())
                st.selectbox("🛠️ Categoria", categorie_uniche, key="categoria")
                colf1, colf2 = st.columns(2)
                with colf1:
                    apply_click = st.form_submit_button("✅ Applica")
                with colf2:
                    reset_click = st.form_submit_button("🔄 Reset", on_click=reset_filtri)
                if apply_click:
                    st.session_state["filters_applied"] = True

# ---------------- FILTRAGGIO (applica solo quando si preme Applica o Reset) ----------------
if st.session_state.get("filters_applied", False):
    st.session_state["filters_applied"] = False  # resetta il flag dopo l'applicazione

mask = pd.Series(True, index=df.index)

if st.session_state.codice:
    q = _normalize_text(st.session_state.codice)
    mask &= df["Codice_norm"].str.contains(q, na=False, regex=False)

if st.session_state.descrizione:
    q = _normalize_text(st.session_state.descrizione)
    mask &= df["Descrizione_norm"].str.contains(q, na=False)

if st.session_state.ubicazione:
    q = _normalize_text(st.session_state.ubicazione)
    mask &= df["Ubicazione_norm"].str.contains(q, na=False, regex=False)

if st.session_state.categoria != "Tutte":
    q = _normalize_text(st.session_state.categoria)
    mask &= df["Categoria_norm"] == q

filtro = df[mask]

# ---------------- RISULTATI ----------------
total = len(filtro)
st.markdown(f"### 📦 {total} risultato(i) trovati")

download_cols = ["Codice", "Descrizione", "Ubicazione", "Categoria"]

# download SOLO su desktop/tablet (non mobile)
if total > 0 and not is_mobile:
    st.download_button(
        "📥 Scarica risultati (CSV)",
        filtro[download_cols].to_csv(index=False),
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
                <p><span class="muted">📄 Descrizione:</span> {descrizione_html}</p>
                <p><span class="muted">📍 Ubicazione:</span> {row['Ubicazione']}</p>
                <p><span class="muted">🛠️ Categoria:</span> {row['Categoria']}</p>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="top-btn" onclick="window.scrollTo({top: 0, behavior: \'smooth\'});">⬆️</div>', unsafe_allow_html=True)
else:
    st.dataframe(filtro[download_cols], use_container_width=True, height=480)
