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
st.markdown("등원초등학교 게시판에서 최신 가정통신문을 자동으로 불러옵니다.")

# 사이드바: API 키 및 설정
with st.sidebar:
    st.header("⚙️ 환경 설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])
    st.markdown("---")
    st.info("💡 **데이터 캐싱 활성화됨**\n\n한 번 번역된 문서는 서버에 저장되어 다음 번엔 대기 시간 없이 즉시 로딩됩니다.")

# ==========================================
# 2. 핵심 AI 및 크롤링 기능 (캐싱 적용)
# ==========================================

@st.cache_data(show_spinner=False)
def fetch_notice_list(board_url):
    """등원초등학교 게시판 메인에서 최신 글 목록과 링크를 가져오는 함수"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(board_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        notices = []
        
        # 서울시교육청 게시판 표준 구조에서 제목과 링크 추출
        for a_tag in soup.select('td.title a, td.left a, .board-list a, .td_title a'):
            title = a_tag.text.strip()
            link = a_tag.get('href')
            if link and title and 'javascript' not in link:
                full_link = urllib.parse.urljoin(board_url, link)
                if not any(notice['title'] == title for notice in notices): # 중복 제거
                    notices.append({"title": title, "url": full_link})
                    
        return notices
    except Exception as e:
        return []

@st.cache_data(show_spinner=False)
def crawl_deungwon_notice(url):
    """선택한 가정통신문의 본문을 크롤링하는 함수"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # 게시글 본문 영역 추출
        content_area = soup.select_one('.board-text, .bbsc, .contents, #board_area, .view_content') 
        
        if content_area:
            return content_area.get_text(separator='\n', strip=True)
        else:
            return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        return f"❌ 크롤링 에러: {e}"

@st.cache_data(show_spinner=False)
def translate_text_with_gemini(text, target_lang, api_key):
    """Gemini API 텍스트 번역 함수"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
당신은 한국 '등원초등학교'의 가정통신문을 다문화 가정 학부모님들께 전달하는 전문 번역가입니다.
아래 제공된 [한국어 원문]을 {target_lang}로 번역해 주세요.

[번역 규칙]
1. 원본의 마크다운 형식(표, 글머리 기호, 줄바꿈 등)을 훼손하지 말 것.
2. 부연 설명이나 인사말 없이 오직 '번역된 결과물'만 출력할 것.

[한국어 원문]
{text}
"""
        return model.generate_content(prompt).text
    except Exception as e:
        return f"❌ 번역 에러: {e}"

@st.cache_data(show_spinner=False)
def extract_text_from_image(image_bytes, api_key):
    """Gemini Vision 이미지 텍스트 판독 함수"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        image = Image.open(image_bytes)
        prompt = "이 이미지에 있는 모든 텍스트를 마크다운 형식으로 정확하게 추출해줘. 문서 구조를 최대한 유지해."
        return model.generate_content([prompt, image]).text
    except Exception as e:
        return f"❌ 이미지 판독 에러: {e}"

# ==========================================
# 3. 메인 UI (탭 구조)
# ==========================================

if not api_key:
    st.warning("👈 사이드바에 Gemini API Key를 먼저 입력해 주세요.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["🔗 등원초 게시판 자동 연동", "📝 텍스트 직접 입력", "🖼️ 이미지/가정통신문 업로드"])

# --- [탭 1: 등원초등학교 게시판 자동 크롤링] ---
with tab1:
    st.markdown("### 🌐 최신 가정통신문 불러오기")
    board_url = "https://deungwon.sen.es.kr/192617/subMenu.do" # 사용자님이 지정한 게시판 주소
    
    with st.spinner("등원초 게시판 목록을 불러오는 중입니다..."):
        notices = fetch_notice_list(board_url)
    
    if notices:
        # 셀렉트박스로 게시글 목록을 보여줌
        notice_titles = [f"{idx+1}. {notice['title']}" for idx, notice in enumerate(notices)]
        selected_title = st.selectbox("번역할 가정통신문을 선택하세요:", notice_titles)
        
        # 선택한 게시글의 인덱스를 찾아 URL 매칭
        selected_index = notice_titles.index(selected_title)
        target_url = notices[selected_index]['url']
        
        if st.button("해당 가정통신문 긁어오기 및 번역", key="btn_crawl"):
            with st.spinner("게시글 본문을 가져오는 중입니다..."):
                crawled_text = crawl_deungwon_notice(target_url)
            
            if "에러" in crawled_text:
                st.error(crawled_text)
            else:
                st.success("본문 수집 완료! 즉시 번역을 시작합니다.")
                with st.spinner(f"가져온 내용을 {target_lang}로 번역 중입니다..."):
                    translated_from_url = translate_text_with_gemini(crawled_text, target_lang, api_key)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📄 가져온 원문")
                    st.text_area("원본 텍스트", crawled_text, height=400, disabled=True) 
                with col2:
                    st.markdown(f"### 🌐 {target_lang} 번역본")
                    st.success(translated_from_url)
    else:
        st.error("게시판 목록을 불러오지 못했습니다. 학교 사이트 구조가 변경되었거나 일시적인 접속 오류일 수 있습니다.")

# --- [탭 2: 텍스트 직접 입력] ---
with tab2:
    source_text = st.text_area("번역할 가정통신문 내용을 붙여넣으세요", height=200)
    if st.button("텍스트 번역하기", key="btn_text"):
        if source_text:
            with st.spinner(f"Gemini가 {target_lang}로 번역 중입니다..."):
                st.info(translate_text_with_gemini(source_text, target_lang, api_key))
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
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📄 추출된 원문")
                st.info(extracted_text)
            with col2:
                st.markdown(f"### 🌐 {target_lang} 번역본")
                st.success(translated_from_img)
