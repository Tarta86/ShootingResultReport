import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="Selektionskonzept-Tool", layout="wide")

# -----------------------------------------------------------------------------
# 1) Pfade ---------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DEFAULT_FILE = BASE_DIR / "data" / "data.xlsx"
LOGO_FILE   = BASE_DIR / "assets" / "swiss_shooting_logo.png"  # <--- Logo hier ablegen

# -----------------------------------------------------------------------------
# 2) Daten laden ---------------------------------------------------------------
@st.cache_data(show_spinner="📊 Lade Daten …")
def load_and_prepare(filepath: Path) -> pd.DataFrame:
    if not filepath.exists():
        st.error(f"Excel-Datei nicht gefunden: {filepath}\n➜ Lege sie in `data/data.xlsx`. ")
        st.stop()
    df = pd.read_excel(filepath)
    df = df[df["issfID"].astype(str).str.len() == 16]
    def birth_year_from_issfID(issf_id):
        try:
            return datetime.datetime.strptime(str(issf_id)[6:14], "%d%m%Y").year
        except ValueError:
            return None
    df["birth_year"] = df["issfID"].apply(birth_year_from_issfID)
    df = df.dropna(subset=["birth_year"])
    df["age"] = df["Year"] - df["birth_year"]
    df = df[df["age"] > 9]
    df["category"] = np.where(df["age"] > 21, "Elite", "Juniors")
    current_year = datetime.datetime.now().year
    df = df[df["Year"] > current_year - 11]
    repl = {"Center Fire": "25m Center Fire Pistol Open",
            "25m Standard Pistol": "25m Standard Pistol Open",
            "50m Pistol ": "50m Pistol Open",
            "50m Rifle Prone ": "50m Rifle Prone Open"}
    for k, v in repl.items():
        df.loc[df["discipline"].str.contains(k, case=False), "discipline"] = v
    return df

DATA = load_and_prepare(DEFAULT_FILE)

# -----------------------------------------------------------------------------
# 3) Scoring-Funktionen ---------------------------------------------------------

def quantile_score(df: pd.DataFrame, user_result: float):
    return None if df.empty else (df["result"].le(user_result).sum() / len(df)) * 100

def range_score(df: pd.DataFrame, user_result: float, lq: float, uq: float):
    if df.empty:
        return None
    L, U = df["result"].quantile(lq), df["result"].quantile(uq)
    if L >= U:
        return None
    return np.clip(100 * (user_result - L) / (U - L), 0, 100)

def all_qscores(df: pd.DataFrame):
    if df.empty:
        return []
    res = df["result"].values; n = len(res)
    return [((res <= r).sum() / n) * 100 for r in res]

# -----------------------------------------------------------------------------
# 4) Sidebar -------------------------------------------------------------------

st.sidebar.header("⚙️ Einstellungen")
selected_disc = st.sidebar.selectbox("Disziplin", sorted(DATA["discipline"].unique()), index=None, placeholder="Bitte wählen …")
user_res = st.sidebar.number_input("Eigenes Resultat", min_value=0.0, step=1.0, format="%0.1f")
min_age, max_age = int(DATA["age"].min()), int(DATA["age"].max())
age_selected = st.sidebar.slider("Alter (Jahre)", min_value=min_age, max_value=max_age, value=min_age, step=1)

st.sidebar.markdown("**Unteres / Oberes Quantil (%)**")
lower_perc, upper_perc = st.sidebar.slider("Bereich", 0.0, 100.0, (50.0, 97.5))
lq, uq = lower_perc/100, upper_perc/100

with st.sidebar.expander("Y-Achse einstellen"):
    y_min = st.number_input("Y-Min", value=None, step=1.0, format="%0.1f", key="ymin")
    y_max = st.number_input("Y-Max", value=None, step=1.0, format="%0.1f", key="ymax")

# -----------------------------------------------------------------------------
# 5) Header mit Logo ------------------------------------------------------------

title_col, logo_col = st.columns([0.8, 0.2])
with title_col:
    st.title("🎯 Selektionskonzept-Tool")
with logo_col:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), use_column_width="auto")
    else:
        st.markdown("<small>Logo fehlt (assets/swiss_shooting_logo.png)</small>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6) Daten‑Filter --------------------------------------------------------------

if selected_disc is None:
    st.info("Bitte links eine Disziplin auswählen.")
    st.stop()

mask = (DATA["discipline"] == selected_disc) & (DATA["age"] == age_selected)
df_disc = DATA[mask].copy()
if df_disc.empty:
    st.error("Keine Daten für diese Auswahl gefunden.")
    st.stop()

q_score = quantile_score(df_disc, user_res)
r_score = range_score(df_disc, user_res, lq, uq)

col1, col2 = st.columns(2)
col1.metric("Quantile-Score", "k.A." if q_score is None else f"{q_score:.2f} Punkte")
col2.metric("Range-Score", "k.A." if r_score is None else f"{r_score:.2f} Punkte")

# -----------------------------------------------------------------------------
# 7) Plots ---------------------------------------------------------------------

fig1, ax1 = plt.subplots(figsize=(5, 6))
ax1.scatter(np.random.normal(1.0, 0.04, len(df_disc)), df_disc["result"], color="black", alpha=0.7)
L, U = df_disc["result"].quantile(lq), df_disc["result"].quantile(uq)
ax1.axhline(L, color="blue", linestyle="--"); ax1.axhline(U, color="blue", linestyle="--")
ax1.scatter([1.0], [user_res], marker="x", color="red", s=100)
ax1.set_xlim(0.8, 1.2)
ax1.set_xlabel("Alle Schütz*innen"); ax1.set_ylabel("Resultat"); ax1.set_title("Swarm / Range Score")
if y_min is not None and y_max is not None and y_min < y_max:
    ax1.set_ylim(y_min, y_max)
else:
    y0, y1 = ax1.get_ylim(); ax1.set_ylim(min(y0, user_res-5), max(y1, user_res+5))
st.pyplot(fig1, use_container_width=True)

fig2, ax2 = plt.subplots(figsize=(5, 6))
ax2.scatter(all_qscores(df_disc), df_disc["result"], color="black", alpha=0.7)
ax2.axvline(q_score, color="red", linestyle="--"); ax2.scatter([q_score], [user_res], marker="x", color="red", s=100)
ax2.set_xlabel("Quantil-Score (%)"); ax2.set_ylabel("Resultat"); ax2.set_title("Quantil / Result")
ax2.set_xlim(-5, 105)
if y_min is not None and y_max is not None and y_min < y_max:
    ax2.set_ylim(y_min, y_max)
else:
    y0, y1 = ax2.get_ylim(); ax2.set_ylim(min(y0, user_res-5), max(y1, user_res+5))
st.pyplot(fig2, use_container_width=True)

# -----------------------------------------------------------------------------
# 8) Footer --------------------------------------------------------------------

st.caption("© 2025 Schweizer Schiesssportverband – Streamlit-Version des Selektionskonzept-Tools – Daten integriert")
