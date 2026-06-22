import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests
from bs4 import BeautifulSoup
import urllib.parse

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기")
st.markdown("등원초등학교의 가정통신문 URL을 입력하거나, 텍스트/이미지를 업로드하면 **Gemini AI**가 자연스럽게 번역합니다.")

# 사이드바: API 키 및 설정
with st.sidebar:
    st.header("⚙️ 환경 설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])
    st.markdown("---")
    st.info("💡 **데이터 캐싱 활성화됨**\n\n한 번 번역된 문서나 이미지는 서버에 임시 저장되어 다음 번엔 대기 시간 없이 즉시 1초 만에 로딩됩니다.")

# ==========================================
# 2. 핵심 AI 및 크롤링 기능 (캐싱 적용)
# ==========================================

@st.cache_data(show_spinner=False)
def crawl_deungwon_notice(url):
    """등원초등학교 가정통신문 특정 URL에서 본문을 크롤링하는 함수 (기존 로직 반영)"""
    try:
        # 학교 사이트 보안 차단을 막기 위한 헤더 위장
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 📌 [수정 포인트] 기존 ipynb에서 사용하셨던 정확한 본문 태그 선택자를 여기에 넣어주세요!
        # 서울시교육청(sen.go.kr) 표준 게시판 구조를 기본값으로 적용해두었습니다.
        content_area = soup.select_one('.board-text, .bbsc, .contents, #board_area') 
        
        if content_area:
            text = content_area.get_text(separator='\n', strip=True)
            return text
        else:
            # 본문 영역을 찾지 못한 경우 전체 텍스트를 정리해서 반환
            return soup.get_text(separator='\n', strip=True)
            
    except Exception as e:
        return f"❌ 크롤링 에러 발생 (링크를 확인해주세요): {e}"

@st.cache_data(show_spinner=False)
def translate_text_with_gemini(text, target_lang, api_key):
    """Gemini API 텍스트 번역 함수"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
당신은 한국 '등원초등학교'의 공지사항과 가정통신문을 다문화 가정 학부모님들께 전달하는 전문 번역가입니다.
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

@st.cache_data(show_spinner=False)
def extract_text_from_image(image_bytes, api_key):
    """Gemini Vision 이미지 텍스트 판독 함수"""
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
# 3. 메인 UI (탭 구조)
# ==========================================

if not api_key:
    st.warning("👈 사이드바에 Gemini API Key를 먼저 입력해 주세요.")
    st.stop()

# 탭을 3개로 구성하여 크롤링, 텍스트, 이미지 기능을 모두 제공합니다.
tab1, tab2, tab3 = st.tabs(["🔗 등원초 사이트 크롤링", "📝 텍스트 직접 입력", "🖼️ 이미지/가정통신문 업로드"])

# --- [탭 1: 등원초등학교 크롤링] ---
with tab1:
    st.markdown("### 🌐 등원초등학교 가정통신문 링크 번역")
    st.caption("등원초 홈페이지의 가정통신문 게시글 URL을 복사해서 붙여넣으세요.")
    
    notice_url = st.text_input("가정통신문 게시글 URL 입력:")
    
    if st.button("웹페이지 긁어오기 및 번역", key="btn_crawl"):
        if notice_url:
            with st.spinner("등원초등학교 사이트에서 본문을 가져오는 중입니다..."):
                crawled_text = crawl_deungwon_notice(notice_url)
            
            if "에러" in crawled_text:
                st.error(crawled_text)
            else:
                st.success("데이터 수집 완료! 즉시 번역을 시작합니다.")
                with st.spinner(f"가져온 내용을 {target_lang}로 번역 중입니다..."):
                    translated_from_url = translate_text_with_gemini(crawled_text, target_lang, api_key)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📄 가져온 원문")
                    # 내용이 너무 길면 스크롤이 생기도록 텍스트 박스로 출력
                    st.text_area("원본 텍스트", crawled_text, height=400, disabled=True) 
                with col2:
                    st.markdown(f"### 🌐 {target_lang} 번역본")
                    st.success(translated_from_url)
        else:
            st.warning("URL을 입력해 주세요.")

# --- [탭 2: 텍스트 직접 입력] ---
with tab2:
    source_text = st.text_area("번역할 가정통신문 내용을 붙여넣으세요", height=200)
    if st.button("텍스트 번역하기", key="btn_text"):
        if source_text:
            with st.spinner(f"Gemini가 {target_lang}로 번역 중입니다..."):
                translated_text = translate_text_with_gemini(source_text, target_lang, api_key)
                st.success("번역 완료!")
                st.info(translated_text)
        else:
            st.error("텍스트를 입력해 주세요.")

# --- [탭 3: 첨부파일/이미지 업로드] ---
with tab3:
    uploaded_file = st.file_uploader("가정통신문 이미지 파일을 올려주세요 (JPG, PNG)", type=['jpg', 'jpeg', 'png'])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="업로드된 원본 이미지", use_column_width=True)
        if st.button("이미지 판독 및 번역하기", key="btn_img"):
            with st.spinner("이미지에서 글자를 추출하는 중입니다..."):
                extracted_text = extract_text_from_image(uploaded_file, api_key)
            with st.spinner(f"추출된 내용을 {target_lang}로 번역 중입니다..."):
                translated_from_img = translate_text_with_gemini(extracted_text, target_lang, api_key)
            
            st.success("판독 및 번역 완료!")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📄 추출된 원문")
                st.info(extracted_text)
            with col2:
                st.markdown(f"### 🌐 {target_lang} 번역본")
                st.success(translated_from_img)
