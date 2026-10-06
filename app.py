import streamlit as st
import pdfplumber
import google.generativeai as genai

# 웹 페이지 탭 제목 설정
st.set_page_config(page_title="생기부 면접 질문 생성기", page_icon="🎓")

# 1. 화면 구성: 제목 및 안내 문구 (st.title 사용)
st.title("🎓 생기부 기반 면접 예상 질문 생성기")
st.markdown("학생의 **학교생활기록부 PDF**와 **희망 대학/학과**를 입력하면 과거 사례 기반 맞춤형 면접 질문을 생성합니다.")

# 2. 보안을 위해 API 키를 웹 화면에서 직접 입력받도록 구성
api_key = st.text_input("Gemini API 키를 입력하세요 (AQ...로 시작)", type="password")

# 3. 입력 창 구성 (st.text_input, st.file_uploader 등 사용)
col1, col2 = st.columns(2)
with col1:
    university = st.text_input("희망 대학", placeholder="예: 한국대학교")
with col2:
    major = st.text_input("모집 단위(학과)", placeholder="예: 수학교육과")

past_data = st.text_area(
    "과거 면접 기출 동향 및 특징", 
    placeholder="수학적 원리(기하, 미적분)를 실생활이나 타 교과에 융합한 사례를 깊게 물어봄..."
)

uploaded_file = st.file_uploader("학생 생기부 PDF 파일 업로드", type="pdf")
pdf_password = st.text_input("PDF 비밀번호 (나이스 생기부는 보통 생년월일 6자리, 없으면 비워둠)", type="password")

# 4. 실행 버튼 구성 (st.button 사용)
if st.button("면접 예상 질문 생성하기"):
    # 필수 입력값 확인
    if not api_key:
        st.warning("API 키를 입력해주세요.")
    elif not uploaded_file:
        st.warning("PDF 파일을 업로드해주세요.")
    elif not university or not major:
        st.warning("희망 대학과 학과를 입력해주세요.")
    else:
        # 로딩 스피너 작동
        with st.spinner("생기부를 분석하고 질문을 생성 중입니다. 잠시만 기다려주세요..."):
            try:
                # API 연결
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-3.7-flash') 
                
                # PDF 텍스트 추출 로직
                student_record_text = ""
                with pdfplumber.open(uploaded_file, password=pdf_password if pdf_password else None) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            student_record_text += page_text + "\n"
                
                # 프롬프트 설계 (이전 단계에서 수정한 양식 그대로 적용)
                prompt = f"""
                당신은 {university} {major}의 입학사정관입니다.
                아래 [과거 기출문제]와 [학생 생활기록부]를 분석하여 이공계열(수학, 기하 등) 역량을 보여주는 면접 질문 5개를 생성하세요.
                
                주의사항: 절대 인사말이나 서론, 결론을 작성하지 마세요. 오직 아래의 [출력 양식]에 정확히 맞춰서 5개의 세트만 반복하여 출력하세요.

                [출력 양식]
                📌 [출제 근거]: 학년 과목명 - 활동 요약
                Q. (여기에 생기부 기반 메인 질문 작성)
                ⚡ 꼬리질문 공격 포인트: (여기에 꼬리질문의 의도와 후속 질문 작성)
                🔑 필수 답변 키워드: (여기에 학생 답변에 포함되어야 할 핵심 키워드 3~5개를 쉼표로 구분하여 작성)

                [과거 기출문제 및 면접 평가 기준]
                {past_data}

                [학생 생활기록부 추출 내용]
                {student_record_text}
                """
                
                # API 호출 및 결과 화면 출력
                response = model.generate_content(prompt)
                st.success("면접 질문 생성이 완료되었습니다!")
                
                # 결과를 웹 화면에 예쁘게 출력
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")