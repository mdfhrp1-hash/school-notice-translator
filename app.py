import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests
from bs4 import BeautifulSoup
import urllib.parse
import urllib3

# SSL 인증서 경고 무시 (한국 학교 사이트 크롤링 필수 설정)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기")
st.markdown("등원초등학교 게시판에서 최신 가정통신문을 자동으로 불러옵니다.")

with st.sidebar:
    st.header("⚙️ 환경 설정")
    api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])
    st.markdown("---")
    st.info("💡 **데이터 캐싱 활성화됨**\n\n한 번 번역된 문서는 서버에 저장되어 대기 시간 없이 즉시 로딩됩니다.")

# ==========================================
# 2. 핵심 AI 및 크롤링 기능 (캐싱 적용)
# ==========================================

@st.cache_data(show_spinner=False)
def fetch_notice_list(board_url):
    """등원초등학교 게시판 목록 크롤링 (강화된 우회 로직)"""
    try:
        # 실제 크롬 브라우저처럼 완벽하게 위장
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        # verify=False를 통해 공공기관 보안 인증서 충돌 무시
        response = requests.get(board_url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        notices = []
        
        # 방식 1: 테이블 내의 모든 링크 검색
        for a_tag in soup.select('td a, .title a, .subject a, .board-list a'):
            title = a_tag.text.strip()
            link = a_tag.get('href', '')
            # 자바스크립트 빈 링크 제외하고 유효한 링크만 수집
            if title and link and 'javascript' not in link.lower() and '#' not in link:
                full_link = urllib.parse.urljoin(board_url, link)
                if not any(n['title'] == title for n in notices):
                    notices.append({"title": title, "url": full_link})
                    
        return {"status": "success", "data": notices}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(show_spinner=False)
def crawl_deungwon_notice(url):
    """본문 크롤링 (강화된 우회 로직)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        content_area = soup.select_one('.board-text, .bbsc, .contents, #board_area, .view_content, td.content') 
        
        if content_area:
            return content_area.get_text(separator='\n', strip=True)
        else:
            return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        return f"❌ 크롤링 에러: {e}"

@st.cache_data(show_spinner=False)
def translate_text_with_gemini(text, target_lang, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
당신은 한국 '등원초등학교'의 가정통신문을 다문화 가정 학부모님들께 전달하는 전문 번역가입니다.
아래 제공된 [한국어 원문]을 {target_lang}로 번역해 주세요.

[번역 규칙]
1. 원본의 마크다운 형식(표, 글머리 기호, 줄바꿈 등)을 훼손하지 말 것.
2. 부연 설명 없이 오직 '번역된 결과물'만 출력할 것.

[한국어 원문]
{text}
"""
        return model.generate_content(prompt).text
    except Exception as e:
        return f"❌ 번역 에러: {e}"

@st.cache_data(show_spinner=False)
def extract_text_from_image(image_bytes, api_key):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        image = Image.open(image_bytes)
        prompt = "이 이미지에 있는 텍스트를 마크다운 형식으로 추출해줘."
        return model.generate_content([prompt, image]).text
    except Exception as e:
        return f"❌ 이미지 판독 에러: {e}"

# ==========================================
# 3. 메인 UI
# ==========================================

if not api_key:
    st.warning("👈 사이드바에 Gemini API Key를 먼저 입력해 주세요.")
    st.
