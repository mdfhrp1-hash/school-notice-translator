import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests
from bs4 import BeautifulSoup
import urllib.parse
import urllib3
import ssl
from requests.adapters import HTTPAdapter
import io
import time

# --- Selenium 관련 라이브러리 ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 🚨 핵심 마법 1: 구형 학교 사이트 보안 장벽 우회 (목록 긁어오기용)
# ==========================================
class LegacyHttpAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers('DEFAULT@SECLEVEL=0')
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

def get_legacy_session():
    session = requests.session()
    session.mount('https://', LegacyHttpAdapter())
    return session

# ==========================================
# 🚨 핵심 마법 2: Streamlit Cloud용 가상 크롬 브라우저 (캡처용)
# ==========================================
@st.cache_resource(show_spinner=False)
def get_driver():
    """Streamlit Cloud용 Headless 크롬 드라이버 세팅"""
    options = Options()
    options.add_argument('--headless') # 화면 없이 백그라운드 실행
    options.add_argument('--no-sandbox') 
    options.add_argument('--disable-dev-shm-usage') 
    options.add_argument('--window-size=1920,2000') # 스크롤 없이 길게 캡처하기 위해 창을 세로로 길게 설정
    options.add_argument('--ignore-certificate-errors') # 셀레니움에서도 인증서 에러 무시
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기")
st.markdown("최신 가정통신문을 자동으로 불러오며, AI가 화면을 직접 캡처(HWP 우회)하여 번역합니다.")

with st.sidebar:
    st.header("⚙️ 환경 설정")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API 키 자동 연동 완료")
    except Exception:
        st.error("🚨 Streamlit Secrets에 API 키가 설정되지 않았습니다.")
        st.stop()
        
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])

# ==========================================
# 2. 크롤링 및 AI 기능
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_notice_list(board_url):
    """하이브리드 게시판 크롤링: 표, 리스트, 카드형 등 모든 구조의 게시물 제목을 유연하게 찾습니다."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        session = get_legacy_session()
        response = session.get(board_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        notices = []
        
        # 1. 서울시교육청 사이트들이 제목을 숨겨두는 모든 가능한 태그와 클래스를 총동원하여 탐색합니다.
        # (표의 제목칸, 리스트형 제목칸, 모바일형 제목칸 모두 포함)
        title_elements = soup.select(
            'td.title, td.left, td.tal, td.subject, td.txt_l, '  # 일반적인 표 형태
            'div.tit, p.tit, span.tit, li.tit, '                 # 리스트/웹진 형태
            '.board_list a, .bbs_list a, .board-list a'          # 컨테이너 안의 직접 링크
        )
        
        # 2. 만약 위에서 못 찾았다면, 게시판 영역 안의 모든 칸(td)을 싹 다 가져옵니다. (최후의 보루)
        if not title_elements:
            title_elements = soup.select('.board_area td, .sub_content td, #content td, table td')
            
        # 3. 찾은 요소들 안에서 진짜 '가정통신문 링크'만 똑똑하게 걸러냅니다.
        for element in title_elements:
            # 요소 자체가 <a> 태그이거나, 내부에 <a> 태그를 품고 있는 경우 모두 대응
            a_tag = element if element.name == 'a' else element.find('a')
            
            if a_tag:
                title = a_tag.get_text(strip=True)
                link = a_tag.get('href', '')
                
                # 제목이 너무 짧은 메뉴 버튼이나 쓸모없는 자바스크립트 더미 링크 필터링
                if len(title) > 4 and link and not link.startswith(('javascript:void', '#', 'tel:', 'mailto:')):
                    # '다음', '이전', '목록' 같은 페이징 버튼은 철저히 배제
                    if title not in ['이전', '다음', '처음', '맨끝', '목록', '검색', '확인', '취소']:
                        full_link = urllib.parse.urljoin(board_url, link)
                        
                        # 중복 방지 로직 (이미 수집한 제목이면 패스)
                        if not any(n['title'] == title for n in notices):
                            notices.append({"title": title, "url": full_link})
                            
        return {"status": "success", "data": notices[:30]} # 가장 최신 글 30개만 반환
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(show_spinner=False)
def capture_and_translate(url, target_lang, _api_key):
    """Selenium으로 요소를 스크린샷 찍고 Gemini Vision으로 바로 번역"""
    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(3) # 동적 렌더링(로딩)을 위해 3초 대기
        
        wait = WebDriverWait(driver, 10)
        # 📌 서울시교육청 공통 본문 영역 CSS 선택자 모음
        content_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".board-text, .bbsc, .view_content, #board_area, .content")))
        
        # 요소 스크린샷 캡처
        screenshot_bytes = content_element.screenshot_as_png
        image = Image.open(io.BytesIO(screenshot_bytes))
        
        # Gemini Vision 번역
        genai.configure(api_key=_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
당신은 한국 학교의 가정통신문 전문 번역가입니다.
첨부된 이미지는 가정통신문의 본문(또는 첨부파일)을 캡처한 것입니다. 
이미지 안의 모든 텍스트를 판독한 후, 반드시 {target_lang}로 번역해 주세요.

[번역 규칙]
1. 원본의 구조(표, 제목 등)를 마크다운 형식으로 최대한 유지할 것.
2. 부연 설명 없이 '번역된 결과물'만 출력할 것.
"""
        response = model.generate_content([prompt, image])
        return {"status": "success", "image": image, "translated_text": response.text}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 3. 메인 UI
# ==========================================
st.markdown("### 🌐 최신 가정통신문 목록")
board_url = "https://deungwon.sen.es.kr/192617/subMenu.do"

with st.spinner("등원초 게시판 목록을 불러오는 중입니다..."):
    result = fetch_notice_list(board_url)

if result["status"] == "success" and result["data"]:
    notices = result["data"]
    notice_titles = [f"{idx+1}. {notice['title']}" for idx, notice in enumerate(notices)]
    
    selected_title = st.selectbox("번역할 가정통신문을 선택하세요:", notice_titles)
    selected_index = notice_titles.index(selected_title)
    target_url = notices[selected_index]['url']
    
    if st.button("가상 브라우저로 캡처 및 번역 시작", key="btn_capture"):
        with st.spinner("서버에서 가상 크롬을 띄워 해당 글의 사진을 찍고 번역하는 중입니다... (약 10~15초 소요)"):
            capture_result = capture_and_translate(target_url, target_lang, api_key)
            
            if capture_result["status"] == "error":
                st.error("🚨 스크린샷 캡처 또는 번역 중 오류가 발생했습니다.")
                st.error(capture_result["message"])
            else:
                st.success("캡처 및 번역 완료!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📸 AI가 캡처한 원문 화면")
                    st.image(capture_result["image"], caption="가상 브라우저 스크린샷 결과", use_column_width=True)
                with col2:
                    st.markdown(f"### 🌐 {target_lang} 번역본")
                    st.success(capture_result["translated_text"])
                    
elif result["status"] == "success" and not result["data"]:
    st.warning("접속은 성공했으나, 게시글 목록을 찾지 못했습니다.")
else:
    st.error("🚨 학교 사이트 접속에 실패했습니다.")
    st.error(f"상세 에러 내용: {result['message']}")
