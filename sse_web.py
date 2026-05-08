import streamlit as st
import google.generativeai as genai

# ==========================================
# QC-bot: Integrated Semiconductor Quality Analysis System
# Version: 1.0.0 (Professional Edition)
# ==========================================

# 페이지 설정
st.set_page_config(page_title="QC-BOT | SYSTEM", layout="wide")

# UI 정밀 규격 조정: 산업용 대시보드 스타일
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');
    
    /* 전역 스타일 설정 */
    .stApp {
        background-color: #F1F3F5;
        font-family: 'Inter', 'Noto Sans KR', sans-serif;
        color: #212529;
    }
    
    /* 사이드바 스타일링 (다크 네이비) */
    [data-testid="stSidebar"] {
        background-color: #102A43;
        color: #FFFFFF;
        border-right: 1px solid #243B53;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        color: #BCCCDC !important;
    }

    /* 사이드바 라디오 버튼 */
    div[data-testid="stMarkdownContainer"] > p {
        color: #D9E2EC !important;
        font-weight: 500 !important;
    }
    
    /* 입력창 규격화 */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        min-height: 48px !important;
        font-size: 0.95rem !important;
        border: 1px solid #D9E2EC !important;
        border-radius: 4px !important;
        background-color: #FFFFFF !important;
    }
    
    /* 헤더 스타일링 (미니멀) */
    h1 {
        font-weight: 700;
        color: #102A43 !important;
        letter-spacing: -0.02em;
        margin-bottom: 0.5rem !important;
    }
    
    h2, h3 {
        color: #243B53 !important;
        font-weight: 600 !important;
    }

    /* 버튼 스타일 (기업용 블루) */
    .stButton>button {
        background-color: #1864AB;
        color: #FFFFFF;
        border: none;
        border-radius: 4px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        font-size: 0.9rem;
        transition: all 0.15s ease;
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .stButton>button:hover {
        background-color: #1971C2;
        border: none;
        color: #FFFFFF;
    }
    
    /* 카드 컨테이너 (정밀 그리드) */
    .report-card {
        background-color: #FFFFFF;
        padding: 2rem;
        border-radius: 8px;
        border: 1px solid #D9E2EC;
        margin-top: 1rem;
    }
    
    /* 레이아웃 간격 정밀 조정 */
    .block-container {
        padding-top: 5rem !important; /* 상단 여백 유지 */
        max-width: 1200px !important;
    }

    /* 구분선 */
    hr {
        margin: 2rem 0 !important;
        border: 0;
        border-top: 1px solid #D9E2EC;
    }
    
    </style>
    """, unsafe_allow_html=True)

# 시스템 상수
ENGINEERING_KNOWLEDGE = """
[STANDARD] FDC log correlation analysis required.
[GRADING] Minor (<1% yield), Major (1-5%), Critical (>5%).
[GUIDE] Peeling (ALD flow imbalance), Bridge (Over-exposure), Particle (Chamber delamination).
[SPEC] ALD Temp 450C (+/-10), Pressure 3.0torr (+/-0.2).
"""

def get_best_model(api_key):
    genai.configure(api_key=api_key)
    try:
        models = genai.list_models()
        names = [m.name.replace('models/', '') for m in models if 'generateContent' in m.supported_generation_methods]
        for p in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
            if p in names: return p
        return names[0] if names else "gemini-1.5-flash"
    except: return "gemini-1.5-flash"

# --- SIDEBAR ---
with st.sidebar:
    st.title("QC-BOT")
    app_mode = st.radio("시스템 메뉴", ["불량 원인 분석", "품질 멘토링", "장비 데이터 진단"])
    st.markdown("---")
    # CONFIGURATION (설정) 부분 시인성 강화 (두꺼운 화이트)
    st.markdown('<p style="color: #FFFFFF; font-weight: 800; font-size: 1.15rem; margin-bottom: 5px;">시스템 설정</p>', unsafe_allow_html=True)
    raw_key = st.text_input("Gemini API 키", type="password")
    api_key = raw_key.strip() if raw_key else ""
    if st.button("시스템 연결"):
        if api_key: st.success("연결 완료")
        else: st.error("키 입력 필요")

# --- 메인 로직 ---
if app_mode == "불량 원인 분석":
    st.title("불량 원인 분석")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2.5])
    with col1:
        # 102A43 색상으로 통일 및 가시성 극대화
        st.markdown('<p style="color: #102A43; font-weight: 800; font-size: 1.1rem; margin-bottom: 8px;">공정 노드</p>', unsafe_allow_html=True)
        node = st.selectbox("노드 선택", ["14nm", "10nm", "7nm", "5nm", "3nm", "2nm", "기타"], label_visibility="collapsed")
    with col2:
        # 102A43 색상으로 통일 및 가시성 극대화
        st.markdown('<p style="color: #102A43; font-weight: 800; font-size: 1.1rem; margin-bottom: 8px;">문제 현상 기술</p>', unsafe_allow_html=True)
        issue = st.text_input("현상 입력", placeholder="상세 불량 증상을 입력하세요", label_visibility="collapsed")
    
    if st.button("분석 실행"):
        if not api_key: 
            st.error("시스템 연결 필요")
        elif not issue: 
            st.warning("내용 입력 필요")
        else:
            with st.spinner("분석 중..."):
                try:
                    model = genai.GenerativeModel(get_best_model(api_key))
                    prompt = f"반도체 수석 엔지니어로서 [{node}] 노드의 [{issue}] 이슈에 대한 FA 리포트를 한글로 작성하라. 지식베이스 참고:\n{ENGINEERING_KNOWLEDGE}"
                    st.markdown('<div class="report-card">', unsafe_allow_html=True)
                    st.markdown("### 분석 보고서")
                    st.markdown(model.generate_content(prompt).text)
                    st.markdown('</div>', unsafe_allow_html=True)
                except Exception as e: 
                    st.error(f"시스템 오류: {e}")

elif app_mode == "품질 멘토링":
    st.title("품질 멘토링")
    st.markdown("---")
    if "history" not in st.session_state: st.session_state.history = []
    for m in st.session_state.history:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if chat_prompt := st.chat_input("질문 내용을 입력하세요"):
        if not api_key: st.error("시스템 연결 필요")
        else:
            st.chat_message("user").markdown(chat_prompt)
            st.session_state.history.append({"role": "user", "content": chat_prompt})
            with st.chat_message("assistant"):
                res = genai.GenerativeModel(get_best_model(api_key)).generate_content(f"엔지니어 멘토로서 한글로 답변하라. 지식베이스:\n{ENGINEERING_KNOWLEDGE}\n\n질문: {chat_prompt}").text
                st.markdown(res)
                st.session_state.history.append({"role": "assistant", "content": res})

elif app_mode == "장비 데이터 진단":
    st.title("장비 데이터 진단")
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown('<p style="color: #102A43; font-weight: 800; font-size: 1.1rem; margin-bottom: 8px;">온도 (C)</p>', unsafe_allow_html=True)
        temp = st.number_input("온도", value=450.0, label_visibility="collapsed")
    with c2:
        st.markdown('<p style="color: #102A43; font-weight: 800; font-size: 1.1rem; margin-bottom: 8px;">압력 (T)</p>', unsafe_allow_html=True)
        press = st.number_input("압력", value=3.0, label_visibility="collapsed")
    with c3:
        st.markdown('<p style="color: #102A43; font-weight: 800; font-size: 1.1rem; margin-bottom: 8px;">유량 (SCCM)</p>', unsafe_allow_html=True)
        flow = st.number_input("유량", value=500.0, label_visibility="collapsed")
    
    if st.button("진단 시작"):
        st.subheader("진단 결과")
        errs = []
        if not (440<=temp<=460): errs.append(f"범위 이탈: 온도 ({temp})")
        if not (2.8<=press<=3.2): errs.append(f"범위 이탈: 압력 ({press})")
        if not (475<=flow<=525): errs.append(f"범위 이탈: 유량 ({flow})")
        if not errs: st.success("모든 파라미터가 정상 범위 내에 있습니다.")
        else:
            for e in errs: st.error(e)

st.markdown("---")
st.caption("© 2026 QC-BOT | 통합 품질 제어 시스템")
