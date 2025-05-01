import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt

st.set_page_config(page_title="Selektionskonzept-Tool", layout="wide")

# -----------------------------------------------------------------------------
# 1) Daten laden
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="📊 Lade Excel-Datei …")
def load_and_prepare(uploaded_file: str | None) -> pd.DataFrame:
    """Lädt die Excel-Datei (File-Uploader oder Default) und bereitet sie auf."""
    if uploaded_file is None:
        st.warning("Keine Excel-Datei ausgewählt – bitte links oben eine Datei hochladen.")
        st.stop()

    df = pd.read_excel(uploaded_file)

    # -- Bereinigung (analog MATLAB) --
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

    df["category"] = "Juniors"
    df.loc[df["age"] > 21, "category"] = "Elite"

    current_year = datetime.datetime.now().year
    df = df[df["Year"] > (current_year - 11)]

    # Harmonisiere Disziplin-Namen
    df.loc[df["discipline"].str.contains("Center Fire", case=False), "discipline"] = "25m Center Fire Pistol Open"
    df.loc[df["discipline"].str.contains("25m Standard Pistol", case=False), "discipline"] = "25m Standard Pistol Open"
    df.loc[df["discipline"].str.contains("50m Pistol ", case=False), "discipline"] = "50m Pistol Open"
    df.loc[df["discipline"].str.contains("50m Rifle Prone ", case=False), "discipline"] = "50m Rifle Prone Open"

    return df

# -----------------------------------------------------------------------------
# 2) Score-Berechnungsfunktionen
# -----------------------------------------------------------------------------

def quantile_score(df: pd.DataFrame, user_result: float) -> float | None:
    """Prozentualer Anteil schlechter oder gleicher Ergebnisse (0-100)."""
    if df.empty:
        return None
    num_lower_equal = (df["result"] <= user_result).sum()
    return (num_lower_equal / len(df)) * 100


def range_score(df: pd.DataFrame, user_result: float, lower_q: float, upper_q: float) -> float | None:
    """Linear skaliert zwischen unterem und oberem Quantil (0-100)."""
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
    """Liste mit Quantil-Scores für alle Resultate im DataFrame."""
    if df.empty:
        return []
    results = df["result"].values
    n = len(results)
    return [((results <= r).sum() / n) * 100 for r in results]

# -----------------------------------------------------------------------------
# 3) Sidebar-Steuerung
# -----------------------------------------------------------------------------

st.sidebar.header("⚙️ Einstellungen")
uploaded_file = st.sidebar.file_uploader("Excel-Datei (.xlsx) hochladen", type="xlsx")

data = load_and_prepare(uploaded_file)

# Disziplin
disciplines = sorted(data["discipline"].unique())
selected_disc = st.sidebar.selectbox("Disziplin", disciplines, index=None, placeholder="Bitte wählen …")

# Eigenes Resultat
user_res = st.sidebar.number_input("Eigenes Resultat", min_value=0.0, step=1.0, format="%0.1f")

# Alter – neues Filter
min_age, max_age = int(data["age"].min()), int(data["age"].max())
age_range = st.sidebar.slider("Alter (Jahre)", min_value=min_age, max_value=max_age, value=(min_age, max_age))

# Quantile Slider
st.sidebar.markdown("**Unteres / Oberes Quantil (%)**")
lower_perc, upper_perc = st.sidebar.slider("Bereich", min_value=0.0, max_value=100.0, value=(50.0, 97.5))
lower_q = lower_perc / 100
upper_q = upper_perc / 100

# Kategorien (optional, kann bleiben)
cats = st.sidebar.multiselect("Kategorien", ["Juniors", "Elite"], default=["Juniors", "Elite"])

# Y-Achse
with st.sidebar.expander("Y-Achse einstellen"):
    y_min = st.number_input("Y-Min", value=None, step=1.0, format="%0.1f", key="ymin")
    y_max = st.number_input("Y-Max", value=None, step=1.0, format="%0.1f", key="ymax")

# -----------------------------------------------------------------------------
# 4) Hauptlogik & Ausgabe
# -----------------------------------------------------------------------------

st.title("🎯 Selektionskonzept-Tool")

if selected_disc is None:
    st.info("Bitte links eine Disziplin auswählen.")
    st.stop()

# Gefilterte Daten
mask = (
    (data["discipline"] == selected_disc)
    & (data["category"].isin(cats))
    & (data["age"].between(age_range[0], age_range[1]))
)
df_disc = data[mask].copy()

if df_disc.empty:
    st.error("Keine Daten für die gewählte Kombination gefunden.")
    st.stop()

# Score-Berechnungen
q_score = quantile_score(df_disc, user_res)
r_score = range_score(df_disc, user_res, lower_q, upper_q)

col1, col2 = st.columns(2)

with col1:
    if q_score is not None:
        st.metric("Quantile-Score", f"{q_score:.2f} Punkte")
    else:
        st.metric("Quantile-Score", "k.A.")

with col2:
    if r_score is not None:
        st.metric("Range-Score", f"{r_score:.2f} Punkte")
    else:
        st.metric("Range-Score", "k.A.")

# -----------------------------------------------------------------------------
# 5) Plots
# -----------------------------------------------------------------------------

# Plot 1 – Pseudo-Swarm
fig_swarm, ax_swarm = plt.subplots(figsize=(5, 6))

xvals = np.random.normal(loc=1.0, scale=0.04, size=len(df_disc))
ax_swarm.scatter(xvals, df_disc["result"], color="black", alpha=0.7)

# Benchmark-Linien
LVal = df_disc["result"].quantile(lower_q)
UVal = df_disc["result"].quantile(upper_q)
ax_swarm.axhline(LVal, color="blue", linestyle="--")
ax_swarm.axhline(UVal, color="blue", linestyle="--")

# Eigenes Resultat
ax_swarm.scatter([1.0], [user_res], marker="x", color="red", s=100)

ax_swarm.set_xlim(0.8, 1.2)
ax_swarm.set_xlabel("Alle Schütz*innen")
ax_swarm.set_ylabel("Resultat")
ax_swarm.set_title("Swarm / Range Score")

# Y-Achse
if y_min is not None and y_max is not None and y_min < y_max:
    ax_swarm.set_ylim(y_min, y_max)
else:
    ymin, ymax = ax_swarm.get_ylim()
    margin = 5
    ax_swarm.set_ylim(min(ymin, user_res - margin), max(ymax, user_res + margin))

st.pyplot(fig_swarm, use_container_width=True)

# Plot 2 – Quantil vs. Result
fig_q, ax_q = plt.subplots(figsize=(5, 6))

q_scores_all = compute_quantile_scores_for_df(df_disc)
ax_q.scatter(q_scores_all, df_disc["result"], color="black", alpha=0.7)

# Vertikallinie & eigenes Resultat
ax_q.axvline(q_score, color="red", linestyle="--")
ax_q.scatter([q_score], [user_res], marker="x", color="red", s=100)

ax_q.set_xlabel("Quantil-Score (%)")
ax_q.set_ylabel("Resultat")
ax_q.set_title("Quantil / Result")
ax_q.set_xlim(-5, 105)

if y_min is not None and y_max is not None and y_min < y_max:
    ax_q.set_ylim(y_min, y_max)
else:
    ymin, ymax = ax_q.get_ylim()
    margin = 5
    ax_q.set_ylim(min(ymin, user_res - margin), max(ymax, user_res + margin))

st.pyplot(fig_q, use_container_width=True)
 
# -----------------------------------------------------------------------------
# 6) Footer
# -----------------------------------------------------------------------------

st.caption("© 2025 Schweizer Schiesssportverband – Streamlit-Version des Selektionskonzept-Tools")
