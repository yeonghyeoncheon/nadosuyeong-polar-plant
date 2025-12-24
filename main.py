import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pathlib import Path
import unicodedata
import io

# ==================================================
# 페이지 설정
# ==================================================
st.set_page_config(
    page_title="나도수영을 pH, EC, 광주기를 이용한 생장률 비교",
    layout="wide"
)

# ==================================================
# 한글 폰트 (Streamlit)
# ==================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# ==================================================
# 기본 정보
# ==================================================
DATA_DIR = Path("data")

EC_MAP = {
    "송도고": 1.0,
    "하늘고": 2.0,   # 최적
    "아라고": 4.0,
    "동산고": 8.0
}

# ==================================================
# NFC / NFD 안전 비교 함수
# ==================================================
def normalize_name(name: str) -> set:
    return {
        unicodedata.normalize("NFC", name),
        unicodedata.normalize("NFD", name)
    }

def find_file_by_name(directory: Path, target_name: str):
    target_norm = normalize_name(target_name)
    for f in directory.iterdir():
        if f.is_file():
            if unicodedata.normalize("NFC", f.name) in target_norm or \
               unicodedata.normalize("NFD", f.name) in target_norm:
                return f
    return None

# ==================================================
# 데이터 로딩
# ==================================================
@st.cache_data
def load_environment_data():
    env_data = {}
    with st.spinner("환경 데이터 로딩 중..."):
        for school in EC_MAP.keys():
            file_path = find_file_by_name(DATA_DIR, f"{school}_환경데이터.csv")
            if file_path is None:
                st.error(f"❌ {school} 환경 데이터 파일이 없습니다.")
                return None
            df = pd.read_csv(file_path)
            df["학교"] = school
            env_data[school] = df
    return env_data

@st.cache_data
def load_growth_data():
    with st.spinner("생육 결과 데이터 로딩 중..."):
        xlsx_path = None
        for f in DATA_DIR.iterdir():
            if f.suffix == ".xlsx":
                xlsx_path = f
                break

        if xlsx_path is None:
            st.error("❌ 생육 결과 XLSX 파일을 찾을 수 없습니다.")
            return None

        xls = pd.ExcelFile(xlsx_path)
        growth_data = {}
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df["학교"] = sheet
            df["EC"] = EC_MAP.get(sheet, None)
            growth_data[sheet] = df
    return growth_data

env_data = load_environment_data()
growth_data = load_growth_data()

if env_data is None or growth_data is None:
    st.stop()

# ==================================================
# 데이터 통합
# ==================================================
env_all = pd.concat(env_data.values(), ignore_index=True)
growth_all = pd.concat(growth_data.values(), ignore_index=True)

# ==================================================
# 제목
# ==================================================
st.title("🌱 나도수영을 pH, EC, 광주기를 이용한 생장률 비교")

# ==================================================
# 사이드바
# ==================================================
school_option = st.sidebar.selectbox(
    "학교 선택",
    ["전체"] + list(EC_MAP.keys())
)

if school_option != "전체":
    env_all = env_all[env_all["학교"] == school_option]
    growth_all = growth_all[growth_all["학교"] == school_option]

# ==================================================
# 파생 변수 (상대변화율 & 생장률)
# ==================================================
env_all["pH_상대변화율"] = env_all.groupby("학교")["ph"].pct_change()
env_all["EC_상대변화율"] = env_all.groupby("학교")["ec"].pct_change()

growth_all["생장률"] = (
    growth_all["지상부 길이(mm)"] + growth_all["지하부길이(mm)"]
) / 2

# ==================================================
# 탭 구성
# ==================================================
tab1, tab2, tab3 = st.tabs([
    "📊 EC–pH 상관관계",
    "☀️ 광주기 영향 분석",
    "📈 EC별 생장률 비교"
])

# ==================================================
# 탭 1: EC vs pH 상관관계
# ==================================================
with tab1:
    st.subheader("pH와 EC 상대변화율 상관관계")

    fig = px.scatter(
        env_all,
        x="EC_상대변화율",
        y="pH_상대변화율",
        color="학교",
        title="EC와 pH의 상대변화율 산점도"
    )

    fig.update_layout(
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
    )

    st.plotly_chart(fig, use_container_width=True)

# ==================================================
# 탭 2: 광주기 영향 (시간 기반)
# ==================================================
with tab2:
    st.subheader("광주기가 생육 환경에 미치는 영향")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=("광주기 추정 (시간 변화)", "온도 변화")
    )

    for school, df in env_all.groupby("학교"):
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["ec"], name=f"{school} EC"),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df["time"], y=df["temperature"], name=f"{school} 온도"),
            row=2, col=1
        )

    fig.update_layout(
        height=600,
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
    )

    st.plotly_chart(fig, use_container_width=True)

# ==================================================
# 탭 3: EC별 생장률
# ==================================================
with tab3:
    st.subheader("EC 농도에 따른 생장률 변화")

    summary = (
        growth_all
        .groupby(["학교", "EC"])["생장률"]
        .mean()
        .reset_index()
    )

    fig = px.line(
        summary,
        x="EC",
        y="생장률",
        color="학교",
        markers=True,
        title="EC 농도별 평균 생장률"
    )

    fig.add_vline(
        x=2.0,
        line_dash="dash",
        annotation_text="하늘고 EC 2.0 (최적)",
        annotation_position="top right"
    )

    fig.update_layout(
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
    )

    st.plotly_chart(fig, use_container_width=True)

    # 다운로드
    buffer = io.BytesIO()
    summary.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        label="📥 EC별 생장률 데이터 다운로드",
        data=buffer,
        file_name="EC별_생장률_분석.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

