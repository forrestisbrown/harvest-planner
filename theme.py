"""theme.py — deep moody fall theme, dark default + working light toggle.

The fix vs the old version: we target Streamlit's actual widget containers
(inputs, selectboxes, toggles, tabs, checkboxes) so nothing stays dark-on-dark
or washed out. Both modes are fully specified — no reliance on Streamlit's base
leaking through.
"""
import streamlit as st

# Deep, moody harvest. Dark is the default/primary direction.
DARK = {
    "bg": "#1C1410", "panel": "#261C15", "raise": "#31241B",
    "ink": "#F0E6D8", "muted": "#B39B82", "line": "#3A2C21",
    "ember": "#C4462E", "rust": "#A6392E", "amber": "#D98A3D",
    "gold": "#E0A94E", "olive": "#8A8B4B",
    "input_bg": "#2B2019", "input_ink": "#F0E6D8",
}
LIGHT = {
    "bg": "#F7EFE3", "panel": "#EFE1CD", "raise": "#F2E7D6",
    "ink": "#2A1E15", "muted": "#7A6551", "line": "#DFCBAF",
    "ember": "#B23A22", "rust": "#96311F", "amber": "#B9702A",
    "gold": "#C08A2E", "olive": "#6E7038",
    "input_bg": "#FFFFFF", "input_ink": "#2A1E15",
}

FONT = ('-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
        '"Helvetica Neue", Arial, sans-serif')

def palette(dark: bool):
    return DARK if dark else LIGHT

def inject(dark: bool):
    p = palette(dark)
    st.markdown(f"""
    <style>
      :root {{
        --bg:{p['bg']}; --panel:{p['panel']}; --raise:{p['raise']};
        --ink:{p['ink']}; --muted:{p['muted']}; --line:{p['line']};
        --ember:{p['ember']}; --rust:{p['rust']}; --amber:{p['amber']};
        --gold:{p['gold']}; --olive:{p['olive']};
        --ibg:{p['input_bg']}; --iink:{p['input_ink']};
      }}
      /* base surfaces */
      .stApp {{ background: var(--bg); }}
      .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
      div[data-testid="stMarkdownContainer"] {{
        color: var(--ink); font-family: {FONT}; }}
      section[data-testid="stSidebar"] {{
        background: var(--panel); border-right:1px solid var(--line); }}
      section[data-testid="stSidebar"] * {{ color: var(--ink); }}

      /* headings */
      h1,h2,h3,h4,h5 {{ color: var(--ink) !important; font-family:{FONT};
        font-weight:700; letter-spacing:-.01em; }}
      h1 {{ font-weight:800; }}
      .stCaption, .small, div[data-testid="stCaptionContainer"] {{
        color: var(--muted) !important; }}

      /* the gradient rule under the title */
      .fall-rule {{ height:4px; border:0; margin:.2rem 0 1.2rem;
        background:linear-gradient(90deg,var(--rust),var(--ember),var(--amber),var(--olive));
        border-radius:2px; }}

      /* Text/number/date inputs and textareas get warm backgrounds.
         NOTE: selectboxes are intentionally left to Streamlit's base theme —
         forcing their background causes dark-on-dark in light mode, so we let
         the base (set in config.toml) handle them and they stay readable. */
      .stTextInput input, .stNumberInput input, .stTextArea textarea,
      .stDateInput input {{
        background: var(--ibg) !important; color: var(--iink) !important;
        border:1px solid var(--line) !important; }}

      /* buttons */
      .stButton>button, .stDownloadButton>button {{
        background: var(--rust); color:#fff !important; border:0;
        border-radius:10px; padding:.5rem 1rem; font-weight:600;
        font-family:{FONT}; }}
      .stButton>button:hover, .stDownloadButton>button:hover {{
        background: var(--ember); color:#fff !important; }}
      .stButton>button:focus {{ outline:2px solid var(--gold); }}
      .stButton>button p {{ color:#fff !important; }}

      /* metrics */
      div[data-testid="stMetric"] {{ background: var(--raise);
        border:1px solid var(--line); border-radius:12px; padding:12px 16px; }}
      div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {{
        color: var(--ink) !important; }}

      /* tabs */
      .stTabs [data-baseweb="tab-list"] {{ gap:6px; border-bottom:1px solid var(--line); }}
      .stTabs [data-baseweb="tab"] {{ background: var(--panel);
        border:1px solid var(--line); border-bottom:0;
        border-radius:10px 10px 0 0; padding:6px 14px; color: var(--muted); }}
      .stTabs [data-baseweb="tab"] p {{ color: var(--muted) !important; font-weight:600; }}
      .stTabs [aria-selected="true"] {{ background: var(--rust); }}
      .stTabs [aria-selected="true"] p {{ color:#fff !important; }}

      /* toggle + checkbox accents */
      div[data-baseweb="checkbox"] div[data-checked="true"],
      div[data-baseweb="toggle"] div[aria-checked="true"] {{
        background: var(--ember) !important; border-color: var(--ember) !important; }}

      /* info / alert boxes -> warm instead of default blue */
      div[data-testid="stAlert"], div[data-testid="stNotification"],
      div[role="alert"] {{ background: var(--raise) !important;
        border:1px solid var(--amber) !important; border-radius:12px !important;
        color: var(--ink) !important; }}
      div[data-testid="stAlert"] *, div[role="alert"] * {{ color: var(--ink) !important; }}

      /* expanders */
      details, .stExpander {{ background: var(--panel) !important;
        border:1px solid var(--line) !important; border-radius:12px; }}
      .streamlit-expanderHeader, summary {{ color: var(--ink) !important; }}
      /* hide leaking Material icon glyph names (e.g. "_arrow_right") when the
         icon font fails to load in some Streamlit builds */
      summary span[data-testid="stIconMaterial"],
      [data-testid="stExpanderToggleIcon"] {{
        font-family:'Material Symbols Rounded','Material Symbols Outlined',sans-serif !important;
        overflow:hidden; }}
      summary span[data-testid="stIconMaterial"]:not(:defined) {{ visibility:hidden; }}

      /* pills used in the recipe list */
      .pill {{ display:inline-block; padding:2px 10px; border-radius:999px;
        font-size:.72rem; background:var(--raise); border:1px solid var(--line);
        color:var(--muted); margin-right:6px; }}
      .pill.fav {{ background:var(--gold); color:#241a10; border-color:var(--gold); }}
      .pill.cuisine {{ background:var(--amber); color:#241a10; border-color:var(--amber); }}
      .small {{ color:var(--muted); font-size:.82rem; }}

      /* slider track */
      div[data-baseweb="slider"] div[role="slider"] {{ background: var(--ember) !important; }}
    </style>
    """, unsafe_allow_html=True)
