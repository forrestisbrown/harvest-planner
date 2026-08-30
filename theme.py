"""theme.py — warm fall palette + light/dark CSS injected into Streamlit."""
import streamlit as st

# Fall palette, grounded in harvest materials rather than generic terracotta.
LIGHT = {
    "bg": "#FBF6EE", "panel": "#F2E3CE", "ink": "#2E2018", "muted": "#7A6650",
    "russet": "#A6392E", "burnt": "#C8632B", "gold": "#D99A2B", "olive": "#6B6B2E",
    "line": "#E3D2B4",
}
DARK = {
    "bg": "#211812", "panel": "#2E231B", "ink": "#F3E7D6", "muted": "#B49B7E",
    "russet": "#E06A4E", "burnt": "#E08A4A", "gold": "#E7B85C", "olive": "#A8AC5A",
    "line": "#3D2F24",
}

def palette(dark: bool):
    return DARK if dark else LIGHT

def inject(dark: bool):
    p = palette(dark)
    st.markdown(f"""
    <style>
      :root {{
        --bg:{p['bg']}; --panel:{p['panel']}; --ink:{p['ink']}; --muted:{p['muted']};
        --russet:{p['russet']}; --burnt:{p['burnt']}; --gold:{p['gold']};
        --olive:{p['olive']}; --line:{p['line']};
      }}
      .stApp {{ background: var(--bg); color: var(--ink); }}
      section[data-testid="stSidebar"] {{ background: var(--panel); border-right:1px solid var(--line); }}
      h1,h2,h3,h4 {{ font-family: Georgia, 'Iowan Old Style', serif !important; color: var(--ink); letter-spacing:.2px; }}
      h1 {{ font-weight:700; }}
      .stApp, p, span, label, div {{ font-family: Georgia, 'Iowan Old Style', serif; }}
      /* accent bar under the title */
      .fall-rule {{ height:4px; border:0; margin:.2rem 0 1rem;
        background:linear-gradient(90deg,var(--russet),var(--burnt),var(--gold),var(--olive)); border-radius:2px; }}
      /* cards */
      .card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
        padding:14px 16px; margin-bottom:12px; }}
      .pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.72rem;
        background:var(--bg); border:1px solid var(--line); color:var(--muted); margin-right:6px; }}
      .pill.fav {{ background:var(--gold); color:#2E2018; border-color:var(--gold); }}
      .pill.cuisine {{ background:var(--burnt); color:#fff; border-color:var(--burnt); }}
      .stButton>button {{ background:var(--russet); color:#fff; border:0; border-radius:10px;
        padding:.42rem .9rem; font-family:Georgia,serif; }}
      .stButton>button:hover {{ background:var(--burnt); color:#fff; }}
      .stButton>button:focus {{ outline:2px solid var(--gold); }}
      div[data-testid="stMetric"] {{ background:var(--panel); border:1px solid var(--line);
        border-radius:12px; padding:10px 14px; }}
      .stTabs [data-baseweb="tab-list"] {{ gap:4px; }}
      .stTabs [data-baseweb="tab"] {{ background:var(--panel); border-radius:10px 10px 0 0;
        border:1px solid var(--line); border-bottom:0; color:var(--muted); }}
      .stTabs [aria-selected="true"] {{ background:var(--russet); color:#fff; }}
      .small {{ color:var(--muted); font-size:.82rem; }}
    </style>
    """, unsafe_allow_html=True)
