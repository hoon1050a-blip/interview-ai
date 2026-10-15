import streamlit as st
import streamlit.components.v1 as components
import pdfplumber
import google.generativeai as genai
import pandas as pd
import re
import json
import time

st.set_page_config(page_title="생기부 면접 질문 생성기", page_icon="🎓")

# 0. 세션 상태(Session State) 초기화 - 저장 버튼을 눌러도 결과가 날아가지 않도록 보관
if "interview_result" not in st.session_state:
    st.session_state.interview_result = None
if "safe_student_text" not in st.session_state:
    st.session_state.safe_student_text = ""
if "target_title" not in st.session_state:
    st.session_state.target_title = ""

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

# 3. 수식(LaTeX) 및 마크다운 완벽 지원 PDF 저장 컴포넌트
def pdf_download_component(result_text: str, title_prefix: str):
    safe_text = json.dumps(result_text, ensure_ascii=False)
    safe_filename = json.dumps(f"{title_prefix}_면접예상질문.pdf", ensure_ascii=False)
    safe_title = json.dumps(f"{title_prefix} 맞춤형 면접 예상 질문", ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
        <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        
        <style>
            body {{
                font-family: 'Noto Sans KR', sans-serif;
                margin: 0;
                padding: 8px 0;
            }}
            .btn-container {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                align-items: center;
            }}
            .pdf-btn {{
                background-color: #FF4B4B;
                color: white;
                border: none;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 600;
                border-radius: 8px;
                cursor: pointer;
                font-family: 'Noto Sans KR', sans-serif;
                transition: opacity 0.2s;
            }}
            .pdf-btn.print-mode {{
                background-color: #1E3A8A;
            }}
            .pdf-btn:hover {{
                opacity: 0.88;
            }}
            .status-msg {{
                font-size: 13px;
                color: #555;
                margin-left: 5px;
            }}
            /* PDF 내부 디자인 (인용구 박스 및 수식 스타일) */
            #pdf-render-area {{
                display: none;
                padding: 15px 20px;
                color: #111827;
                line-height: 1.65;
                font-size: 11pt;
                background: #ffffff;
            }}
            #pdf-render-area .doc-header {{
                text-align: center;
                font-size: 18pt;
                font-weight: 700;
                color: #1E3A8A;
                border-bottom: 2px solid #1E3A8A;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            #pdf-render-area h3 {{
                color: #1E3A8A;
                font-size: 13pt;
                margin-top: 18px;
                margin-bottom: 8px;
                page-break-after: avoid;
            }}
            #pdf-render-area blockquote {{
                background-color: #F8FAFC;
                border-left: 4px solid #3B82F6;
                margin: 0 0 16px 0;
                padding: 12px 16px;
                border-radius: 4px;
                page-break-inside: avoid;
                break-inside: avoid;
            }}
            #pdf-render-area blockquote p {{
                margin: 6px 0;
            }}
            #pdf-render-area hr {{
                border: 0;
                border-top: 1px solid #E5E7EB;
                margin: 16px 0;
            }}
        </style>
    </head>
    <body>
        <div class="btn-container">
            <button class="pdf-btn" id="dl-btn" onclick="downloadDirectPDF()">📥 면접 질문 PDF 바로 다운로드</button>
            <button class="pdf-btn print-mode" onclick="openPrintPDF()">🖨️ 고화질 PDF 저장 / 인쇄 (긴 문서·수식 권장)</button>
            <span class="status-msg" id="status-text"></span>
        </div>

        <div id="pdf-render-area"></div>

        <script>
            const rawMarkdown = {safe_text};
            const fileName = {safe_filename};
            const docTitle = {safe_title};
            const renderArea = document.getElementById('pdf-render-area');
            const statusText = document.getElementById('status-text');
            const dlBtn = document.getElementById('dl-btn');

            function renderMathAndMarkdown() {{
                renderArea.innerHTML = '<div class="doc-header">' + docTitle + '</div>' + marked.parse(rawMarkdown);
                renderMathInElement(renderArea, {{
                    delimiters: [
                        {{left: '$$', right: '$$', display: true}},
                        {{left: '$', right: '$', display: false}},
                        {{left: '\\\\(', right: '\\\\)', display: false}},
                        {{left: '\\\\[', right: '\\\\]', display: true}}
                    ],
                    throwOnError: false
                }});
            }}

            function downloadDirectPDF() {{
                dlBtn.disabled = true;
                statusText.innerText = "⏳ 수식 렌더링 및 PDF 변환 중입니다 (약 3~5초 소요)...";
                renderMathAndMarkdown();
                renderArea.style.display = 'block';

                const opt = {{
                    margin:       [12, 12, 12, 12],
                    filename:     fileName,
                    image:        {{ type: 'jpeg', quality: 0.98 }},
                    html2canvas:  {{ scale: 2, useCORS: true, scrollY: 0 }},
                    jsPDF:        {{ unit: 'mm', format: 'a4', orientation: 'portrait' }},
                    pagebreak:    {{ mode: ['avoid-all', 'css', 'legacy'] }}
                }};

                html2pdf().set(opt).from(renderArea).save().then(() => {{
                    renderArea.style.display = 'none';
                    statusText.innerText = "✅ PDF 다운로드가 완료되었습니다!";
                    dlBtn.disabled = false;
                }}).catch((err) => {{
                    renderArea.style.display = 'none';
                    statusText.innerText = "⚠️ 변환 중 오류가 발생했습니다. 오른쪽 고화질 저장 버튼을 이용해 주세요.";
                    dlBtn.disabled = false;
                }});
            }}

            function openPrintPDF() {{
                renderMathAndMarkdown();
                const printWin = window.open('', '_blank', 'width=950,height=850');
                printWin.document.write(`
                    <html>
                    <head>
                        <title>${{fileName}}</title>
                        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
                        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
                        <style>
                            body {{ font-family: 'Noto Sans KR', sans-serif; padding: 20px; line-height: 1.65; font-size: 11pt; color: #111827; }}
                            .doc-header {{ text-align: center; font-size: 18pt; font-weight: 700; color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 20px; }}
                            h3 {{ color: #1E3A8A; font-size: 13pt; margin-top: 18px; margin-bottom: 8px; page-break-after: avoid; }}
                            blockquote {{ background-color: #F8FAFC; border-left: 4px solid #3B82F6; margin: 0 0 16px 0; padding: 12px 16px; border-radius: 4px; page-break-inside: avoid; break-inside: avoid; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                            blockquote p {{ margin: 6px 0; }}
                            hr {{ border: 0; border-top: 1px solid #E5E7EB; margin: 16px 0; }}
                        </style>
                    </head>
                    <body>${{renderArea.innerHTML}}</body>
                    </html>
                `);
                printWin.document.close();
                setTimeout(() => {{
                    printWin.focus();
                    printWin.print();
                }}, 600);
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=65)


# ==========================================
# 화면 UI 구성
# ==========================================
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

# 4. 질문 생성 버튼 클릭 시 동작 (결과를 st.session_state에 저장)
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
                model = genai.GenerativeModel('gemini-3.8-flash') 
                
                # 프롬프트 생성 (수식 LaTeX 표기 지침 추가)
                prompt = f"""
                당신은 {university} {major}의 입학사정관입니다.
                아래 [과거 기출문제 및 동향]과 비식별화된 [학생 생활기록부]를 분석하여 전공 적합성을 보여주는 면접 질문 세트 15개를 생성하세요. (메인 질문 15개와 각각의 꼬리 질문을 포함하여 총 30개 이상의 질문을 만드세요.)
                
                주의사항: 절대 인사말이나 서론, 결론을 작성하지 마세요. 
                중요 1: 가독성을 위해 반드시 아래의 [출력 양식]에 기재된 마크다운 인용구(>)와 굵은 글씨(**), 줄바꿈을 정확히 지켜서 15개의 세트를 출력하세요.
                중요 2: 수학·과학 수식이나 기호(함수, 미적분, 극한, 벡터, 행렬, 화학식 등)가 등장할 때는 깨지지 않도록 반드시 표준 LaTeX 수식 문법인 $수식$ 형태로 감싸서 작성하세요.

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
                
                # 간헐적 API 오류(429 한도 초과 등) 방지를 위한 자동 재시도 로직
                max_retries = 3
                retry_delay = 5
                response_text = None
                
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content(prompt)
                        response_text = response.text
                        break
                    except Exception as api_err:
                        if attempt < max_retries - 1:
                            st.toast(f"일시적 지연이 발생하여 {retry_delay}초 후 자동 재시도합니다... ({attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            raise api_err

                # 생성된 결과를 세션 상태에 영구 보관 (저장 버튼을 눌러도 유지됨)
                st.session_state.interview_result = response_text
                st.session_state.safe_student_text = safe_student_text
                st.session_state.target_title = f"{university}_{major}"
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")


# ==========================================
# 5. 결과 출력 및 PDF 다운로드 구역 (버튼 블록 외부에 배치하여 화면 증발 방지)
# ==========================================
if st.session_state.interview_result:
    st.success(f"개인정보 보호 처리가 완료되었습니다. {st.session_state.target_title.replace('_', ' ')} 맞춤형 면접 질문을 출력합니다!")
    
    # 상단에 PDF 저장 버튼 배치 (클릭해도 아래 질문이 절대 사라지지 않음)
    st.markdown("#### 📄 결과 저장하기 (수식·서식 유지)")
    pdf_download_component(
        result_text=st.session_state.interview_result,
        title_prefix=st.session_state.target_title
    )
    
    st.divider()
    
    # 화면에 질문 출력 (스트림릿 자체 마크다운 + 수식 렌더링)
    st.markdown(st.session_state.interview_result)
    
    # 하단에도 편의를 위해 텍스트 백업 다운로드 버튼 유지 (눌러도 화면 초기화 안 됨)
    st.download_button(
        label="📄 일반 텍스트로 백업 다운로드 (.txt)",
        data=st.session_state.interview_result,
        file_name=f"{st.session_state.target_title}_면접예상질문.txt",
        mime="text/plain"
    )
    
    # 비식별화 확인용 토글
    with st.expander("보안 처리된 생기부 텍스트 확인하기 (클릭)"):
        st.text(st.session_state.safe_student_text[:1000] + "\n\n... (중략) ...")
