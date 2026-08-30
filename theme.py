"""theme.py — v3 single warm theme (no light/dark toggle).
Aged-paper warmth: soft, muted, easy on the eyes. Pills + centered headers.
"""
import streamlit as st

P = {
    "bg":"#F3E9D8",        # aged paper
    "panel":"#EBDCC4",     # slightly deeper card
    "raise":"#F0E4CF",
    "ink":"#3A2A1E",       # warm dark brown text
    "muted":"#8A745C",
    "line":"#DBC8A9",
    "rust":"#A85A3C",      # primary accent (muted clay/rust)
    "ember":"#BE6B45",
    "olive":"#7E7A45",
    "gold":"#C79A4B",
    "ibg":"#FBF4E7", "iink":"#3A2A1E",
}
FONT = ('-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
        '"Helvetica Neue", Arial, sans-serif')

def inject():
    p=P
    st.markdown(f"""
    <style>
      :root {{
        --bg:{p['bg']}; --panel:{p['panel']}; --raise:{p['raise']};
        --ink:{p['ink']}; --muted:{p['muted']}; --line:{p['line']};
        --rust:{p['rust']}; --ember:{p['ember']}; --olive:{p['olive']};
        --gold:{p['gold']}; --ibg:{p['ibg']}; --iink:{p['iink']};
      }}
      .stApp {{ background: var(--bg); }}
      .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
      div[data-testid="stMarkdownContainer"] {{ color: var(--ink); font-family:{FONT}; }}
      section[data-testid="stSidebar"] {{ background: var(--panel); border-right:1px solid var(--line); }}
      section[data-testid="stSidebar"] * {{ color: var(--ink); }}
      h1,h2,h3,h4,h5 {{ color: var(--ink) !important; font-family:{FONT}; font-weight:700; letter-spacing:-.01em; }}
      h1 {{ font-weight:800; }}
      div[data-testid="stCaptionContainer"], .small {{ color: var(--muted) !important; }}

      /* centered header block */
      .center {{ text-align:center; }}
      .hero-title {{ text-align:center; font-size:2.4rem; font-weight:800; margin:.2rem 0 0; color:var(--ink); }}
      .hero-sub {{ text-align:center; color:var(--muted); margin:.1rem 0 0; }}
      .fall-rule {{ height:4px; border:0; width:120px; margin:.7rem auto 1.4rem;
        background:linear-gradient(90deg,var(--rust),var(--ember),var(--gold),var(--olive)); border-radius:2px; }}

      /* pills */
      .pill {{ display:inline-block; padding:3px 12px; border-radius:999px; font-size:.74rem;
        background:var(--raise); border:1px solid var(--line); color:var(--muted); margin:2px 4px 2px 0; }}
      .pill.on {{ background:var(--rust); color:#fff; border-color:var(--rust); }}
      .pill.fav {{ background:var(--gold); color:#2c2110; border-color:var(--gold); }}
      .pill.cuisine {{ background:var(--ember); color:#fff; border-color:var(--ember); }}
      .pill.veg {{ background:var(--olive); color:#fff; border-color:var(--olive); }}

      /* cards */
      .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin-bottom:14px; }}

      /* inputs (no dark mode to fight now) */
      .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input {{
        background:var(--ibg) !important; color:var(--iink) !important; border:1px solid var(--line) !important; }}

      /* buttons */
      .stButton>button, .stDownloadButton>button {{ background:var(--rust); color:#fff !important; border:0;
        border-radius:10px; padding:.5rem 1.1rem; font-weight:600; font-family:{FONT}; width:100%; }}
      .stButton>button:hover {{ background:var(--ember); color:#fff !important; }}
      .stButton>button p {{ color:#fff !important; }}
      .stButton>button:focus {{ outline:2px solid var(--gold); }}

      /* metrics */
      div[data-testid="stMetric"] {{ background:var(--raise); border:1px solid var(--line); border-radius:12px; padding:12px 16px; }}
      div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {{ color:var(--ink) !important; }}

      /* tabs — centered, pill-like */
      .stTabs [data-baseweb="tab-list"] {{ gap:6px; justify-content:center; border-bottom:1px solid var(--line); }}
      .stTabs [data-baseweb="tab"] {{ background:var(--panel); border:1px solid var(--line); border-bottom:0;
        border-radius:12px 12px 0 0; padding:6px 16px; color:var(--muted); }}
      .stTabs [data-baseweb="tab"] p {{ color:var(--muted) !important; font-weight:600; }}
      .stTabs [aria-selected="true"] {{ background:var(--rust); }}
      .stTabs [aria-selected="true"] p {{ color:#fff !important; }}

      /* radio as segmented pills */
      div[role="radiogroup"] {{ gap:8px; }}
      div[role="radiogroup"] label {{ background:var(--raise); border:1px solid var(--line);
        border-radius:999px; padding:4px 14px; }}

      div[data-baseweb="checkbox"] div[data-checked="true"] {{ background:var(--rust) !important; border-color:var(--rust) !important; }}
      div[data-testid="stAlert"], div[role="alert"] {{ background:var(--raise) !important;
        border:1px solid var(--gold) !important; border-radius:12px !important; color:var(--ink) !important; }}
      div[data-testid="stAlert"] * {{ color:var(--ink) !important; }}
      details, .stExpander {{ background:var(--panel) !important; border:1px solid var(--line) !important; border-radius:12px; }}
      summary {{ color:var(--ink) !important; }}
      /* Hide the collapse-arrow icon glyph that some Streamlit builds render as
         literal text ("keyboard_arrow_right"). Target the icon span inside the
         summary; the real label is a sibling and stays visible. */
      summary [data-testid="stIconMaterial"],
      summary span.material-icons,
      summary span.material-icons-outlined,
      details summary svg + span:first-child:empty {{ display:none !important; }}
      summary [data-testid="stExpanderIcon"] {{ font-size:0 !important; }}
      div[data-baseweb="slider"] div[role="slider"] {{ background:var(--rust) !important; }}
      .small {{ color:var(--muted); font-size:.82rem; }}
    </style>
    """, unsafe_allow_html=True)
