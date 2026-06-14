"""Shared Streamlit UI helpers for the Smart Attendance frontend."""

import streamlit as st


def apply_global_styles(max_width: int = 1180) -> None:
    st.markdown(
        f"""
        <style>
        :root {{
          --app-bg: #f6f8fb;
          --surface: #ffffff;
          --surface-muted: #f8fafc;
          --text: #172033;
          --muted: #667085;
          --border: #d9e2ec;
          --brand: #0f766e;
          --brand-dark: #134e4a;
          --accent: #2563eb;
          --danger: #b42318;
        }}
        .stApp {{background: var(--app-bg); color: var(--text);}}
        .block-container {{
          max-width: {max_width}px;
          padding-top: 1.25rem;
          padding-bottom: 2.5rem;
        }}
        h1, h2, h3 {{letter-spacing: 0; color: var(--text);}}
        h2, h3 {{margin-top: 0.75rem;}}
        .app-header {{
          border: 1px solid var(--border);
          border-radius: 8px;
          background: var(--surface);
          padding: 1.1rem 1.25rem;
          margin-bottom: 1.25rem;
          box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        }}
        .app-header__label {{
          color: var(--brand);
          font-size: 0.78rem;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          margin-bottom: 0.25rem;
        }}
        .app-header h1 {{
          margin: 0;
          font-size: 2rem;
          line-height: 1.2;
        }}
        .app-header p {{
          margin: 0.45rem 0 0;
          max-width: 780px;
          color: var(--muted);
          font-size: 1rem;
        }}
        .section-title {{
          color: var(--text);
          font-size: 1.05rem;
          font-weight: 700;
          margin: 1.4rem 0 0.65rem;
        }}
        div[data-testid="stMetric"] {{
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 0.85rem 0.95rem;
          box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03);
        }}
        [data-testid="stForm"] {{
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 1.2rem;
          box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03);
        }}
        div.stButton > button, div[data-testid="stDownloadButton"] > button {{
          border-radius: 8px;
          border: 1px solid var(--border);
          font-weight: 650;
          min-height: 2.55rem;
        }}
        div.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] button[kind="primary"] {{
          background: var(--brand);
          border-color: var(--brand);
        }}
        div.stButton > button[kind="primary"]:hover, div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
          background: var(--brand-dark);
          border-color: var(--brand-dark);
        }}
        .info-panel {{
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 1rem;
          color: var(--muted);
        }}
        .info-panel strong {{color: var(--text);}}
        .compact-note {{
          color: var(--muted);
          font-size: 0.9rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, label: str = "Smart Attendance") -> None:
    st.markdown(
        f"""
        <div class="app-header">
          <div class="app-header__label">{label}</div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str) -> None:
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
