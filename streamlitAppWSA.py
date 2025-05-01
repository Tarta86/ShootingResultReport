import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(page_title="Selektionskonzept-Tool", layout="wide")

# -----------------------------------------------------------------------------
# 1) Pfad zur eingebetteten Excel-Datei ------------------------------------------------
BASE_DIR = Path(__file__).parent
DEFAULT_FILE = BASE_DIR / "data" / "data.xlsx"

# -----------------------------------------------------------------------------
# 2) Daten laden & vorbereiten ---------------------------------------------------------
@st.cache_data(show_spinner="📊 Lade eingebaute Daten …")
def load_and_prepare(filepath: Path) -> pd.DataFrame:
    if not filepath.exists():
        st.error(f"Excel-Datei nicht gefunden: {filepath}\n➜ Lege sie in das Verzeichnis `data/`. ")
        st.stop()
    df = pd.read_excel(filepath)
    df = df[df["issfID"].apply(lambda x: len(str(x)) == 16)]

    def birth_year_from_issfID(issf_id):
        try:
            dt = datetime.datetime.strptime(str(issf_id)[6:14], "%d%m%Y")
            return dt.year
        except ValueError:
            return None

    df["birth_year"] = df["issfID"].apply(birth_year_from_issfID)
    df = df.dropna(subset=["birth_year"])
    df["age"] = df["Year"] - df["birth_year"]
    df = df[df["age"] > 9]
    df["category"] = np.where(df["age"] > 21, "Elite", "Juniors")
    current_year = datetime.datetime.now().year
    df = df[df["Year"] > (current_year - 11)]
    df.loc[df["discipline"].str.contains("Center Fire", case=False), "discipline"] = "25m Center Fire Pistol Open"
    df.loc[df["discipline"].str.contains("25m Standard Pistol", case=False), "discipline"] = "25m Standard Pistol Open"
    df.loc[df["discipline"].str.contains("50m Pistol ", case=False), "discipline"] = "50m Pistol Open"
    df.loc[df["discipline"].str.contains("50m Rifle Prone ", case=False), "discipline"] = "50m Rifle Prone Open"
    return df

DATA = load_and_prepare(DEFAULT_FILE)

# -----------------------------------------------------------------------------
# 3) Score-Funktionen -----------------------------------------------------------

def quantile_score(df: pd.DataFrame, user_result: float) -> float | None:
    if df.empty:
        return None
    return (df["result"].le(user_result).sum() / len(df)) * 100


def range_score(df: pd.DataFrame, user_result: float, lower_q: float, upper_q: float) -> float | None:
    if df.empty:
        return None
    LVal = df["result"].quantile(lower_q)
    UVal = df["result"].quantile(upper_q)
    if LVal >= UVal:
        return None
    if user_result <= LVal:
        return 0
    if user_result >= UVal:
        return 100
    return 100 * (user_result - LVal) / (UVal - LVal)


def compute_quantile_scores_for_df(df: pd.DataFrame) -> list[float]:
    if df.empty:
        return []
    results = df["result"].values
    n = len(results)
    return [((results <= r).sum() / n) * 100 for r in results]

# -----------------------------------------------------------------------------
# 4) Sidebar-Steuerung -----------------------------------------------------------

st.sidebar.header("⚙️ Einstellungen")

# Disziplin
selected_disc = st.sidebar.selectbox(
    "Disziplin", sorted(DATA["discipline"].unique()), index=None, placeholder="Bitte wählen …")

# Eigenes Resultat
user_res = st.sidebar.number_input("Eigenes Resultat", min_value=0.0, step=1.0, format="%0.1f")

# Alter – **Einzelwert**
min_age, max_age = int(DATA["age"].min()), int(DATA["age"].max())
age_selected = st.sidebar.slider("Alter (Jahre)", min_value=min_age, max_value=max_age, value=min_age, step=1)

# Quantile
st.sidebar.markdown("**Unteres / Oberes Quantil (%)**")
lower_perc, upper_perc = st.sidebar.slider("Bereich", 0.0, 100.0, (50.0, 97.5))
lower_q, upper_q = lower_perc / 100, upper_perc / 100

# Kategorien
cats = st.sidebar.multiselect("Kategorien", ["Juniors", "Elite"], default=["Juniors", "Elite"])

# Y-Achse
with st.sidebar.expander("Y-Achse einstellen"):
    y_min = st.number_input("Y-Min", value=None, step=1.0, format="%0.1f", key="ymin")
    y_max = st.number_input("Y-Max", value=None, step=1.0, format="%0.1f", key="ymax")

# -----------------------------------------------------------------------------
# 5) Hauptlogik -----------------------------------------------------------------

st.title("🎯 Selektionskonzept-Tool")

if selected_disc is None:
    st.info("Bitte links eine Disziplin auswählen.")
    st.stop()

mask = (
    (DATA["discipline"] == selected_disc)
    & (DATA["category"].isin(cats))
    & (DATA["age"] == age_selected)
)

df_disc = DATA[mask].copy()

if df_disc.empty:
    st.error("Keine Daten für diese Auswahl gefunden.")
    st.stop()

q_score = quantile_score(df_disc, user_res)
r_score = range_score(df_disc, user_res, lower_q, upper_q)

col1, col2 = st.columns(2)
col1.metric("Quantile-Score", "k.A." if q_score is None else f"{q_score:.2f} Punkte")
col2.metric("Range-Score", "k.A." if r_score is None else f"{r_score:.2f} Punkte")

# -----------------------------------------------------------------------------
# 6) Plots ----------------------------------------------------------------------

fig_swarm, ax_swarm = plt.subplots(figsize=(5, 6))
ax_swarm.scatter(np.random.normal(1.0, 0.04, len(df_disc)), df_disc["result"], color="black", alpha=0.7)
LVal, UVal = df_disc["result"].quantile(lower_q), df_disc["result"].quantile(upper_q)
ax_swarm.axhline(LVal, color="blue", linestyle="--")
ax_swarm.axhline(UVal, color="blue", linestyle="--")
ax_swarm.scatter([1.0], [user_res], marker="x", color="red", s=100)
ax_swarm.set_xlim(0.8, 1.2)
ax_swarm.set_xlabel("Alle Schütz*innen")
ax_swarm.set_ylabel("Resultat")
ax_swarm.set_title("Swarm / Range Score")
if y_min is not None and y_max is not None and y_min < y_max:
    ax_swarm.set_ylim(y_min, y_max)
else:
    ymin, ymax = ax_swarm.get_ylim(); margin = 5
    ax_swarm.set_ylim(min(ymin, user_res - margin), max(ymax, user_res + margin))
st.pyplot(fig_swarm, use_container_width=True)

fig_q, ax_q = plt.subplots(figsize=(5, 6))
ax_q.scatter(compute_quantile_scores_for_df(df_disc), df_disc["result"], color="black", alpha=0.7)
ax_q.axvline(q_score, color="red", linestyle="--")
ax_q.scatter([q_score], [user_res], marker="x", color="red", s=100)
ax_q.set_xlabel("Quantil-Score (%)")
ax_q.set_ylabel("Resultat")
ax_q.set_title("Quantil / Result")
ax_q.set_xlim(-5, 105)
if y_min is not None and y_max is not None and y_min < y_max:
    ax_q.set_ylim(y_min, y_max)
else:
    ymin, ymax = ax_q.get_ylim(); margin = 5
    ax_q.set_ylim(min(ymin, user_res - margin), max(ymax, user_res + margin))
st.pyplot(fig_q, use_container_width=True)

# -----------------------------------------------------------------------------
# 7) Footer ---------------------------------------------------------------------

st.caption("© 2025 Schweizer Schiesssportverband – Streamlit-Version des Selektionskonzept-Tools – Daten integriert")
