import streamlit as st
import google.generativeai as genai
from PIL import Image
import time

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="다문화 가정을 위한 학교 알리미", page_icon="🏫", layout="wide")

st.title("🏫 다문화 가정 학부모를 위한 가정통신문 번역기")
st.markdown("""
학교에서 발송된 가정통신문 이미지나 텍스트를 입력하면, 
**Gemini AI**가 문맥을 파악하여 자연스럽게 번역해 줍니다.
""")

# 사이드바: API 키 및 설정
with st.sidebar:
    st.header("⚙️ 환경 설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])
    st.markdown("---")
    st.info("💡 **속도 최적화 적용 완료**\n\n한 번 번역된 문서나 이미지는 서버에 임시 저장(캐싱)되어, 다시 요청할 때 대기 시간 없이 즉시 결과를 보여줍니다.")

# ==========================================
# 2. 핵심 AI 기능 (캐싱 적용)
# ==========================================

# @st.cache_data를 붙이면 동일한 텍스트와 언어에 대해 API를 재호출하지 않고 저장된 결과를 불러옵니다.
@st.cache_data(show_spinner=False)
def translate_text_with_gemini(text, target_lang, api_key):
    """Gemini API를 사용하여 텍스트를 한 번에 번역하는 함수"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
당신은 한국 학교의 공지사항과 가정통신문을 다문화 가정 학부모님들께 전달하는 전문 번역가입니다.
아래 제공된 [한국어 원문]을 {target_lang}로 번역해 주세요.

[번역 규칙]
1. 원본의 마크다운 형식(표, 글머리 기호, 줄바꿈, 굵은 글씨 등)을 절대 훼손하지 말고 그대로 유지할 것.
2. 스마트폰 앱(Application)과 참가 신청(Application) 같은 동음이의어를 문맥에 맞게 정확히 구별할 것.
3. 번역에 대한 당신의 부연 설명이나 인사말 없이, 오직 '번역된 결과물'만 출력할 것.

[한국어 원문]
{text}
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ 번역 에러: {e}"

# 이미지에서 텍스트를 추출하는 작업도 캐싱하여 비용과 시간을 아낍니다.
@st.cache_data(show_spinner=False)
def extract_text_from_image(image_bytes, api_key):
    """Gemini Vision 기능을 사용하여 이미지에서 텍스트를 추출하는 함수"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        image = Image.open(image_bytes)
        prompt = "이 이미지에 있는 모든 텍스트를 마크다운 형식으로 정확하게 추출해줘. 문서의 구조(표, 제목 등)를 최대한 유지해."
        
        response = model.generate_content([prompt, image])
        return response.text
    except Exception as e:
        return f"❌ 이미지 판독 에러: {e}"

# ==========================================
# 3. 메인 UI (입력 및 결과 출력)
# ==========================================

if not api_key:
    st.warning("👈 사이드바에 Gemini API Key를 먼저 입력해 주세요.")
    st.stop()

# 탭으로 텍스트 입력과 이미지 업로드 구분
tab1, tab2 = st.tabs(["📝 텍스트 직접 입력", "🖼️ 이미지/가정통신문 업로드"])

with tab1:
    source_text = st.text_area("번역할 가정통신문 내용을 붙여넣으세요", height=200)
    if st.button("텍스트 번역하기", key="btn_text"):
        if source_text:
            with st.spinner(f"Gemini가 {target_lang}로 번역 중입니다..."):
                translated_text = translate_text_with_gemini(source_text, target_lang, api_key)
                st.success("번역 완료!")
                st.markdown("### 🌐 번역 결과")
                st.info(translated_text)
        else:
            st.error("텍스트를 입력해 주세요.")

with tab2:
    uploaded_file = st.file_uploader("가정통신문 이미지 파일을 올려주세요 (JPG, PNG)", type=['jpg', 'jpeg', 'png'])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="업로드된 원본 이미지", use_column_width=True)
        
        if st.button("이미지 판독 및 번역하기", key="btn_img"):
            # 1단계: OCR (이미지 -> 텍스트)
            with st.spinner("이미지에서 글자를 추출하는 중입니다..."):
                extracted_text = extract_text_from_image(uploaded_file, api_key)
            
            # 2단계: 번역 (추출된 텍스트 -> 타겟 언어)
            with st.spinner(f"추출된 내용을 {target_lang}로 번역 중입니다..."):
                translated_from_img = translate_text_with_gemini(extracted_text, target_lang, api_key)
            
            st.success("판독 및 번역 완료!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📄 추출된 한국어 원문")
                st.info(extracted_text)
            with col2:
                st.markdown(f"### 🌐 {target_lang} 번역본")
                st.success(translated_from_img)
