import streamlit as st
import pdfplumber
import google.generativeai as genai
import pandas as pd

st.set_page_config(page_title="생기부 면접 질문 생성기", page_icon="🎓")

# 1. CSV 데이터 자동 불러오기 (캐싱 적용으로 속도 향상)
@st.cache_data
def load_data():
    try:
        # 방금 추출한 CSV 파일명 적용
        df = pd.read_csv("interview_data_extracted.csv") 
        return df
    except Exception as e:
        return None

df = load_data()

st.title("🎓 생기부 기반 면접 예상 질문 생성기")
st.markdown("학생의 **학교생활기록부 PDF**와 **희망 대학/학과**를 입력하면 과거 사례 기반 맞춤형 면접 질문을 생성합니다.")

api_key = st.text_input("Gemini API 키를 입력하세요 (AQ...로 시작)", type="password")

col1, col2 = st.columns(2)
with col1:
    university = st.text_input("희망 대학", placeholder="예: 건국대학교")
with col2:
    major = st.text_input("모집 단위(학과)", placeholder="예: 수학교육과")

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
        with st.spinner("기출 데이터를 검색하고 생기부를 분석 중입니다... 잠시만 기다려주세요."):
            try:
                # 2. 입력한 대학/학과로 과거 기출 데이터 검색
                past_data_text = ""
                if df is not None:
                    # 데이터베이스에서 대학명과 모집단위가 포함된 데이터 필터링
                    filtered_df = df[df['대학'].str.contains(university, na=False) & df['모집단위'].str.contains(major, na=False)]
                    
                    if not filtered_df.empty:
                        past_data_text = " ".join(filtered_df['기출문제'].astype(str).tolist())
                    else:
                        past_data_text = f"해당 대학/학과의 과거 기출 데이터가 없습니다. 일반적인 {university} {major} 면접 수준에 맞춰 생성해주세요."
                else:
                    past_data_text = f"데이터베이스 파일(CSV)을 찾을 수 없습니다. 일반적인 {university} {major} 면접 수준에 맞춰 생성해주세요."

                # 3. AI 설정 및 PDF 추출
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-3.7-flash') 
                
                student_record_text = ""
                with pdfplumber.open(uploaded_file, password=pdf_password if pdf_password else None) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            student_record_text += page_text + "\n"
                
                # 4. 프롬프트 생성 (검색된 과거 데이터를 AI에게 전달)
                prompt = f"""
                당신은 {university} {major}의 입학사정관입니다.
                아래 [과거 기출문제 및 동향]과 [학생 생활기록부]를 분석하여 이공계열(수학, 기하 등) 역량을 보여주는 면접 질문 5개를 생성하세요.
                
                주의사항: 절대 인사말이나 서론, 결론을 작성하지 마세요. 오직 아래의 [출력 양식]에 정확히 맞춰서 5개의 세트만 반복하여 출력하세요.

                [출력 양식]
                📌 [출제 근거]: 학년 과목명 - 활동 요약
                Q. (여기에 생기부 기반 메인 질문 작성)
                ⚡ 꼬리질문 공격 포인트: (여기에 꼬리질문의 의도와 후속 질문 작성)
                🔑 필수 답변 키워드: (여기에 학생 답변에 포함되어야 할 핵심 키워드 3~5개를 쉼표로 구분하여 작성)

                [과거 기출문제 및 동향]
                {past_data_text}

                [학생 생활기록부 추출 내용]
                {student_record_text}
                """
                
                response = model.generate_content(prompt)
                st.success(f"{university} {major} 맞춤형 면접 질문 생성이 완료되었습니다!")
                
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
