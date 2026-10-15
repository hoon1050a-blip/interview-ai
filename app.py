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
if "token_info" not in st.session_state:
    st.session_state.token_info = None

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
                margin-top: 8px;
                font-size: 13px;
                font-weight: 500;
                color: #374151;
                min-height: 20px;
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
        </div>
        <div class="status-msg" id="status-text"></div>

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
    components.html(html_code, height=100)


# ==========================================
# 화면 UI 구성
# ==========================================
st.title("🎓 생기부 기반 면접 예상 질문 생성기")
st.markdown("학생의 **학교생활기록부 PDF**와 **희망 대학/학과**를 입력하면 과거 사례 기반 맞춤형 면접 질문을 생성합니다. (전송 전 개인정보는 자동 비식별화 처리됩니다.)")
st.caption("하다가 어려운점이 있다면 제작자에게 문의주세요(지족고 송정훈)")

api_key = st.text_input("Gemini API 키를 입력하세요 (무료 키 사용 가능)", type="password")

col1, col2 = st.columns(2)
with col1:
    university = st.text_input("희망 대학", placeholder="예: 한국대학교")
with col2:
    major = st.text_input("모집 단위(학과)", placeholder="예: 수학교육과")

col3, col4 = st.columns(2)
with col3:
    student_name = st.text_input("학생 이름 (생기부 내 이름 가림 처리용)", placeholder="예: 홍길동")
with col4:
    question_count = st.selectbox(
        "생성할 질문 세트 수",
        options=[15, 20, 25, 30],
        index=1,  # 기본값 20세트
        help="질문 수를 20~25개로 늘려도 전체 토큰 소모량은 약 5% 내외만 증가합니다."
    )

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
        with st.spinner(f"생기부 비식별화 및 맞춤형 질문 {question_count}세트 생성 중입니다... 잠시만 기다려주세요."):
            try:
                # 과거 기출 데이터 검색
                past_data_text = ""
                if df is not None:
                    filtered_df = df[df['대학'].str.contains(university, na=False) & df['모집단위'].str.contains(major, na=False)]
                    if not filtered_df.empty:
                        past_data_text = " ".join(filtered_df['기출문제'].astype(str).tolist())
                    else:
                        past_data_text = f"해당 대학/학과의 과거 기출 데이터가 없습니다. 일반적인 {university} {major} 서류 기반 면접 수준에 맞춰 생성해주세요."
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
                model = genai.GenerativeModel(
                    model_name='gemini-3.8-flash',
                    generation_config={"max_output_tokens": 16384}
                )
                
                # 프롬프트 생성 (메인 질문은 생기부 사실/과정 확인 중심, 꼬리질문에서 단계적 검증 지침 강화)
                prompt = f"""
                당신은 {university} {major}의 학생부종합전형(서류 기반) 면접관입니다.
                아래 [과거 기출문제 및 동향]과 비식별화된 [학생 생활기록부]를 분석하여 면접 질문 세트 {question_count}개를 생성하세요.

                [질문 출제 원칙 및 난이도 조절 지침 - 매우 중요]
                1. **메인 질문(Q.)은 반드시 '생기부에 적힌 내용 그 자체'에서만 출제하세요.**
                   - 처음부터 생기부에 없는 외부 개념이나 지나치게 깊은 대학 전공 지식을 물어보는 것을 엄격히 금지합니다.
                   - 메인 질문에서는 생기부에 기록된 활동을 시작하게 된 계기(호기심), 구체적인 탐구 과정 및 방법, 본인이 맡은 역할, 활동 중 겪은 어려움과 해결 과정, 활동을 통해 배우고 느낀 점을 묻는 '서류 사실 확인형 질문'으로 구성하세요.
                2. **심화 탐구 검증은 '꼬리질문(⚡)'에서 단계적으로 진행하세요.**
                   - 학생이 수행한 심화 탐구의 진위 여부나 원리 이해도 검증은 꼬리질문에서 물어보세요.
                   - 단, 꼬리질문 역시 생기부에 학생이 직접 언급한 개념·원리·수식·실험 결과를 고등학교 교육과정 수준에서 제대로 이해하고 썼는지 확인하는 선에서 출제하고, 생기부에 전혀 없는 생소한 대학 전공 이론을 끌어와 묻지 마세요.
                3. **형식 및 수식 규칙:**
                   - 절대 인사말이나 서론, 결론을 작성하지 마세요.
                   - 가독성을 위해 반드시 아래 [출력 양식]의 마크다운 인용구(>)와 굵은 글씨(**), 줄바꿈을 정확히 지켜서 {question_count}개의 세트를 끝까지 출력하세요.
                   - 수학·과학 수식이나 기호(함수, 미적분, 극한, 벡터, 행렬, 화학식 등)가 등장할 때는 반드시 표준 LaTeX 수식 문법인 $수식$ 형태로 감싸서 작성하세요.

                [출력 양식]
                ### 🎯 질문 세트 [번호]
                > 📌 **[출제 근거]**: 활동 영역(자율/동아리/진로/교과목명) - 생기부에 기재된 핵심 활동 요약
                >
                > **Q. (생기부에 적힌 활동 내용·동기·과정·역할을 바탕으로 한 기본 확인 질문)**
                >
                > ⚡ **꼬리질문 및 심화 검증 포인트**: (학생의 답변을 바탕으로 탐구 원리 이해도나 후속 적용을 고교 수준에서 검증하는 꼬리질문 1~2개 작성)
                >
                > 🔑 **필수 답변 키워드**: (학생 답변에 포함되어야 할 핵심 키워드 3~5개를 쉼표로 구분하여 작성)
                
                ---

                [과거 기출문제 및 동향]
                {past_data_text}

                [학생 생활기록부 추출 내용]
                {safe_student_text}
                
                [추가 지시사항]
                학생의 생기부 텍스트에서 '교과 세특'뿐만 아니라 '자율활동', '진로활동', '동아리활동', '행동특성 및 종합의견' 등 다양한 영역의 소재를 골고루 발췌하여 {question_count}개의 질문 세트를 구성하세요.
                """
                
                # 간헐적 API 오류(429 한도 초과 등) 방지를 위한 자동 재시도 로직
                max_retries = 3
                retry_delay = 12
                response = None
                
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content(prompt)
                        break
                    except Exception as api_err:
                        if attempt < max_retries - 1:
                            st.toast(f"일시적 한도 지연이 발생하여 {retry_delay}초 후 자동 재시도합니다... ({attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            raise api_err

                # 토큰 사용량 추출 (usage_metadata)
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_token_count", 0)
                    output_tokens = getattr(usage, "candidates_token_count", 0)
                    total_tokens = getattr(usage, "total_token_count", prompt_tokens + output_tokens)
                    st.session_state.token_info = {
                        "prompt": prompt_tokens,
                        "output": output_tokens,
                        "total": total_tokens
                    }
                else:
                    st.session_state.token_info = None

                # 생성된 결과를 세션 상태에 영구 보관
                st.session_state.interview_result = response.text
                st.session_state.safe_student_text = safe_student_text
                st.session_state.target_title = f"{university}_{major}"
                
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")


# ==========================================
# 5. 결과 출력 및 PDF 다운로드 구역
# ==========================================
if st.session_state.interview_result:
    st.success(f"개인정보 보호 처리가 완료되었습니다. {st.session_state.target_title.replace('_', ' ')} 맞춤형 면접 질문을 출력합니다!")
    
    # 📊 토큰 사용량 표시 구역
    if st.session_state.token_info:
        t_info = st.session_state.token_info
        tpm_percent = round((t_info["total"] / 250000) * 100, 1)
        st.info(
            f"📊 **이번 작업 토큰 소모량:** 총 **{t_info['total']:,} 토큰** "
            f"(입력: {t_info['prompt']:,} / 출력: {t_info['output']:,}) "
            f"— 무료 분당 토큰 한도(25만)의 약 **{tpm_percent}%** 사용"
        )
    
    # 상단에 PDF 저장 버튼 배치
    st.markdown("#### 📄 결과 저장하기 (수식·서식 유지)")
    pdf_download_component(
        result_text=st.session_state.interview_result,
        title_prefix=st.session_state.target_title
    )
    
    st.divider()
    
    # 화면에 질문 출력
    st.markdown(st.session_state.interview_result)
    
    # 하단 텍스트 백업 다운로드 버튼
    st.download_button(
        label="📄 일반 텍스트로 백업 다운로드 (.txt)",
        data=st.session_state.interview_result,
        file_name=f"{st.session_state.target_title}_면접예상질문.txt",
        mime="text/plain"
    )
    
    # 비식별화 확인용 토글
    with st.expander("보안 처리된 생기부 텍스트 확인하기 (클릭)"):
        st.text(st.session_state.safe_student_text[:1000] + "\n\n... (중략) ...")
