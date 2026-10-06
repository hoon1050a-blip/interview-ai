import streamlit as st
import pdfplumber
import google.generativeai as genai
import pandas as pd
import re

st.set_page_config(page_title="생기부 면접 질문 생성기", page_icon="🎓")

# 1. 깃허브에 올린 CSV 데이터 자동 불러오기
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("interview_data_extracted.csv") 
        return df
    except Exception as e:
        return None

df = load_data()

# 2. 개인정보 비식별화(마스킹) 함수
def mask_personal_info(text, student_name=""):
    # 주민등록번호 마스킹
    text = re.sub(r'\d{6}[-\s]*[1-4]\d{6}', '******-*******', text)
    
    # 전화번호 마스킹
    text = re.sub(r'01[016789][-\s]*\d{3,4}[-\s]*\d{4}', '010-****-****', text)
    
    # 이메일 마스킹
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '***@***.***', text)
    
    # 학생 이름 마스킹 (입력된 경우)
    if student_name and len(student_name) >= 2:
        text = text.replace(student_name, "OOO")
        
    return text

st.title("🎓 생기부 기반 면접 예상 질문 생성기")
st.markdown("학생의 **학교생활기록부 PDF**와 **희망 대학/학과**를 입력하면 과거 사례 기반 맞춤형 면접 질문을 생성합니다. (전송 전 개인정보는 자동 비식별화 처리됩니다.)")

api_key = st.text_input("Gemini API 키를 입력하세요 (무료 키 사용 가능)", type="password")

col1, col2 = st.columns(2)
with col1:
    university = st.text_input("희망 대학", placeholder="예: 한국대학교")
with col2:
    major = st.text_input("모집 단위(학과)", placeholder="예: 수학교육과")

student_name = st.text_input("학생 이름 (생기부 내 이름 가림 처리용)", placeholder="예: 홍길동")

uploaded_file = st.file_uploader("학생 생기부 PDF 파일 업로드", type="pdf")
pdf_password = st.text_input("PDF 비밀번호 (나이스 생기부는 보통 생년월일 6자리, 없으면 비워둠)", type="password")

if st.button("면접 예상 질문 생성하기"):
    if not api_key:
        st.warning("API 키를 입력해주세요.")
    elif not uploaded_file:
        st.warning("PDF 파일을 업로드해주세요.")
    elif not university or not major:
        st.warning("희망 대학과 학과를 입력해주세요.")
    else:
        with st.spinner("생기부 비식별화 및 AI 분석을 진행 중입니다... 잠시만 기다려주세요."):
            try:
                # 과거 기출 데이터 검색
                past_data_text = ""
                if df is not None:
                    filtered_df = df[df['대학'].str.contains(university, na=False) & df['모집단위'].str.contains(major, na=False)]
                    if not filtered_df.empty:
                        past_data_text = " ".join(filtered_df['기출문제'].astype(str).tolist())
                    else:
                        past_data_text = f"해당 대학/학과의 과거 기출 데이터가 없습니다. 일반적인 {university} {major} 면접 수준에 맞춰 생성해주세요."
                else:
                    past_data_text = "데이터베이스(CSV)를 찾을 수 없습니다."

                # PDF 텍스트 추출
                raw_student_text = ""
                with pdfplumber.open(uploaded_file, password=pdf_password if pdf_password else None) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            raw_student_text += page_text + "\n"
                
                # 추출된 텍스트에서 개인정보 비식별화(마스킹) 실행
                safe_student_text = mask_personal_info(raw_student_text, student_name)
                
                # AI 설정 및 호출
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-3.7-flash') 
                
                # 프롬프트 생성 (15세트 생성 및 전 영역 반영 지시사항 추가)
               # 4. 프롬프트 생성 (마크다운 가독성 및 15세트 생성 지시사항 추가)
                prompt = f"""
                당신은 {university} {major}의 입학사정관입니다.
                아래 [과거 기출문제 및 동향]과 비식별화된 [학생 생활기록부]를 분석하여 전공 적합성을 보여주는 면접 질문 세트 15개를 생성하세요. (메인 질문 15개와 각각의 꼬리 질문을 포함하여 총 30개 이상의 질문을 만드세요.)
                
                주의사항: 절대 인사말이나 서론, 결론을 작성하지 마세요. 
                중요: 가독성을 위해 반드시 아래의 [출력 양식]에 기재된 마크다운 인용구(>)와 굵은 글씨(**), 줄바꿈을 정확히 지켜서 15개의 세트를 출력하세요.

                [출력 양식]
                ### 🎯 질문 세트 [번호]
                > 📌 **[출제 근거]**: 활동 영역(자율/동아리/진로/교과목명) - 활동 요약
                >
                > **Q. (여기에 생기부 기반 메인 질문 작성)**
                >
                > ⚡ **꼬리질문 공격 포인트**: (여기에 꼬리질문의 의도와 후속 질문 1~2개 작성)
                >
                > 🔑 **필수 답변 키워드**: (여기에 학생 답변에 포함되어야 할 핵심 키워드 3~5개를 쉼표로 구분하여 작성)
                
                ---

                [과거 기출문제 및 동향]
                {past_data_text}

                [학생 생활기록부 추출 내용]
                {safe_student_text}
                
                [추가 지시사항]
                학생의 생기부 텍스트에서 '교과 세특'뿐만 아니라 '자율활동', '진로활동', '동아리활동' 등 다양한 영역의 소재를 골고루 발췌하여 15개의 질문 세트를 구성하세요.
                """
                
                response = model.generate_content(prompt)
                st.success(f"개인정보 보호 처리가 완료되었습니다. {university} {major} 맞춤형 면접 질문을 출력합니다!")
                
                # 화면에 질문 출력
                st.markdown(response.text)
                
                # ==========================================
                # 📥 다운로드 버튼 추가 구역
                # ==========================================
                st.download_button(
                    label="📥 생성된 면접 질문 다운로드 (.txt)",
                    data=response.text,
                    file_name=f"{university}_{major}_면접예상질문.txt",
                    mime="text/plain"
                )
                
                # 비식별화 확인용 토글
                with st.expander("보안 처리된 생기부 텍스트 확인하기 (클릭)"):
                    st.text(safe_student_text[:1000] + "\n\n... (중략) ...")
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
