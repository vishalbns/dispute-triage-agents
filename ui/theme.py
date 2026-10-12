"""Shared look for both portals.

Deliberately a fictional institution. This is a demo on public code, so it must not
carry any real company's name or marks.
"""
import streamlit as st

BRAND = "Harborline Credit Union"
INK = "#16202A"
PRIMARY = "#1F7A63"
MUTED = "#5E6974"
LINE = "#E2E4DF"

STATUS = {
    "submitted":         ("Received", "#5E6974", "#EEF0ED"),
    "processing":        ("In review", "#8A5A12", "#F8EFDD"),
    "awaiting_approval": ("Awaiting reviewer", "#1F5F86", "#E3EFF7"),
    "approved":          ("Approved", "#1F7A63", "#E2F0EB"),
    "denied":            ("Declined", "#9B2C2C", "#F7E7E6"),
}

LOGO = """<svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
  <rect width="32" height="32" rx="8" fill="#1F7A63"/>
  <path d="M8 21.5c2.4 0 2.4-3 4.8-3s2.4 3 4.8 3 2.4-3 4.8-3 2.4 3 4.8 3" stroke="#fff"
        stroke-width="1.8" stroke-linecap="round" fill="none"/>
  <path d="M11 14.5V9.5h3.5v5M17.5 14.5v-7H21v7" stroke="#fff" stroke-width="1.8"
        stroke-linecap="round" fill="none"/>
</svg>"""

CSS = f"""
<style>
  /* Streamlit's own toolbar is fixed at the top. Clear it, and let the page show
     through it, rather than sliding our header underneath. */
  header[data-testid="stHeader"] {{ background: transparent; height: 3rem; }}
  .block-container {{ padding-top: 4.2rem; max-width: 1180px; }}
  #MainMenu, footer {{ visibility: hidden; }}

  .hdr {{ display:flex; align-items:center; gap:12px; padding:0 0 14px;
          border-bottom:1px solid {LINE}; margin-bottom:6px; }}
  .hdr .mark {{ display:flex; align-items:center; gap:10px; }}
  .hdr .brand {{ font-size:17px; font-weight:700; color:{INK}; letter-spacing:-.01em; line-height:1.1; }}
  .hdr .portal {{ font-size:12px; color:{MUTED}; letter-spacing:.09em; text-transform:uppercase; }}
  .hdr .spacer {{ flex:1; }}
  .chip {{ font-size:11px; font-weight:700; letter-spacing:.09em; text-transform:uppercase;
           padding:4px 10px; border-radius:999px; background:#F8EFDD; color:#8A5A12;
           border:1px solid #E8D5AE; white-space:nowrap; }}

  .demo {{ font-size:12.5px; color:{MUTED}; background:#F1F2EE; border:1px solid {LINE};
           border-radius:8px; padding:9px 12px; margin:10px 0 20px; line-height:1.45; }}
  .demo b {{ color:{INK}; }}

  .pill {{ display:inline-block; font-size:11.5px; font-weight:700; padding:3px 10px;
           border-radius:999px; letter-spacing:.02em; }}

  h2, h3 {{ letter-spacing:-.01em; }}
  .sect {{ font-size:11px; font-weight:700; letter-spacing:.11em; text-transform:uppercase;
           color:{MUTED}; margin:18px 0 6px; }}
  .meta {{ color:{MUTED}; font-size:13.5px; }}

  div[data-testid="stExpander"] details {{ border:1px solid {LINE}; border-radius:8px;
                                           background:#fff; }}
  div[data-testid="stMetricValue"] {{ font-size:22px; }}
  .stButton button {{ border-radius:8px; font-weight:600; }}
</style>
"""


def page(title: str, icon: str, portal: str, wide=False):
    st.set_page_config(page_title=f"{title} · {BRAND}", page_icon=icon,
                       layout="wide" if wide else "centered")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="hdr"><div class="mark">{LOGO}'
        f'<div><div class="brand">{BRAND}</div>'
        f'<div class="portal">{portal}</div></div></div>'
        f'<div class="spacer"></div><span class="chip">Demo</span></div>',
        unsafe_allow_html=True)


def demo_note(extra: str = ""):
    st.markdown(
        f'<div class="demo"><b>Demonstration only.</b> {BRAND} is a fictional institution. '
        f'Policies, loans and transactions here are synthetic, and no real account is touched. '
        f'{extra}</div>', unsafe_allow_html=True)


def pill(status: str) -> str:
    label, fg, bg = STATUS.get(status, (status, MUTED, "#EEF0ED"))
    return f'<span class="pill" style="color:{fg};background:{bg}">{label}</span>'
