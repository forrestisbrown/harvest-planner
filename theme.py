"""theme.py — cool & inviting: greens, blues, greys. Single calm theme.
Sage/teal accents on a soft blue-grey canvas. Pills + centered headers.
"""
import streamlit as st

P = {
    "bg":"#EEF3F2",        # soft blue-grey canvas
    "panel":"#E0E9E8",     # muted sage-grey card
    "raise":"#E9F0EF",
    "ink":"#1F2E2C",       # deep slate-green text
    "muted":"#5F7370",     # muted grey-green
    "line":"#CBD8D5",
    "teal":"#2E7D74",      # primary accent (calm teal)
    "green":"#4A8C6F",     # sage green
    "blue":"#3E6B8C",      # dusty blue
    "slate":"#5A6B72",     # cool grey
    "ibg":"#F7FAF9", "iink":"#1F2E2C",
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
        --teal:{p['teal']}; --green:{p['green']}; --blue:{p['blue']};
        --slate:{p['slate']}; --ibg:{p['ibg']}; --iink:{p['iink']};
      }}
      .stApp {{ background: var(--bg); }}
      .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
      div[data-testid="stMarkdownContainer"] {{ color: var(--ink); font-family:{FONT}; }}
      section[data-testid="stSidebar"] {{ background: var(--panel); border-right:1px solid var(--line); }}
      section[data-testid="stSidebar"] * {{ color: var(--ink); }}
      h1,h2,h3,h4,h5 {{ color: var(--ink) !important; font-family:{FONT}; font-weight:700; letter-spacing:-.01em; }}
      h1 {{ font-weight:800; }}
      div[data-testid="stCaptionContainer"], .small {{ color: var(--muted) !important; }}

      .center {{ text-align:center; }}
      .hero-title {{ text-align:center; font-size:2.4rem; font-weight:800; margin:.2rem 0 0; color:var(--ink); }}
      .hero-sub {{ text-align:center; color:var(--muted); margin:.1rem 0 0; }}
      .fall-rule {{ height:4px; border:0; width:120px; margin:.7rem auto 1.4rem;
        background:linear-gradient(90deg,var(--teal),var(--green),var(--blue),var(--slate)); border-radius:2px; }}

      .pill {{ display:inline-block; padding:3px 12px; border-radius:999px; font-size:.74rem;
        background:var(--raise); border:1px solid var(--line); color:var(--muted); margin:2px 4px 2px 0; }}
      .pill.on {{ background:var(--teal); color:#fff; border-color:var(--teal); }}
      .pill.fav {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
      .pill.cuisine {{ background:var(--blue); color:#fff; border-color:var(--blue); }}
      .pill.veg {{ background:var(--green); color:#fff; border-color:var(--green); }}

      .card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin-bottom:14px; }}

      .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input {{
        background:var(--ibg) !important; color:var(--iink) !important; border:1px solid var(--line) !important; }}

      .stButton>button, .stDownloadButton>button {{ background:var(--teal); color:#fff !important; border:0;
        border-radius:10px; padding:.5rem 1.1rem; font-weight:600; font-family:{FONT}; width:100%; }}
      .stButton>button:hover {{ background:var(--green); color:#fff !important; }}
      .stButton>button p {{ color:#fff !important; }}
      .stButton>button:focus {{ outline:2px solid var(--blue); }}

      div[data-testid="stMetric"] {{ background:var(--raise); border:1px solid var(--line); border-radius:12px; padding:12px 16px; }}
      div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {{ color:var(--ink) !important; }}

      .stTabs [data-baseweb="tab-list"] {{ gap:6px; justify-content:center; border-bottom:1px solid var(--line); }}
      .stTabs [data-baseweb="tab"] {{ background:var(--panel); border:1px solid var(--line); border-bottom:0;
        border-radius:12px 12px 0 0; padding:6px 16px; color:var(--muted); }}
      .stTabs [data-baseweb="tab"] p {{ color:var(--muted) !important; font-weight:600; }}
      .stTabs [aria-selected="true"] {{ background:var(--teal); }}
      .stTabs [aria-selected="true"] p {{ color:#fff !important; }}

      div[role="radiogroup"] {{ gap:8px; }}
      div[role="radiogroup"] label {{ background:var(--raise); border:1px solid var(--line); border-radius:999px; padding:4px 14px; }}
      div[data-baseweb="checkbox"] div[data-checked="true"] {{ background:var(--teal) !important; border-color:var(--teal) !important; }}
      div[data-testid="stAlert"], div[role="alert"] {{ background:var(--raise) !important;
        border:1px solid var(--blue) !important; border-radius:12px !important; color:var(--ink) !important; }}
      div[data-testid="stAlert"] * {{ color:var(--ink) !important; }}
      details, .stExpander {{ background:var(--panel) !important; border:1px solid var(--line) !important; border-radius:12px; }}
      summary {{ color:var(--ink) !important; }}
      summary [data-testid="stIconMaterial"], summary span.material-icons,
      summary span.material-icons-outlined {{ display:none !important; }}
      div[data-baseweb="slider"] div[role="slider"] {{ background:var(--teal) !important; }}
      .small {{ color:var(--muted); font-size:.82rem; }}
    </style>
    """, unsafe_allow_html=True)
