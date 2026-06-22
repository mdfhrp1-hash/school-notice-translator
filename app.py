import streamlit as st
import google.generativeai as genai
from PIL import Image
import requests
from bs4 import BeautifulSoup
import urllib.parse
import urllib3
import ssl
from requests.adapters import HTTPAdapter

# SSL 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 🚨 핵심 마법: 구형 학교 사이트 보안 장벽 우회 로직
# ==========================================
class LegacyHttpAdapter(HTTPAdapter):
    """최신 OpenSSL 3.0 환경에서 구형 한국 공공기관 인증서에 접속하기 위한 어댑터"""
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # 보안 레벨을 0으로 강제 하향 조정하여 구형 서명(WRONG_SIGNATURE_TYPE) 허용
        ctx.set_ciphers('DEFAULT@SECLEVEL=0')
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

def get_legacy_session():
    """보안이 낮아진 특수 세션을 반환하는 함수"""
    session = requests.session()
    session.mount('https://', LegacyHttpAdapter())
    return session

# ==========================================
# 1. 페이지 설정 및 초기화
# ==========================================
st.set_page_config(page_title="등원초 다문화 가정 알리미", page_icon="🏫", layout="wide")

st.title("🏫 등원초등학교 가정통신문 다국어 번역기")
st.markdown("등원초등학교 게시판에서 최신 가정통신문을 자동으로 불러옵니다.")

with st.sidebar:
    st.header("⚙️ 환경 설정")
    # GitHub 보안 경고(Secret scanning)를 피하기 위해 st.secrets 사용
    # 반드시 Streamlit Cloud 세팅(Secrets)에 GEMINI_API_KEY를 넣어두셔야 합니다!
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("API 키 자동 연동 완료")
    except Exception:
        st.error("🚨 Streamlit Secrets에 API 키가 설정되지 않았습니다.")
        st.stop()
        
    target_lang = st.selectbox("번역할 언어를 선택하세요", ["English", "Tiếng Việt (베트남어)", "中文 (중국어)", "日本語 (일본어)", "Русский (러시아어)"])
    st.markdown("---")
    st.info("💡 **데이터 캐싱 활성화됨**\n\n한 번 번역된 문서는 서버에 저장되어 대기 시간 없이 즉시 로딩됩니다.")

# ==========================================
# 2. 핵심 AI 및 크롤링 기능 (캐싱 적용)
# ==========================================

@st.cache_data(show_spinner=False)
def fetch_notice_list(board_url):
    """특수 세션을 이용한 게시판 목록 크롤링"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # requests.get 대신 우리가 만든 특수 접속기(get_legacy_session) 사용
        session = get_legacy_session()
        response = session.get(board_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        notices = []
        
        for a_tag in soup.select('td a, .title a, .subject a, .board-list a'):
            title = a_tag.text.strip()
            link = a_tag.get('href', '')
            if title and link and 'javascript' not in link.lower() and '#' not in link:
                full_link = urllib.parse.urljoin(board_url, link)
                if not any(n['title'] == title for n in notices):
                    notices.append({"title": title, "url": full_link})
                    
        return {"status": "success", "data": notices}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(show_spinner=False)
def crawl_deungwon_notice(url):
    """특수 세션을 이용한 본문 크롤링"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        session = get_legacy_session()
        response = session.get(url, headers=headers, timeout=10)
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

tab1, tab2, tab3 = st.tabs(["🔗 등원초 게시판 자동 연동", "📝 텍스트 직접 입력", "🖼️ 첨부 이미지 업로드"])

with tab1:
    st.markdown("### 🌐 최신 가정통신문 불러오기")
    board_url = "https://deungwon.sen.es.kr/192617/subMenu.do"
    
    with st.spinner("등원초 게시판 목록을 긁어오는 중입니다 (보안 우회 중)..."):
        result = fetch_notice_list(board_url)
    
    if result["status"] == "success" and result["data"]:
        notices = result["data"]
        notice_titles = [f"{idx+1}. {notice['title']}" for idx, notice in enumerate(notices)]
        selected_title = st.selectbox("번역할 가정통신문을 선택하세요:", notice_titles)
        
        selected_index = notice_titles.index(selected_title)
        target_url = notices[selected_index]['url']
        
        if st.button("해당 가정통신문 긁어오기 및 번역", key="btn_crawl"):
            with st.spinner("게시글 본문을 가져오는 중입니다..."):
                crawled_text = crawl_deungwon_notice(target_url)
            
            if "에러" in crawled_text:
                st.error(crawled_text)
            else:
                st.success("본문 수집 완료! 번역을 시작합니다.")
                with st.spinner(f"가져온 내용을 {target_lang}로 번역 중입니다..."):
                    translated_from_url = translate_text_with_gemini(crawled_text, target_lang, api_key)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📄 가져온 원문")
                    st.text_area("원본 텍스트", crawled_text, height=400, disabled=True) 
                with col2:
                    st.markdown(f"### 🌐 {target_lang} 번역본")
                    st.success(translated_from_url)
                    
    elif result["status"] == "success" and not result["data"]:
        st.warning("접속은 성공했으나, 게시글 목록을 찾지 못했습니다. 학교 사이트 게시판 형태가 일반적이지 않습니다.")
    else:
        st.error("🚨 학교 사이트 접속에 실패했습니다.")
        st.error(f"상세 에러 내용: {result['message']}")

with tab2:
    source_text = st.text_area("번역할 내용을 붙여넣으세요", height=200)
    if st.button("텍스트 번역", key="btn_text"):
        st.info(translate_text_with_gemini(source_text, target_lang, api_key))

with tab3:
    uploaded_file = st.file_uploader("이미지 파일 (JPG, PNG)", type=['jpg', 'jpeg', 'png'])
    if uploaded_file and st.button("이미지 번역", key="btn_img"):
        extracted = extract_text_from_image(uploaded_file, api_key)
        st.success(translate_text_with_gemini(extracted, target_lang, api_key))
