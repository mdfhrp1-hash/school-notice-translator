import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 🚨 버그 수정: 캐싱 삭제 (매번 건강한 새 브라우저를 띄웁니다)
# ==========================================
def get_driver():
    options = Options()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox') 
    options.add_argument('--disable-dev-shm-usage') 
    options.add_argument('--window-size=1920,3000') # 이미지 전체가 담기도록 창을 길게 설정
    options.add_argument('--ignore-certificate-errors') 
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기")
st.markdown("가정통신문 이미지를 AI가 직접 판독하여 번역해 줍니다.")

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
# 2. 크롤링 및 AI 기능 (이미지 정밀 캡처 적용)
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_notice_list(board_url):
    driver = None
    try:
        driver = get_driver()
        driver.get(board_url)
        time.sleep(4) 
        
        posts = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        notices = []
        
        for post in posts:
            try:
                a_tag = post.find_element(By.TAG_NAME, "a")
                title = a_tag.text.strip()
                if len(title) > 3:
                    if not any(n['title'] == title for n in notices):
                        notices.append({"title": title})
            except:
                continue
                
        return {"status": "success", "data": notices[:30]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if driver:
            driver.quit() # 작업 완료 후 정상 종료

@st.cache_data(show_spinner=False)
def capture_and_translate(board_url, target_title, target_lang, _api_key):
    driver = None
    try:
        driver = get_driver() # 죽은 브라우저를 쓰지 않고 여기서 무조건 새 브라우저를 켭니다!
        driver.get(board_url)
        time.sleep(4) 
        
        posts = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        target_link = None
        
        for post in posts:
            try:
                a_tag = post.find_element(By.TAG_NAME, "a")
                if target_title == a_tag.text.strip():
                    target_link = a_tag
                    break
            except:
                continue
                
        if not target_link:
            return {"status": "error", "message": "목록에서 해당 글을 찾을 수 없습니다."}

        # 자바스크립트 우회하여 클릭 진입
        driver.execute_script("arguments[0].click();", target_link)
        time.sleep(4) # 상세 페이지 로딩 대기
        
        # 💡 [중요 수정] HWP 변환 이미지가 완전히 뜰 때까지 충분히 대기합니다
        content_area = driver.find_element(By.CSS_SELECTOR, ".content, .board_view, .view_con, #board_area")
        time.sleep(3) # 이미지가 로딩될 시간을 3초 더 줍니다
        
        # 이미지가 화면 중앙에 오도록 스크롤
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", content_area)
        time.sleep(1)
        
        # 요소 스크린샷 캡처
        screenshot_bytes = content_area.screenshot_as_png
        image = Image.open(io.BytesIO(screenshot_bytes))
        
        genai.configure(api_key=_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
당신은 한국 학교의 가정통신문 전문 번역가입니다.
첨부된 이미지는 HWP 파일 형태의 가정통신문 본문 이미지입니다. 
이미지 안의 모든 텍스트를 정밀하게 판독한 후, 반드시 {target_lang}로 번역해 주세요.

[번역 규칙]
1. 원본의 구조(표, 제목, 단락 등)를 마크다운 형식으로 최대한 동일하게 유지할 것.
2. 부연 설명 없이 '번역된 결과물'만 출력할 것.
"""
        response = model.generate_content([prompt, image])
        return {"status": "success", "image": image, "translated_text": response.text}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if driver:
            driver.quit() # 번역이 끝나면 안전하게 브라우저 닫기

# ==========================================
# 3. 메인 UI
# ==========================================
st.markdown("### 🌐 등원초등학교 최신 가정통신문")
board_url = "https://deungwon.sen.es.kr/192617/subMenu.do"

with st.spinner("가상 브라우저로 학교 게시판을 여는 중입니다..."):
    result = fetch_notice_list(board_url)

if result["status"] == "success" and result["data"]:
    notices = result["data"]
    notice_titles = [f"{idx+1}. {notice['title']}" for idx, notice in enumerate(notices)]
    
    selected_title_display = st.selectbox("번역할 가정통신문을 선택하세요:", notice_titles)
    selected_index = notice_titles.index(selected_title_display)
    target_title = notices[selected_index]['title']
    
    if st.button("가상 브라우저로 이미지 캡처 및 번역 시작", key="btn_capture"):
        with st.spinner(f"[{target_title}] 이미지를 로딩하고 캡처하는 중입니다... (약 15초 소요)"):
            capture_result = capture_and_translate(board_url, target_title, target_lang, api_key)
            
            if capture_result["status"] == "error":
                st.error("🚨 스크린샷 캡처 또는 번역 중 오류가 발생했습니다.")
                st.error(capture_result["message"])
            else:
                st.success("캡처 및 번역 완료!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📸 AI가 인식한 원문 이미지")
                    st.image(capture_result["image"], caption="가상 브라우저가 자동 캡처한 HWP 본문", use_column_width=True)
                with col2:
                    st.markdown(f"### 🌐 {target_lang} 번역본")
                    st.success(capture_result["translated_text"])
                    
elif result["status"] == "success" and not result["data"]:
    st.warning("접속은 성공했으나, 게시글 목록을 불러오지 못했습니다.")
else:
    st.error("🚨 학교 사이트 접속에 실패했습니다.")
    st.error(f"상세 에러 내용: {result['message']}")
