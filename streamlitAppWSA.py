import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="Schweizer Schiesssport‑Auswertung", layout="wide")

# -----------------------------------------------------------------------------
# 1) Pfade & konstante Grenzen --------------------------------------------------
BASE_DIR   = Path(__file__).parent
DEFAULT_XL = BASE_DIR / "data"   / "data.xlsx"
LOGO_FILE  = BASE_DIR / "assets" / "swiss_shooting_logo.png"
JUNIOR_MAX = 21  # <= 21 = Juniors
ELITE_MIN  = 22  # >= 22 = Elite

# -----------------------------------------------------------------------------
# 2) Daten laden ----------------------------------------------------------------
@st.cache_data(show_spinner="📊 Lade Daten …")
def load_data(xl_path: Path) -> pd.DataFrame:
    if not xl_path.exists():
        st.error(f"Excel nicht gefunden: {xl_path}")
        st.stop()

    df = pd.read_excel(xl_path)
    df = df[df["issfID"].astype(str).str.len() == 16]

    def birth_year_from_issfID(x):
        try:
            return datetime.datetime.strptime(str(x)[6:14], "%d%m%Y").year
        except ValueError:
            return None

    df["birth_year"] = df["issfID"].apply(birth_year_from_issfID)
    df = df.dropna(subset=["birth_year"])
    df["age"] = df["Year"] - df["birth_year"]
    df = df[df["age"] > 9]
    df["category"] = np.where(df["age"] >= ELITE_MIN, "Elite", "Juniors")

    current_year = datetime.datetime.now().year
    df = df[df["Year"] > current_year - 11]

    repl = {
        "Center Fire": "25m Center Fire Pistol Open",
        "25m Standard Pistol": "25m Standard Pistol Open",
        "50m Pistol ": "50m Pistol Open",
        "50m Rifle Prone ": "50m Rifle Prone Open",
    }
    for k, v in repl.items():
        df.loc[df["discipline"].str.contains(k, case=False), "discipline"] = v

    return df

DATA = load_data(DEFAULT_XL)

# -----------------------------------------------------------------------------
# 3) Scoring‑Functions ----------------------------------------------------------

def quantile_score(df: pd.DataFrame, res: float):
    return None if df.empty else (df["result"].le(res).sum() / len(df)) * 100

def range_score(df: pd.DataFrame, res: float, lq: float, uq: float):
    if df.empty:
        return None
    L, U = df["result"].quantile(lq), df["result"].quantile(uq)
    if L >= U:
        return None
    return np.clip(100 * (res - L) / (U - L), 0, 100)

def qscores_all(df: pd.DataFrame):
    if df.empty:
        return []
    vals = df["result"].values; n = len(vals)
    return [((vals <= v).sum() / n) * 100 for v in vals]

# -----------------------------------------------------------------------------
# 4) Sidebar – Grund­steuerung --------------------------------------------------

st.sidebar.header("⚙️ Einstellungen")

# Toggle: Selektion (ON)  vs  PISTE (OFF)
mode_selektion = st.sidebar.toggle("Selektions‑Modus", value=False, help="ON = Selektion, OFF = PISTE")

# Disziplin Wahl
selected_disc = st.sidebar.selectbox("Disziplin", sorted(DATA["discipline"].unique()), index=None, placeholder="Bitte wählen …")

# Eigenes Resultat
user_res = st.sidebar.number_input("Eigenes Resultat", min_value=0.0, step=1.0, format="%0.1f")

# Dynamische Alters‑ oder Kategorie‑Filter
if mode_selektion:
    cat_choice = st.sidebar.radio("Kategorie", ["Juniors", "Elite"], horizontal=True)
else:
    min_age, max_age = 10, int(DATA["age"].max())
    age_selected = st.sidebar.slider("Alter (Jahre)", min_age, max_age, min_age)

# Quantile Slider
st.sidebar.markdown("**Unteres / Oberes Quantil (%)**")
lower_perc, upper_perc = st.sidebar.slider("Bereich", 0.0, 100.0, (50.0, 97.5))
lq, uq = lower_perc / 100, upper_perc / 100

# Optional Y‑Achse
with st.sidebar.expander("Y‑Achse einstellen"):
    y_min = st.number_input("Y‑Min", value=None, step=1.0, format="%0.1f", key="ymin")
    y_max = st.number_input("Y‑Max", value=None, step=1.0, format="%0.1f", key="ymax")

# -----------------------------------------------------------------------------
# 5) Header + Logo --------------------------------------------------------------

tool_title = "Selektionsbewertung" if mode_selektion else "PISTE‑Bewertung"
title_col, logo_col = st.columns([0.8, 0.2])
with title_col:
    st.title(f"🎯 {tool_title}")
with logo_col:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), use_container_width=True)

# -----------------------------------------------------------------------------
# 6) Filter‑Logik --------------------------------------------------------------

if selected_disc is None:
    st.info("Bitte links eine Disziplin auswählen.")
    st.stop()

if mode_selektion:
    # Kategorie‑Switch
    if cat_choice == "Juniors":
        mask = (DATA["discipline"] == selected_disc) & (DATA["age"] <= JUNIOR_MAX)
    else:
        mask = (DATA["discipline"] == selected_disc) & (DATA["age"] >= ELITE_MIN)
else:
    # PISTE‑Logik wie bisher
    if age_selected <= JUNIOR_MAX:
        mask = (DATA["discipline"] == selected_disc) & (DATA["age"] == age_selected)
    else:
        mask = (DATA["discipline"] == selected_disc) & (DATA["age"] >= ELITE_MIN)

df_disc = DATA[mask].copy()

if df_disc.empty:
    st.error("Keine Daten für diese Auswahl gefunden.")
    st.stop()

q_score = quantile_score(df_disc, user_res)
r_score = range_score(df_disc, user_res, lq, uq)

# -----------------------------------------------------------------------------
# 7) Kennzahlen ----------------------------------------------------------------

c1, c2 = st.columns(2)
c1.metric("Quantile‑Score", "k.A." if q_score is None else f"{q_score:.2f} Punkte")
c2.metric("Range‑Score",    "k.A." if r_score is None else f"{r_score:.2f} Punkte")

# -----------------------------------------------------------------------------
# 8) Plots ---------------------------------------------------------------------

fig1, ax1 = plt.subplots(figsize=(5, 6))
ax1.scatter(np.random.normal(1.0, 0.04, len(df_disc)), df_disc["result"], color="black", alpha=0.7)
L, U = df_disc["result"].quantile(lq), df_disc["result"].quantile(uq)
ax1.axhline(L, color="blue", linestyle="--"); ax1.axhline(U, color="blue", linestyle="--")
ax1.scatter([1.0], [user_res], marker="x", color="red", s=100)
ax1.set_xlim(0.8, 1.2); ax1.set_xlabel("Alle Schütz*innen"); ax1.set_ylabel("Resultat")
ax1.set_title("Swarm / Range Score")
if y_min is not None and y_max is not None and y_min < y_max:
    ax1.set_ylim(y_min, y_max)
else:
    y0, y1 = ax1.get_ylim(); ax1.set_ylim(min(y0, user_res-5), max(y1, user_res+5))

st.pyplot(fig1, use_container_width=True)

fig2, ax2 = plt.subplots(figsize=(5, 6))
ax2.scatter(qscores_all(df_disc), df_disc["result"], color="black", alpha=0.7)
ax2.axvline(q_score, color="red", linestyle="--"); ax2.scatter([q_score], [user_res], marker="x", color="red", s=100)
ax2.set_xlabel("Quantil‑Score (%)"); ax2.set_ylabel("Resultat"); ax2.set_title("Quantil / Result")
ax2.set_xlim(-5, 105)
if y_min is not None and y_max is not None and y_min < y_max:
    ax2.set_ylim(y_min, y_max)
else:
    y0, y1 = ax2.get_ylim(); ax2.set_ylim(min(y0, user_res-5), max(y1, user_res+5))

st.pyplot(fig2, use_container_width=True)

# -----------------------------------------------------------------------------
# 9) Footer --------------------------------------------------------------------

st.caption("© 2025 Schweizer Schiesssportverband – Streamlit‑App – Daten integriert")
