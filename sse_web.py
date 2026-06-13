import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import google.generativeai as genai
import datetime
import io
from PIL import Image

st.set_page_config(page_title="QC-BOT | 통합 품질 제어 시스템", layout="wide", initial_sidebar_state="expanded")

# ── 세션 초기화 ─────────────────────────────────────────────────────
if "defect_history" not in st.session_state:
    np.random.seed(42)
    lots   = [f"LOT-BASE-{i:03d}" for i in range(1, 6)]
    counts = np.random.normal(loc=12, scale=2, size=5).astype(int)
    st.session_state.defect_history = pd.DataFrame({
        "Lot_ID": lots, "Process": ["Baseline"]*5,
        "AI_Pattern_Diagnosis": ["Normal"]*5, "Defect_Count": counts
    })
if "chat_history"     not in st.session_state: st.session_state.chat_history     = []
if "latest_8d_report" not in st.session_state: st.session_state.latest_8d_report = ""
if "fdc_history"      not in st.session_state: st.session_state.fdc_history      = []

# ── 지식베이스 ────────────────────────────────────────────────────────
GLOBAL_STANDARDS = """
[국제 반도체 품질 및 장비 표준 규격]
1. SEMI E10: 설비 신뢰성, 가용성, 유지보수성(RAM) 표준. (Uptime, MTBF 기준)
2. SEMI M1: 300mm 웨이퍼 기하학적 사양 및 평탄도 기준. Edge exclusion zone 규정.
3. IATF 16949 & AEC-Q100: 자동차 산업 품질경영. 결함 발생 시 반드시 8D Report(8 Discipline) 형식을 준수.

[패턴별 원인 매핑 지침]
- Edge 패턴: 식각 설비의 Focus Ring 마모, ALD 챔버 가장자리 온도 불균일.
- Center 패턴: 가스 분사구(Showerhead) 막힘, 노광 중앙 렌즈 오염.
- Scratch 패턴: 웨이퍼 이송 로봇(Robot Arm) 정렬 불량, 카세트 슬롯 마찰.
"""

# ── CSS (Sanitized) ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&family=Noto+Sans+KR:wght@400;500&display=swap');

:root {
    --bg:       #F2F6FD;
    --surface:  #FFFFFF;
    --surf2:    #EBF3FD;
    --blue:     #2B7BE9;
    --blue-l:   #E6F1FB;
    --blue-m:   #B5D4F4;
    --blue-d:   #185FA5;
    --blue-t:   #0C447C;
    --border:   #D4E5F7;
    --border-s: #EBF3FD;
    --text:     #1A2B40;
    --text-s:   #5A7A9A;
    --text-m:   #3A5570;
    --red-bg:#FCEBEB; --red:#A32D2D; --red-b:#F09595;
    --grn-bg:#E1F5EE; --grn:#0F6E56; --grn-b:#9FE1CB;
    --amb-bg:#FAEEDA; --amb:#854F0B; --amb-b:#FAC775;
}

html, body, .stApp, .stApp > header {
    background-color: var(--bg) !important;
    font-family: 'DM Sans','Noto Sans KR',sans-serif;
    color: var(--text) !important;
}

[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span { color: var(--text-s) !important; font-weight: 400 !important; }

div[data-testid="stRadio"] label {
    border-radius: 8px !important;
    border: 1px solid transparent !important;
    padding: 9px 12px !important;
    transition: all 0.18s ease !important;
    cursor: pointer !important;
}
div[data-testid="stRadio"] label:hover { background: var(--blue-l) !important; }
div[data-testid="stRadio"] label:hover p { color: var(--blue-d) !important; }
div[data-testid="stRadio"] label:has(input:checked) {
    background: var(--blue-l) !important;
    border-color: var(--blue-m) !important;
    border-left: 3px solid var(--blue) !important;
    border-radius: 0 8px 8px 0 !important;
}
div[data-testid="stRadio"] label:has(input:checked) p { color: var(--blue-d) !important; font-weight: 500 !important; }

h1 { font-size:22px !important; font-weight:600 !important; letter-spacing:-0.04em !important; color:var(--text) !important; }
h2, h3 { font-weight:500 !important; letter-spacing:-0.03em !important; color:var(--text-m) !important; }
p { color:var(--text-s) !important; font-weight:400 !important; line-height:1.7 !important; }
.stMarkdown p { color:var(--text-s) !important; }

.qc-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px 24px;
    margin-bottom: 16px;
    transition: box-shadow 0.22s, border-color 0.22s, transform 0.22s;
}
.qc-card:hover {
    box-shadow: 0 8px 28px rgba(43,123,233,0.10);
    border-color: var(--blue-m);
    transform: translateY(-1px);
}

.kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }
.kpi-box {
    background:var(--surface); border:1px solid var(--border); border-radius:12px;
    padding:18px 20px; transition:box-shadow 0.2s, transform 0.2s;
}
.kpi-box:hover { box-shadow:0 6px 20px rgba(43,123,233,0.10); transform:translateY(-1px); }
.kpi-label { font-size:10px; font-weight:500; color:var(--text-s); text-transform:uppercase; letter-spacing:0.07em; margin-bottom:8px; }
.kpi-value { font-size:28px; font-weight:600; letter-spacing:-0.04em; font-variant-numeric:tabular-nums; }
.kpi-note  { font-size:11px; color:var(--text-s); margin-top:5px; }
.kpi-up    { color:#1D9E75; }
.kpi-dn    { color:var(--red); }

.sec-head {
    display:flex; align-items:center; gap:8px;
    font-size:13px; font-weight:500; color:var(--text-m);
    margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--border-s);
}
.sec-dot { width:6px; height:6px; border-radius:50%; background:var(--blue); flex-shrink:0; }

.tag-b { display:inline-flex;align-items:center;font-size:10px;font-weight:500;padding:3px 9px;border-radius:20px;letter-spacing:0.02em; background:var(--blue-l);color:var(--blue-t);border:1px solid var(--blue-m); }
.tag-r { display:inline-flex;align-items:center;font-size:10px;font-weight:500;padding:3px 9px;border-radius:20px;letter-spacing:0.02em; background:var(--red-bg);color:var(--red);border:1px solid var(--red-b); }
.tag-g { display:inline-flex;align-items:center;font-size:10px;font-weight:500;padding:3px 9px;border-radius:20px;letter-spacing:0.02em; background:var(--grn-bg);color:var(--grn);border:1px solid var(--grn-b); }
.tag-a { display:inline-flex;align-items:center;font-size:10px;font-weight:500;padding:3px 9px;border-radius:20px;letter-spacing:0.02em; background:var(--amb-bg);color:var(--amb);border:1px solid var(--amb-b); }

.alert-box { display:flex; align-items:flex-start; gap:10px; border-radius:10px; padding:13px 16px; font-size:13px; margin-bottom:14px; line-height:1.6; }
.alert-red  { background:var(--red-bg); color:var(--red); border:1px solid var(--red-b); }
.alert-grn  { background:var(--grn-bg); color:var(--grn); border:1px solid var(--grn-b); }
.alert-amb  { background:var(--amb-bg); color:var(--amb); border:1px solid var(--amb-b); }
.alert-blue { background:var(--blue-l); color:var(--blue-t); border:1px solid var(--blue-m); }

.step-label {
    display:inline-flex; align-items:center; gap:6px;
    font-size:10px; font-weight:500; color:var(--blue);
    text-transform:uppercase; letter-spacing:0.07em;
    margin-bottom:12px; padding:4px 10px;
    background:var(--blue-l); border-radius:20px; border:1px solid var(--blue-m);
}
.page-sub { font-size:13px; color:var(--text-s); line-height:1.6; margin-bottom:24px; }

.stButton > button {
    background: var(--blue) !important; color:#fff !important;
    border:none !important; border-radius:8px !important;
    padding:10px 22px !important; font-size:13px !important;
    font-weight:500 !important; letter-spacing:-0.01em !important;
    font-family:'DM Sans','Noto Sans KR',sans-serif !important;
    transition: background 0.15s, box-shadow 0.15s, transform 0.1s !important;
}
.stButton > button:hover {
    background: var(--blue-d) !important;
    box-shadow: 0 4px 14px rgba(43,123,233,0.28) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active { transform: scale(0.97) !important; }

.stTextInput input,
.stSelectbox [data-baseweb="select"],
.stNumberInput input {
    background:var(--bg) !important; border:1px solid var(--border) !important;
    border-radius:8px !important; color:var(--text) !important;
    font-size:13px !important; font-family:'DM Sans','Noto Sans KR',sans-serif !important;
    transition: border-color 0.2s, box-shadow 0.2s !important; box-shadow:none !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color:var(--blue) !important;
    box-shadow:0 0 0 3px rgba(43,123,233,0.10) !important;
}

.stSlider [data-baseweb="slider"] [role="slider"] {
    background:var(--blue) !important; border:2px solid var(--surface) !important;
    box-shadow:0 2px 8px rgba(43,123,233,0.3) !important;
    transition:transform 0.15s !important;
}
.stSlider [data-baseweb="slider"] [role="slider"]:hover { transform:scale(1.2) !important; }

.stChatInputContainer, .stChatInputContainer > div,
[data-testid="stChatInput"], [data-testid="stChatInput"] > div {
    background:var(--surface) !important; border-color:var(--border) !important; color:var(--text) !important;
}
[data-testid="stChatInput"] textarea { background:transparent !important; color:var(--text) !important; }
.stBottom, .stBottom > div,
[data-testid="stBottomBlockContainer"],
.stChatFloatingInputContainer, .stChatFloatingInputContainer > div { background:var(--bg) !important; }
[data-testid="stChatInput"] textarea:focus { box-shadow:none !important; border-color:var(--blue) !important; }
[data-testid="stChatInput"] button svg { fill:var(--blue) !important; }

.chat-bubble-bot {
    background:var(--surface); padding:16px 20px; border-radius:12px;
    border:1px solid var(--border); color:var(--text);
    margin-bottom:12px; line-height:1.7; font-size:14px;
}
.chat-bubble-user {
    background:var(--blue-l); color:var(--blue-t); padding:14px 18px;
    border-radius:12px; border:1px solid var(--blue-m);
    margin-left:18%; margin-bottom:12px; font-size:14px;
}

.stDownloadButton > button {
    background:transparent !important; color:var(--blue) !important;
    border:1px solid var(--blue-m) !important; border-radius:8px !important;
    padding:8px 18px !important; font-size:12px !important; font-weight:500 !important;
    transition:all 0.15s !important;
}
.stDownloadButton > button:hover {
    background:var(--blue-l) !important; border-color:var(--blue) !important;
    transform:translateY(-1px) !important;
}

[data-testid="metric-container"] {
    background:var(--surface) !important; border:1px solid var(--border) !important;
    border-radius:12px !important; padding:16px 20px !important;
}
[data-testid="stMetricValue"] { color:var(--text) !important; font-weight:600 !important; }
[data-testid="stMetricLabel"] { color:var(--text-s) !important; font-size:12px !important; }

 @keyframes fadeUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
.fade-up  { animation:fadeUp 0.35s cubic-bezier(0.4,0,0.2,1) both; }
.delay-1  { animation-delay:0.07s; }
.delay-2  { animation-delay:0.14s; }
.delay-3  { animation-delay:0.21s; }

hr { border-color:var(--border-s) !important; }
header, footer, #MainMenu { visibility:hidden; }
</style>
""", unsafe_allow_html=True)


# ── 헬퍼 ─────────────────────────────────────────────────────────────
def get_model(key, model_name="gemini-2.5-flash"):
    genai.configure(api_key=key)
    return genai.GenerativeModel(model_name)


def simulate_massive_logs():
    """10,000개 이상의 원시 데이터 중 이상치(OOC)만 필터링하는 로직"""
    total_data_points = 12500
    times = [datetime.datetime.now() - datetime.timedelta(seconds=i*2) for i in range(total_data_points)]
    # 가상의 압력 데이터 (정상: 3.0 +/- 0.1)
    pressures = np.random.normal(3.0, 0.05, total_data_points)
    
    # 인위적 이상치 주입 (2군데)
    pressures[500] = 3.45  # Spike
    pressures[2100] = 2.65 # Drop
    
    df_raw = pd.DataFrame({"Timestamp": times, "Pressure": pressures})
    # 필터링: 사람이 봐야 할 OOC 데이터만 추출
    anomalies = df_raw[(df_raw["Pressure"] > 3.2) | (df_raw["Pressure"] < 2.8)].copy()
    anomalies["Status"] = "Critical (OOC)"
    return total_data_points, anomalies


def plot_spc_chart(df):
    counts = df["Defect_Count"].values
    x_pos  = np.arange(len(counts))
    mean_v = np.mean(counts)
    std_v  = np.std(counts) if np.std(counts) > 0 else 1
    ucl    = mean_v + 3 * std_v
    lcl    = max(0, mean_v - 3 * std_v)

    fig, ax = plt.subplots(figsize=(5, 2.8))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F2F6FD')

    ax.fill_between(x_pos, counts, mean_v, where=counts >= mean_v,
                    alpha=0.12, color='#2B7BE9', interpolate=True)
    ax.fill_between(x_pos, counts, mean_v, where=counts < mean_v,
                    alpha=0.08, color='#5A7A9A', interpolate=True)
    ax.plot(x_pos, counts, color='#2B7BE9', marker='o', markersize=4,
            linestyle='-', linewidth=1.5,
            markerfacecolor='#2B7BE9', markeredgecolor='#FFFFFF', markeredgewidth=1)
    ax.axhline(mean_v, color='#5A7A9A', linestyle='--', linewidth=1,   label=f'CL {mean_v:.1f}')
    ax.axhline(ucl,    color='#E24B4A', linestyle=':',  linewidth=1.5, label=f'UCL {ucl:.1f}')
    ax.axhline(lcl,    color='#1D9E75', linestyle=':',  linewidth=1,   label=f'LCL {lcl:.1f}')

    ooc = counts > ucl
    if any(ooc):
        ax.scatter(x_pos[ooc], counts[ooc], color='#E24B4A', s=60, zorder=5,
                   edgecolors='#FFFFFF', linewidths=1.2)

    ax.tick_params(axis='y', colors='#5A7A9A', labelsize=8)
    ax.tick_params(axis='x', colors='#5A7A9A', labelsize=7)
    for spine in ax.spines.values(): spine.set_color('#D4E5F7')
    ax.legend(loc='upper left', fontsize=7, facecolor='#FFFFFF',
              edgecolor='#D4E5F7', labelcolor='#5A7A9A')
    fig.tight_layout(pad=0.5)
    return fig


def simulate_inspection(num_defects):
    pat = np.random.choice(["Edge", "Center", "Scratch"])
    if pat == "Edge":
        angles = np.random.uniform(0, 2*np.pi, num_defects)
        radii  = np.random.uniform(125, 148, num_defects)
        x = radii * np.cos(angles); y = radii * np.sin(angles)
    elif pat == "Center":
        angles = np.random.uniform(0, 2*np.pi, num_defects)
        radii  = np.random.uniform(0, 50, num_defects)
        x = radii * np.cos(angles); y = radii * np.sin(angles)
    else:
        sx, sy = np.random.uniform(-100, 50), np.random.uniform(-100, 50)
        ex, ey = sx + np.random.uniform(60,120), sy + np.random.uniform(60,120)
        x = np.linspace(sx,ex,num_defects) + np.random.normal(0,3,num_defects)
        y = np.linspace(sy,ey,num_defects) + np.random.normal(0,3,num_defects)
    return pd.DataFrame({"X_Coord": x, "Y_Coord": y}), pat


def plot_wafer(df, pattern=None):
    fig, ax = plt.subplots(figsize=(4, 4))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')

    ax.add_artist(plt.Circle((0,0), 150, color='#EBF3FD', fill=True))
    ax.add_artist(plt.Circle((0,0), 150, color='#B5D4F4', fill=False, linewidth=1.5))
    ax.add_artist(plt.Circle((0,0),   6, color='#B5D4F4', fill=True))

    dot_color = {'Edge':'#E24B4A', 'Center':'#2B7BE9', 'Scratch':'#854F0B'}.get(pattern, '#E24B4A')
    ax.scatter(df["X_Coord"], df["Y_Coord"], c=dot_color, s=22, alpha=0.85,
               edgecolors='white', linewidths=0.5, zorder=5)
    if pattern:
        ax.text(0, -165, f"{pattern} Pattern", ha='center', va='top',
                fontsize=9, color='#5A7A9A')

    ax.set_xlim(-175, 175); ax.set_ylim(-180, 175)
    ax.axis('off')
    fig.tight_layout(pad=0)
    return fig


def plot_gauge(value, spec_center, spec_range, label, unit):
    lo = spec_center - spec_range
    hi = spec_center + spec_range
    x_min = spec_center - spec_range * 2.5
    x_max = spec_center + spec_range * 2.5
    ok = lo <= value <= hi

    fig, ax = plt.subplots(figsize=(4.5, 1.6))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#FFFFFF')

    ax.barh(0, x_max - x_min, left=x_min, height=0.5,
            color='#FCEBEB', edgecolor='none', zorder=1)
    ax.barh(0, hi - lo, left=lo, height=0.5,
            color='#E1F5EE', edgecolor='#9FE1CB', linewidth=0.8, zorder=2)
    ax.plot(value, 0, marker='D', markersize=11,
            color='#1D9E75' if ok else '#E24B4A',
            markeredgecolor='white', markeredgewidth=1.5, zorder=5)

    ax.set_xlim(x_min, x_max); ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.tick_params(axis='x', labelsize=8, colors='#5A7A9A')
    for sp in ax.spines.values(): sp.set_color('#D4E5F7')
    ax.axvline(lo, color='#1D9E75', linestyle='--', linewidth=0.8, alpha=0.7)
    ax.axvline(hi, color='#1D9E75', linestyle='--', linewidth=0.8, alpha=0.7)

    status = "In-Spec ✓" if ok else "Out-of-Spec ✗"
    ax.set_title(f"{label}   {value} {unit}   {status}",
                 fontsize=9, color='#1D9E75' if ok else '#A32D2D', pad=6)
    fig.tight_layout(pad=0.4)
    return fig, ok


# ── 사이드바 ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<h2 style="font-size:18px;font-weight:600;letter-spacing:-0.03em;'
        'color:#185FA5;padding:4px 8px 16px;">QC-BOT'
        '<br><span style="font-size:10px;font-weight:400;color:#5A7A9A;'
        'letter-spacing:0.05em;text-transform:uppercase;">Enterprise v6.0</span></h2>',
        unsafe_allow_html=True
    )

    menu = st.radio("시스템 메뉴", [
        "🔬  AI 패턴 분석 · 8D Report",
        "⚙️  공정별 설비 진단 (FDC)",
        "📚  표준 규격 품질 멘토링"
    ])

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:10px;font-weight:500;color:#5A7A9A;'
        'text-transform:uppercase;letter-spacing:0.07em;margin:0 0 6px 2px;">'
        'SPC X-bar Chart</p>',
        unsafe_allow_html=True
    )
    st.pyplot(plot_spc_chart(st.session_state.defect_history), use_container_width=True)

    counts = st.session_state.defect_history["Defect_Count"].values
    mean_v = np.mean(counts)
    std_v  = np.std(counts) if np.std(counts) > 0 else 1
    if counts[-1] > mean_v + 3*std_v:
        st.markdown(
            '<div class="alert-box alert-red" style="margin-top:8px;padding:8px 12px;font-size:11px;">'
            '⚠️ UCL 돌파 감지 — 즉시 확인 필요</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="alert-box alert-grn" style="margin-top:8px;padding:8px 12px;font-size:11px;">'
            '✓ 현재 공정 정상 관리 중</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:10px;font-weight:500;color:#5A7A9A;'
        'text-transform:uppercase;letter-spacing:0.07em;margin:0 0 6px 2px;">'
        'API 시스템 키</p>',
        unsafe_allow_html=True
    )
    raw_key = st.text_input("Gemini API 키", type="password",
                            label_visibility="collapsed", placeholder="Gemini API Key")
    api_key = raw_key.strip() if raw_key else ""


# ═══════════════════════════════════════════════════════════════════════
#  메뉴 1 — AI 패턴 분석 · 8D Report
# ═══════════════════════════════════════════════════════════════════════
if "AI 패턴" in menu:
    st.markdown('<h1>웨이퍼 맵 분석 및 8D Report 발급</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">검사 장비 좌표를 AI가 판독하여 결함 패턴을 분석하고, '
        'IATF 16949 기반 8D 보고서를 자동 생성합니다.</p>',
        unsafe_allow_html=True
    )

    hist = st.session_state.defect_history
    total_lots  = len(hist)
    avg_defects = hist["Defect_Count"].mean()
    std_h       = hist["Defect_Count"].std() if len(hist) > 1 else 1
    ooc_count   = int((hist["Defect_Count"] > hist["Defect_Count"].mean() + 3*std_h).sum()) if len(hist) > 2 else 0

    st.markdown(f"""
<div class="kpi-grid fade-up">
  <div class="kpi-box">
    <div class="kpi-label">누적 분석 Lot</div>
    <div class="kpi-value" style="color:#185FA5;">{total_lots}</div>
    <div class="kpi-note"><span class="kpi-up">↑ 실시간</span> 업데이트 중</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-label">평균 결함 수</div>
    <div class="kpi-value" style="color:#854F0B;">{avg_defects:.1f}</div>
    <div class="kpi-note">기준값 대비 현황</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-label">OOC 발생 수</div>
    <div class="kpi-value" style="color:{'#A32D2D' if ooc_count>0 else '#0F6E56'};">{ooc_count}</div>
    <div class="kpi-note">{'<span class="kpi-dn">즉시 조치 필요</span>' if ooc_count>0 else '<span class="kpi-up">정상 범위</span>'}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    col_in, col_out = st.columns([1, 1.8], gap="medium")

    with col_in:
        st.markdown('<div class="qc-card fade-up delay-1">', unsafe_allow_html=True)
        st.markdown('<div class="step-label">Step 01 · 데이터 수신 및 필터링</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-head"><span class="sec-dot"></span>수집 모드 설정</div>', unsafe_allow_html=True)
        
        data_mode = st.radio("데이터 소스 선택", 
                             ["Standard", "Smart Filter (Massive Logs v7.0)"],
                             horizontal=True, label_visibility="collapsed")
        
        current_lot = f"LOT-{datetime.datetime.now().strftime('%m%d')}-{np.random.randint(100,999)}"
        st.text_input("분석 대상 Lot ID", value=current_lot, disabled=True)
        node = st.selectbox("진행 공정", ["3nm (GAA) Etch", "5nm Photo", "7nm ALD", "28nm CVD"])
        
        if data_mode == "Smart Filter (Massive Logs v7.0)":
            st.markdown('<p style="font-size:11px;color:var(--blue);margin-top:-10px;">'
                        '※ SECS/GEM 가상 커넥터 활성화됨 (1만건 이상의 데이터 실시간 스캔)</p>', unsafe_allow_html=True)
        
        fetch_btn = st.button("장비 데이터 로드 및 분석", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if len(hist) > 0:
            st.markdown('<div class="qc-card fade-up delay-2">', unsafe_allow_html=True)
            st.markdown('<div class="sec-head"><span class="sec-dot"></span>분석 이력</div>', unsafe_allow_html=True)
            dh = hist[["Lot_ID","Process","Defect_Count"]].tail(6).copy()
            dh.columns = ["Lot ID","공정","결함 수"]
            st.dataframe(dh, use_container_width=True, hide_index=True,
                         height=min(35*len(dh)+40, 230))
            st.markdown('</div>', unsafe_allow_html=True)

    with col_out:
        if fetch_btn:
            if not api_key:
                st.markdown('<div class="alert-box alert-red">⚠️ 사이드바에 Gemini API 키를 입력해주세요.</div>', unsafe_allow_html=True)
            else:
                filtered_evidence = ""
                if data_mode == "Smart Filter (Massive Logs v7.0)":
                    with st.status("🚀 대용량 장비 데이터 스캐닝 중...", expanded=True) as status:
                        total_pts, anomalies = simulate_massive_logs()
                        st.write(f"📡 {total_pts:,}개의 센서 데이터 포인트 수신 완료.")
                        st.write("🔍 통계적 이상치(OOC) 탐색 중...")
                        import time
                        time.sleep(1.2)
                        st.write(f"✅ 필터링 완료: {len(anomalies)}개의 핵심 이상 징후 감지.")
                        status.update(label="데이터 프리필터링 완료", state="complete", expanded=False)
                    
                    st.markdown('<div class="alert-box alert-amb"><strong>[Smart Filter 결과]</strong> 엔지니어 검토가 필요한 OOC 구간을 자동으로 추출했습니다.</div>', unsafe_allow_html=True)
                    st.dataframe(anomalies, use_container_width=True, hide_index=True)
                    filtered_evidence = f"\n[장비 로그 필터링 결과]:\n{anomalies.to_string(index=False)}"

                num_defects = np.random.randint(20, 65)
                df_coords, secret_pattern = simulate_inspection(num_defects)

                # 웨이퍼 맵 카드
                st.markdown('<div class="qc-card fade-up">', unsafe_allow_html=True)
                st.markdown('<div class="step-label">Step 02 · AI 판독 결과</div>', unsafe_allow_html=True)
                st.markdown('<div class="sec-head"><span class="sec-dot"></span>웨이퍼 맵 분석</div>', unsafe_allow_html=True)

                wmap_col, info_col = st.columns([1,1])
                fig_w = plot_wafer(df_coords, secret_pattern)
                with wmap_col:
                    st.pyplot(fig_w, use_container_width=True)
                with info_col:
                    pat_tag = {"Edge":"tag-r","Center":"tag-b","Scratch":"tag-a"}.get(secret_pattern,"tag-r")
                    st.markdown(f"""
<div style="padding:8px 0;">
  <div style="font-size:10px;color:var(--text-s);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">Lot ID</div>
  <div style="font-size:12px;font-weight:500;color:var(--text);font-family:monospace;margin-bottom:14px;">{current_lot}</div>
  <div style="font-size:10px;color:var(--text-s);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">공정</div>
  <div style="font-size:12px;font-weight:500;color:var(--text);margin-bottom:14px;">{node}</div>
  <div style="font-size:10px;color:var(--text-s);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">검출 결함</div>
  <div style="font-size:26px;font-weight:600;color:#A32D2D;letter-spacing:-0.04em;margin-bottom:10px;">{num_defects}<span style="font-size:13px;font-weight:400;color:var(--text-s);"> 개</span></div>
  <span class="{pat_tag}">{secret_pattern} Pattern</span>
</div>
""", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # 8D Report 카드
                st.markdown('<div class="qc-card fade-up delay-1">', unsafe_allow_html=True)
                st.markdown('<div class="step-label">Step 03 · 8D Report 자동 생성</div>', unsafe_allow_html=True)
                st.markdown('<div class="sec-head"><span class="sec-dot"></span>IATF 16949 기반 분석 보고서</div>', unsafe_allow_html=True)

                buf = io.BytesIO()
                fig_w.savefig(buf, format="png", bbox_inches='tight', facecolor='white')
                buf.seek(0)
                img_for_ai = Image.open(buf)

                with st.spinner("AI 분석 엔진 가동 중..."):
                    try:
                        model = get_model(api_key)
                        prompt = f"""
당신은 차량용 반도체 품질 보증(QA) 엔지니어입니다.
제공된 웨이퍼 맵 이미지를 판독하고, [{node}] 공정에서 발생한 [{num_defects}개] 결함에 대해
IATF 16949 기반 **8D Report**를 작성하세요.
특히 아래의 필터링된 장비 로그 이상 징후를 근본 원인 분석(D4)의 핵심 근거로 활용하십시오.
이모티콘 사용 금지. 마크다운 표(Table) 형식으로 엄격히 작성.

[필수 포함 포맷]
- D1: 팀 구성 (Team Formation)
- D2: 문제 설명 (Problem Description) — 이미지 패턴 명시
- D3: 임시 봉쇄 조치 (Interim Containment Actions)
- D4: 근본 원인 분석 (Root Cause Analysis) — 장비 로그 증거 필수 포함
- D5: 영구 시정 조치 계획 (Permanent Corrective Actions)
- D6: 시정 조치 실행 및 검증
- D7: 재발 방지 계획
- D8: 팀 공로 인정 및 종료

[분석 근거 데이터]:
{filtered_evidence if filtered_evidence else "장비 로그 데이터 없음 (이미지 기반 추론)"}

[지식베이스]:
{GLOBAL_STANDARDS}
"""
                        response = model.generate_content([prompt, img_for_ai]).text
                        new_row = pd.DataFrame([{
                            "Lot_ID": current_lot, "Process": node,
                            "AI_Pattern_Diagnosis": secret_pattern,
                            "Defect_Count": num_defects
                        }])
                        st.session_state.defect_history = pd.concat(
                            [st.session_state.defect_history, new_row], ignore_index=True)
                        st.session_state.latest_8d_report = response
                        st.markdown(response)
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.download_button(
                            "8D Report 다운로드 (.txt)",
                            data=response,
                            file_name=f"8D_{current_lot}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.markdown(f'<div class="alert-box alert-red">오류 발생: {e}</div>', unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  메뉴 2 — 공정별 설비 진단 (FDC)
# ═══════════════════════════════════════════════════════════════════════
elif "설비 진단" in menu:
    st.markdown('<h1>공정별 장비 정밀 진단 (FDC)</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">핵심 공정 파라미터를 입력하면 스펙 이탈 여부를 게이지 차트로 즉시 시각화합니다.</p>',
        unsafe_allow_html=True
    )

    process_group = st.selectbox("진단 공정 선택", ["포토 공정", "식각 공정", "증착 공정"])

    st.markdown('<div class="qc-card fade-up">', unsafe_allow_html=True)
    st.markdown(f'<div class="sec-head"><span class="sec-dot"></span>{process_group} · 파라미터 입력</div>', unsafe_allow_html=True)

    params_ok = True
    scan_done = False

    if process_group == "포토 공정":
        st.markdown('<p style="font-size:12px;margin-bottom:12px;">설비: EUV 스캐너 (NXE:3400)</p>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: dose  = st.slider("EUV Dose (mJ/cm²) — Spec: 30±2", 25.0, 35.0, 30.0, 0.1)
        with c2: focus = st.slider("Focus Offset (nm) — Spec: 0±15",  -30,  30,   0)
        scan_done = st.button("장비 스캔 실행", use_container_width=False)
        if scan_done:
            g1, g2 = st.columns(2)
            with g1:
                f, ok1 = plot_gauge(dose,  30,  2,  "EUV Dose",     "mJ/cm²")
                st.pyplot(f, use_container_width=True)
            with g2:
                f, ok2 = plot_gauge(focus, 0,  15,  "Focus Offset", "nm")
                st.pyplot(f, use_container_width=True)
            params_ok = ok1 and ok2

    elif process_group == "식각 공정":
        st.markdown('<p style="font-size:12px;margin-bottom:12px;">설비: 건식 식각기 (ICP Etcher)</p>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: rf   = st.slider("RF Source (W) — Spec: 1500±50",       1400, 1600, 1500)
        with c2: bias = st.slider("Bias Voltage (V) — Spec: 300±20",      250,  350,  300)
        with c3: gas  = st.slider("CF4 Gas Flow (sccm) — Spec: 100±5",    80,   120,  100)
        scan_done = st.button("장비 스캔 실행", use_container_width=False)
        if scan_done:
            g1, g2, g3 = st.columns(3)
            with g1:
                f, ok1 = plot_gauge(rf,   1500, 50, "RF Source",    "W")
                st.pyplot(f, use_container_width=True)
            with g2:
                f, ok2 = plot_gauge(bias, 300,  20, "Bias Voltage", "V")
                st.pyplot(f, use_container_width=True)
            with g3:
                f, ok3 = plot_gauge(gas,  100,   5, "CF4 Flow",     "sccm")
                st.pyplot(f, use_container_width=True)
            params_ok = ok1 and ok2 and ok3

    elif process_group == "증착 공정":
        st.markdown('<p style="font-size:12px;margin-bottom:12px;">설비: High-k ALD 챔버</p>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: temp  = st.slider("Chamber Temp (°C) — Spec: 300±5",   280, 320, 300)
        with c2: press = st.slider("Pressure (Torr) — Spec: 2.0±0.1",   1.5, 2.5, 2.0, 0.01)
        scan_done = st.button("장비 스캔 실행", use_container_width=False)
        if scan_done:
            g1, g2 = st.columns(2)
            with g1:
                f, ok1 = plot_gauge(temp,  300, 5,   "Chamber Temp", "°C")
                st.pyplot(f, use_container_width=True)
            with g2:
                f, ok2 = plot_gauge(press, 2.0, 0.1, "Pressure",     "Torr")
                st.pyplot(f, use_container_width=True)
            params_ok = ok1 and ok2

    if scan_done:
        st.markdown("<br>", unsafe_allow_html=True)
        if params_ok:
            st.markdown('<div class="alert-box alert-grn">✓ 모든 파라미터 정상 (In-Spec) — 공정 진행 승인</div>', unsafe_allow_html=True)
            fdc_status = "Pass"
        else:
            st.markdown('<div class="alert-box alert-red">⚠️ 스펙 이탈 감지 (Out-of-Spec) — 즉시 점검 후 공정 중단 요망</div>', unsafe_allow_html=True)
            fdc_status = "Fail"
        st.session_state.fdc_history.append({
            "시각": datetime.datetime.now().strftime("%H:%M:%S"),
            "공정": process_group, "결과": fdc_status
        })

    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.fdc_history:
        st.markdown('<div class="qc-card fade-up delay-1">', unsafe_allow_html=True)
        st.markdown('<div class="sec-head"><span class="sec-dot"></span>진단 이력</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(st.session_state.fdc_history).tail(10),
                     use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  메뉴 3 — 표준 규격 품질 멘토링
# ═══════════════════════════════════════════════════════════════════════
elif "멘토링" in menu:
    st.markdown('<h1>국제 규격 · 품질 전문가 멘토링</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">SEMI E10, SEMI M1, IATF 16949 등 국제 규격 기반의 전문 지식을 실시간으로 제공합니다.</p>',
        unsafe_allow_html=True
    )

    # 빠른 질문 버튼
    st.markdown('<div class="qc-card fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="sec-head"><span class="sec-dot"></span>빠른 질문 바로가기</div>', unsafe_allow_html=True)
    qcols = st.columns(3)
    quick_qs = ["SEMI E10 Uptime 계산 방법", "8D Report D4 작성 가이드", "Edge 패턴 원인과 조치"]
    for i, (col, q) in enumerate(zip(qcols, quick_qs)):
        with col:
            if st.button(q, use_container_width=True, key=f"quick_{i}"):
                st.session_state.chat_history.append({"role": "user", "content": q})
                if api_key:
                    try:
                        model = get_model(api_key)
                        res = model.generate_content(
                            f"반도체 품질 전문가로서 규격을 인용하여 간결하게 답변하세요. 이모티콘 금지.\n{GLOBAL_STANDARDS}\n질문: {q}"
                        ).text
                        st.session_state.chat_history.append({"role": "assistant", "content": res})
                    except Exception as e:
                        st.session_state.chat_history.append({"role": "assistant", "content": f"오류: {e}"})
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # 채팅 이력
    if st.session_state.chat_history:
        st.markdown('<div class="qc-card fade-up delay-1">', unsafe_allow_html=True)
        st.markdown('<div class="sec-head"><span class="sec-dot"></span>대화 내역</div>', unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="chat-bubble-bot">'
                    f'<strong style="color:var(--blue-d);font-size:10px;text-transform:uppercase;letter-spacing:0.05em;">QC Expert</strong>'
                    f'<br><br>{msg["content"]}</div>',
                    unsafe_allow_html=True
                )
        st.markdown('</div>', unsafe_allow_html=True)

    # 채팅 입력
    if prompt := st.chat_input("규격, 공정, 품질 기법에 대해 질문하세요..."):
        if not api_key:
            st.markdown('<div class="alert-box alert-red">⚠️ API 키가 필요합니다.</div>', unsafe_allow_html=True)
        else:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.spinner("전문 지식베이스 검색 중..."):
                try:
                    model = get_model(api_key)
                    res = model.generate_content(
                        f"반도체 품질 전문가로서 규격을 인용하여 답변하세요. 이모티콘 금지.\n{GLOBAL_STANDARDS}\n질문: {prompt}"
                    ).text
                    st.session_state.chat_history.append({"role": "assistant", "content": res})
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")


# ── 푸터 ─────────────────────────────────────────────────────────────
st.markdown(
    '<br><hr style="border-color:#EBF3FD;margin:20px 0 10px;"/>'
    '<p style="font-size:11px;color:#5A7A9A;text-align:center;">'
    'QC-BOT Enterprise v6.0 · Process Control Interface · © 2026</p>',
    unsafe_allow_html=True
)
