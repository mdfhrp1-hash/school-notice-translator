import streamlit as st
import google.generativeai as genai
from PIL import Image
from bs4 import BeautifulSoup
import urllib.parse
import io
import time

# --- 사용자님의 오리지널 로직: Selenium 관련 라이브러리 ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# 🚨 핵심: Streamlit Cloud용 가상 크롬 브라우저 (목록 수집 + 캡처 만능)
# ==========================================
@st.cache_resource(show_spinner=False)
def get_driver():
    options = Options()
    options.add_argument('--headless') 
    options.add_argument('--no-sandbox') 
    options.add_argument('--disable-dev-shm-usage') 
    options.add_argument('--window-size=1920,2000') 
    options.add_argument('--ignore-certificate-errors') # 골치 아팠던 SSL 보안 에러 완벽 무시
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기")
st.markdown("사용자님의 원본 로직(Selenium)을 복구하여, 어떤 환경에서든 가정통신문을 정확히 읽어오고 캡처합니다.")

with st.sidebar:
    st.header("⚙️ 환경 설정")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API 키 안전 연동 완료")
    except Exception:
        st.error("🚨 Streamlit Secrets에 API 키가 설정되지 않았습니다.")
        st.stop()
        
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])

# ==========================================
# 2. 크롤링 및 AI 기능 (Selenium 100% 활용)
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_notice_list(board_url):
    """사용자님 오리지널 방식: 브라우저를 띄워 자바스크립트 렌더링을 기다린 후 목록을 추출합니다."""
    driver = None
    try:
        driver = get_driver()
        driver.get(board_url)
        time.sleep(3) # 자바스크립트가 게시글 목록을 다 그릴 때까지 확실히 기다림
        
        # 📌 교육청 사이트 특성: 게시판이 iframe(액자) 안에 숨겨져 있을 경우 안으로 진입
        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        if len(iframes) > 0:
            driver.switch_to.frame(iframes[0])
            
        # 눈에 보이는 완성된 페이지 소스를 가져와서 분석
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        notices = []
        
        # 게시판 표 안의 제목 링크를 정확히 타겟팅
        for a_tag in soup.select('table tbody tr td a, .board-list a, .bbs_list a'):
            title = a_tag.get_text(strip=True)
            link = a_tag.get('href', '')
            
            if len(title) > 3 and link and not link.startswith(('javascript:void', '#', 'tel', 'mailto')):
                full_link = urllib.parse.urljoin(board_url, link)
                if not any(n['title'] == title for n in notices):
                    notices.append({"title": title, "url": full_link})
                    
        return {"status": "success", "data": notices[:30]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        # 혹시 모를 메모리 누수 방지
        if driver:
            driver.quit()

@st.cache_data(show_spinner=False)
def capture_and_translate(url, target_lang, _api_key):
    """게시글에 진입하여 HWP 뷰어/본문을 스크린샷 찍고 Gemini Vision으로 번역"""
    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        time.sleep(3) # 본문과 첨부파일 미리보기가 뜰 때까지 대기
        
        wait = WebDriverWait(driver, 10)
        content_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".board-text, .bbsc, .view_content, #board_area, .content")))
        
        screenshot_bytes = content_element.screenshot_as_png
        image = Image.open(io.BytesIO(screenshot_bytes))
        
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
    finally:
        if driver:
            driver.quit()

# ==========================================
# 3. 메인 UI
# ==========================================
st.markdown("### 🌐 등원초등학교 최신 가정통신문")
board_url = "https://deungwon.sen.es.kr/192617/subMenu.do"

with st.spinner("가상 브라우저로 학교 게시판을 여는 중입니다... (최초 로딩 시 약간의 시간이 소요됩니다)"):
    result = fetch_notice_list(board_url)

if result["status"] == "success" and result["data"]:
    notices = result["data"]
    notice_titles = [f"{idx+1}. {notice['title']}" for idx, notice in enumerate(notices)]
    
    selected_title = st.selectbox("번역할 가정통신문을 선택하세요:", notice_titles)
    selected_index = notice_titles.index(selected_title)
    target_url = notices[selected_index]['url']
    
    if st.button("가상 브라우저로 캡처 및 번역 시작", key="btn_capture"):
        with st.spinner("해당 글에 진입하여 사진을 찍고 번역하는 중입니다... (약 10~15초 소요)"):
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
    st.warning("접속은 성공했으나, 빈 껍데기만 가져왔습니다. 학교 사이트 구조가 매우 특이합니다.")
else:
    st.error("🚨 학교 사이트 접속에 실패했습니다.")
    st.error(f"상세 에러 내용: {result['message']}")
