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
    .muted { color:#666; font-size:12px; }

    .toolbar { display:flex; gap:.5rem; justify-content:flex-end; align-items:center; }
    .chips { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.5rem; }
    .chip {
        display:inline-flex; align-items:center; gap:.35rem;
        padding:.2rem .5rem; border-radius:999px; background:#f1f3f5; font-size:12px; color:#333;
        border:1px solid #e5e7eb;
    }
    .stPopover, [data-testid="stPopover"] { max-width: 520px !important; }
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

# Evita "nan" in output: rimpiazza NaN con stringa vuota PRIMA della normalizzazione
df = df.fillna("")

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
st.session_state.setdefault("filters_applied", True)  # applica al primo render

def reset_filtri():
    for k, v in defaults.items():
        st.session_state[k] = v
    st.session_state["filters_applied"] = True

def _active_filters_count() -> int:
    cnt = 0
    if st.session_state.codice.strip(): cnt += 1
    if st.session_state.descrizione.strip(): cnt += 1
    if st.session_state.ubicazione.strip(): cnt += 1
    if st.session_state.categoria != "Tutte": cnt += 1
    return cnt

def _active_filters_chips():
    chips = []
    if st.session_state.codice.strip():
        chips.append(("Codice", st.session_state.codice.strip()))
    if st.session_state.descrizione.strip():
        chips.append(("Descrizione", st.session_state.descrizione.strip()))
    if st.session_state.ubicazione.strip():
        chips.append(("Ubicazione", st.session_state.ubicazione.strip()))
    if st.session_state.categoria != "Tutte":
        chips.append(("Categoria", st.session_state.categoria))
    return chips

# ---------------- DETECT MOBILE ----------------
screen_width = st_javascript("window.innerWidth")
is_mobile = bool(screen_width is not None and screen_width < 768)

# ---------------- HEADER + POP-UP FILTRI (Descrizione prima di Ubicazione) ----------------
left, right = st.columns([3, 1])
with left:
    st.title("🔍 Ricerca Ricambi in Magazzino")

with right:
    active_n = _active_filters_count()
    label = "🔽 Filtri" + (f" · {active_n}" if active_n else "")
    popover = getattr(st, "popover", None)

    if popover is not None:
        with st.popover(label):
            with st.form("filters_form", clear_on_submit=False):
                a1, a2 = st.columns([1,1])
                apply_click = a1.form_submit_button("✅ Applica", use_container_width=True)
                reset_click = a2.form_submit_button("🔄 Reset", use_container_width=True, on_click=reset_filtri)
                st.write("")

                # Descrizione prima di Ubicazione
                col_l, col_r = st.columns(2)
                with col_l:
                    st.text_input("🔢 Codice", placeholder="Es. CG055919", key="codice")
                    st.text_input("📄 Descrizione", placeholder="Es. Cuscinetto", key="descrizione")
                with col_r:
                    st.text_input("📍 Ubicazione", placeholder="Es. 0 C 001 02 - C2", key="ubicazione")
                    categorie_uniche = ["Tutte"] + sorted(df["Categoria"].dropna().unique().tolist())
                    st.selectbox("🛠️ Categoria", categorie_uniche, key="categoria")

                st.caption("Suggerimento: premi **Invio** per applicare i filtri mentre scrivi.")
                if apply_click:
                    st.session_state["filters_applied"] = True
    else:
        with st.expander(label, expanded=is_mobile):
            with st.form("filters_form_fallback", clear_on_submit=False):
                a1, a2 = st.columns([1,1])
                apply_click = a1.form_submit_button("✅ Applica", use_container_width=True)
                reset_click = a2.form_submit_button("🔄 Reset", use_container_width=True, on_click=reset_filtri)

                col_l, col_r = st.columns(2)
                with col_l:
                    st.text_input("🔢 Codice", placeholder="Es. CG238258", key="codice")
                    st.text_input("📄 Descrizione", placeholder="Es. Boccola", key="descrizione")
                with col_r:
                    st.text_input("📍 Ubicazione", placeholder="Es. 0 B 001 03 - B2", key="ubicazione")
                    categorie_uniche = ["Tutte"] + sorted(df["Categoria"].dropna().unique().tolist())
                    st.selectbox("🛠️ Categoria", categorie_uniche, key="categoria")

                st.caption("Suggerimento: premi **Invio** per applicare i filtri mentre scrivi.")
                if apply_click:
                    st.session_state["filters_applied"] = True

# Chips dei filtri attivi
chips = _active_filters_chips()
if chips:
    chip_html = "".join([f'<span class="chip">{name}: {val}</span>' for name, val in chips])
    st.markdown(f'<div class="chips">{chip_html}</div>', unsafe_allow_html=True)

# ---------------- FILTRAGGIO ----------------
if st.session_state.get("filters_applied", False):
    st.session_state["filters_applied"] = False  # consume flag

mask = pd.Series(True, index=df.index)

if st.session_state.codice:
    q = _normalize_text(st.session_state.codice)
    mask &= df["Codice_norm"].str.contains(q, na=False, regex=False)

if st.session_state.descrizione:
    q = _normalize_text(st.session_state.descrizione)
    mask &= df["Descrizione_norm"].str.contains(q, na=False, regex=False)

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
cols_out = [c for c in download_cols if c in filtro.columns]

# download SOLO su desktop/tablet (non mobile)
if total > 0 and not is_mobile and cols_out:
    st.download_button(
        "📥 Scarica risultati (CSV)",
        filtro[cols_out].to_csv(index=False),
        "risultati.csv",
        "text/csv",
    )

# ---------------- VISUALIZZAZIONE ----------------
if is_mobile:
    for _, row in filtro.iterrows():
        code_view = "—" if str(row["Codice"]).strip() == "" else row["Codice"]
        desc_view = "—" if str(row["Descrizione"]).strip() == "" else row["Descrizione"]
        ubic_view = "—" if str(row["Ubicazione"]).strip() == "" else row["Ubicazione"]
        cat_view  = "—" if str(row["Categoria"]).strip() == "" else row["Categoria"]

        st.markdown(f"""
            <div class="card">
                <h4>🔢 {code_view}</h4>
                <p><span class="muted">📄 Descrizione:</span> {desc_view}</p>
                <p><span class="muted">📍 Ubicazione:</span> {ubic_view}</p>
                <p><span class="muted">🛠️ Categoria:</span> {cat_view}</p>
            </div>
        """, unsafe_allow_html=True)
else:
    display_df = filtro.copy()
    for col in ["Codice", "Descrizione", "Ubicazione", "Categoria"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda v: "—" if str(v).strip() == "" else v)
    st.dataframe(display_df[cols_out], use_container_width=True, height=480)
