import streamlit as st
import google.generativeai as genai
from PIL import Image
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

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기 (Vision AI)")
st.markdown("가정통신문 URL을 입력하면 AI가 화면을 직접 캡처(HWP 우회)하여 번역합니다.")

with st.sidebar:
    st.header("⚙️ 환경 설정")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API 키 연동 완료")
    except:
        st.error("🚨 Streamlit Secrets에 API 키가 없습니다.")
        st.stop()
        
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])

# ==========================================
# 2. 핵심 AI 및 Selenium 크롤링 기능
# ==========================================

@st.cache_resource(show_spinner=False)
def get_driver():
    """Streamlit Cloud용 Headless 크롬 드라이버 세팅"""
    options = Options()
    options.add_argument('--headless') # 화면 없이 백그라운드 실행
    options.add_argument('--no-sandbox') # 보안 샌드박스 비활성화 (리눅스 필수)
    options.add_argument('--disable-dev-shm-usage') # 메모리 부족 에러 방지
    options.add_argument('--window-size=1920,1080') # 스크린샷을 위한 넉넉한 창 크기
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    # webdriver-manager를 이용해 자동 설치 및 실행
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

@st.cache_data(show_spinner=False)
def capture_and_translate(url, target_lang, _api_key):
    """Selenium으로 요소를 스크린샷 찍고 Gemini Vision으로 바로 번역"""
    driver = None
    try:
        driver = get_driver()
        driver.get(url)
        
        # 동적 로딩을 위해 2초 대기 (사이트 사정에 따라 조절)
        time.sleep(2) 
        
        # 📌 본문 영역 또는 HWP 미리보기 영역 찾기 (기존에 쓰시던 클래스명으로 변경하세요)
        # 예시: 서울시교육청 표준 본문 영역
        wait = WebDriverWait(driver, 10)
        content_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".board-text, .bbsc, .view_content, #board_area")))
        
        # 📸 핵심: 요소만 깔끔하게 스크린샷 캡처 (바이트 형태로 메모리에 저장)
        screenshot_bytes = content_element.screenshot_as_png
        
        # 바이트 데이터를 PIL 이미지 객체로 변환
        image = Image.open(io.BytesIO(screenshot_bytes))
        
        # --- Gemini Vision API 호출 ---
        genai.configure(api_key=_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
당신은 한국 학교의 가정통신문 전문 번역가입니다.
첨부된 이미지는 가정통신문의 본문(또는 첨부파일)을 캡처한 것입니다. 
이미지 안의 모든 텍스트를 판독한 후, 반드시 {target_lang}로 번역해 주세요.

[번역 규칙]
1. 원본의 구조(표, 제목 등)를 마크다운 형식으로 유지할 것.
2. 부연 설명 없이 '번역된 결과물'만 출력할 것.
"""
        response = model.generate_content([prompt, image])
        
        return {"status": "success", "image": image, "translated_text": response.text}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 3. 메인 UI
# ==========================================

st.markdown("### 🔗 특정 가정통신문 URL 캡처 및 번역")
notice_url = st.text_input("가정통신문 게시글 주소(URL)를 입력하세요:")

if st.button("화면 캡처 및 번역 시작", key="btn_capture"):
    if notice_url:
        with st.spinner("가상 브라우저를 띄워 스크린샷을 촬영하고 번역하는 중입니다... (약 10~15초 소요)"):
            result = capture_and_translate(notice_url, target_lang, api_key)
            
            if result["status"] == "error":
                st.error("🚨 스크린샷 캡처 또는 번역 중 오류가 발생했습니다.")
                st.error(result["message"])
            else:
                st.success("캡처 및 번역 완료!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📸 AI가 캡처한 화면 (원본)")
                    st.image(result["image"], caption="가상 브라우저 스크린샷 결과", use_column_width=True)
                with col2:
                    st.markdown(f"### 🌐 {target_lang} 번역본")
                    st.success(result["translated_text"])
    else:
        st.warning("URL을 입력해 주세요.")
