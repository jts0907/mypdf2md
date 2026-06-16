import logging 

import streamlit as st
import pdfplumber
import io
import zipfile
 
# ── 로깅 설정 ────────────────────────────────────────────────
# 상세 오류(traceback)는 서버 로그에만 기록하고, 사용자 화면에는 노출하지 않는다.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="PDF → 마크다운 변환기",
    page_icon="📄",
    layout="wide",
)
 
# ── 글로벌 스타일 ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
 
/* 전체 폰트 */
html, body, [class*="css"], .stMarkdown, .stButton, .stDownloadButton {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}
 
/* 상단 햄버거 메뉴·기본 푸터 정리 */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
 
/* 본문 폭 제한 + 여백 (wide 레이아웃에서 산만함 제거) */
.block-container {
    max-width: 1080px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}
 
/* 헤더 밴드 */
.app-header {
    border-left: 5px solid #2b4c7e;
    padding: 6px 0 6px 18px;
    margin-bottom: 4px;
}
.app-title {
    font-size: 2.0rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #1a2740;
    line-height: 1.25;
}
.app-sub {
    font-size: 0.95rem;
    color: #6b7280;
    margin-top: 4px;
}
 
/* 카드 공통 */
.card {
    border-radius: 10px;
    padding: 16px 20px;
    margin: 14px 0;
    font-size: 0.92rem;
    line-height: 1.7;
}
.card-warn {
    background: #fff8e6;
    border: 1px solid #f0d18a;
    border-left: 4px solid #e0a800;
}
.card-warn b { color: #8a6d00; }
 
/* 결과 영역 소제목 */
.result-name {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1a2740;
    margin: 4px 0 8px 0;
}
 
/* 다운로드 버튼 강조 */
.stDownloadButton button {
    background: #2b4c7e;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 8px 18px;
}
.stDownloadButton button:hover {
    background: #21395f;
    color: #ffffff;
}
 
/* 푸터 크레딧 */
.app-footer {
    text-align: right;
    color: #9aa1ab;
    font-size: 0.78rem;
    margin-top: 8px;
}
</style>
""", unsafe_allow_html=True)
 
 
# ── 표 → 마크다운 변환 ────────────────────────────────────────
def table_to_markdown(table: list) -> str:
    if not table or not table[0]:
        return ""
 
    # None 셀을 빈 문자열로 처리
    rows = [[cell.strip().replace("\n", " ") if cell else "" for cell in row] for row in table]
 
    col_count = max(len(row) for row in rows)
 
    # 열 수 맞추기
    rows = [row + [""] * (col_count - len(row)) for row in rows]
 
    header = rows[0]
    separator = ["---"] * col_count
    body = rows[1:]
 
    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(separator) + " |")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
 
    return "\n".join(lines)
 
 
# ── PDF → 마크다운 변환 (파일 내용 기준 캐싱) ──────────────────
# 같은 파일은 한 번만 변환하고, 이후 재실행(버튼 클릭·익스팬더 토글 등)에서는
# 캐시된 결과를 재사용한다. 입력이 bytes라 내용이 같으면 캐시 적중.
@st.cache_data(show_spinner=False, max_entries=50)
def pdf_to_markdown(file_bytes: bytes) -> str:
    md_lines = []
 
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        total_pages = len(pdf.pages)
 
        for page_num, page in enumerate(pdf.pages, start=1):
            # 표 영역 bbox 수집
            tables = page.find_tables()
            table_bboxes = [t.bbox for t in tables]
 
            # 표가 있는 영역의 텍스트는 별도 처리
            def is_in_table(bbox):
                x0, top, x1, bottom = bbox
                for tb in table_bboxes:
                    if x0 >= tb[0] - 2 and top >= tb[1] - 2 and x1 <= tb[2] + 2 and bottom <= tb[3] + 2:
                        return True
                return False
 
            # 표 제외 텍스트 추출
            if table_bboxes:
                words = page.extract_words()
                non_table_words = [w for w in words if not is_in_table(
                    (w["x0"], w["top"], w["x1"], w["bottom"])
                )]
                # 줄 단위로 재구성
                lines_dict = {}
                for w in non_table_words:
                    line_key = round(w["top"])
                    if line_key not in lines_dict:
                        lines_dict[line_key] = []
                    lines_dict[line_key].append(w["text"])
                text_lines = [" ".join(words_in_line) for _, words_in_line in sorted(lines_dict.items())]
                page_text = "\n".join(text_lines)
            else:
                page_text = page.extract_text() or ""
 
            # 텍스트 추가
            if page_text.strip():
                md_lines.append(page_text.strip())
 
            # 표 추가
            for table in tables:
                data = table.extract()
                if data:
                    md_lines.append("")
                    md_lines.append(table_to_markdown(data))
                    md_lines.append("")
 
            # 페이지 구분 (마지막 페이지 제외)
            if page_num < total_pages:
                md_lines.append("\n---\n")
 
    return "\n".join(md_lines)
 
 
# ── 헤더 ──────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="app-title">📄 PDF → 마크다운 변환기</div>
  <div class="app-sub">한글(HWP)에서 PDF로 저장한 문서 또는 기존 PDF를 마크다운 텍스트로 변환합니다.</div>
</div>
""", unsafe_allow_html=True)
 
# ── 보안 경고 (항상 노출) ─────────────────────────────────────
st.markdown("""
<div class="card card-warn">
<b>⚠️ 🔒 보안 안내 — 공개 자료 전용</b><br>
이 변환기는 외부 클라우드 서버(Streamlit)에서 동작하며, 업로드한 파일은 변환 처리 과정에서 외부 서버 메모리를 거칩니다.<br><br>
✅ <b>사용 가능</b>: 이미 공개된 자료 (의안정보시스템상 의안, 공포된 법령·고시, 판례, 헌재결정례, 보도자료, 공개 간행물 등)<br>
❌ <b>사용 금지</b>: 비공개·내부 검토 문서, 개인정보가 포함된 문서<br><br>
공개 자료 여부가 조금이라도 불확실하면 업로드하지 마십시오. 업로드 시 발생하는 책임은 사용자에게 있습니다.
</div>
""", unsafe_allow_html=True)
 
# ── 사용 방법 (접이식) ────────────────────────────────────────
with st.expander("📌 사용 방법", expanded=False):
    st.markdown("""
- **HWP 파일**: 한컴오피스에서 열기 → 다른 이름으로 저장 → PDF로 저장
- **PDF 파일**: 아래 업로드 버튼으로 바로 업로드
- **복수 파일**: Ctrl(또는 Shift)을 누른 상태로 여러 파일 동시 선택 가능 *(파일당 최대 200MB, 한 번에 10개 이내 권장)*
""")
 
# ── 업로더 ────────────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "PDF 파일을 업로드하세요 (여러 파일 동시 선택 가능)",
    type=["pdf"],
    accept_multiple_files=True,
    help="텍스트 기반 PDF만 지원합니다. 스캔 이미지 PDF는 변환되지 않습니다.",
)
 
if uploaded_files:
    st.info(f"📂 {len(uploaded_files)}개 파일 선택됨")
    results = []  # (download_name, md_text) — ZIP 일괄 다운로드용 누적
    for uploaded_file in uploaded_files:
        st.divider()
        st.markdown(f'<div class="result-name">📄 {uploaded_file.name}</div>', unsafe_allow_html=True)
        with st.spinner(f"{uploaded_file.name} 변환 중..."):
            try:
                md_text = pdf_to_markdown(uploaded_file.getvalue())
 
                if not md_text.strip():
                    st.error("텍스트를 추출할 수 없습니다. 스캔 이미지 PDF이거나 텍스트가 없는 파일일 수 있습니다.")
                else:
                    st.success(f"변환 완료 ({len(md_text):,}자)")
 
                    col1, col2 = st.columns(2)
 
                    with col1:
                        st.subheader("미리보기")
                        st.markdown(md_text[:3000] + ("..." if len(md_text) > 3000 else ""))
 
                    with col2:
                        st.subheader("원문 텍스트")
                        st.text_area(
                            label="마크다운 원문",
                            value=md_text,
                            height=500,
                            label_visibility="collapsed",
                            key=f"textarea_{uploaded_file.name}",
                        )
 
                    # 파일명 설정 (원본 PDF 파일명 그대로 사용)
                    original_name = uploaded_file.name.rsplit(".", 1)[0]
                    download_name = f"{original_name}.md"
 
                    st.download_button(
                        label=f"📥 {download_name} 다운로드",
                        data=md_text.encode("utf-8"),
                        file_name=download_name,
                        mime="text/markdown",
                        key=f"download_{uploaded_file.name}",
                    )
 
                    results.append((download_name, md_text))
            except Exception:
                # 상세 오류는 서버 로그에만 기록 (화면에는 예외 객체를 노출하지 않음)
                logger.exception("PDF 변환 실패: %s", uploaded_file.name)
                st.error("변환 중 오류가 발생했습니다. 텍스트 기반 PDF인지 확인 후 다시 시도해 주세요.")
 
    # ── ZIP 일괄 다운로드 (성공 2건 이상일 때만 노출) ──────────────
    if len(results) >= 2:
        used_names = set()
 
        def _unique_name(name: str) -> str:
            # ZIP 내부 파일명 충돌 방지 (동일 파일명 입력 시 _2, _3 ... 부여)
            if name not in used_names:
                used_names.add(name)
                return name
            base = name[:-3] if name.endswith(".md") else name
            i = 2
            while f"{base}_{i}.md" in used_names:
                i += 1
            new_name = f"{base}_{i}.md"
            used_names.add(new_name)
            return new_name
 
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, text in results:
                zf.writestr(_unique_name(name), text.encode("utf-8"))
 
        st.divider()
        st.download_button(
            label=f"📦 전체 Markdown ZIP 다운로드 ({len(results)}개)",
            data=zip_buffer.getvalue(),
            file_name="converted_markdown.zip",
            mime="application/zip",
            key="download_zip_all",
        )
 
st.divider()
st.markdown("""
<div class="app-footer">
오픈소스 도구 <b>pdfplumber</b> 활용 &nbsp;|&nbsp; 제작: <b>eonow687</b> &nbsp;|&nbsp; 2026.06.08 업데이트
</div>
""", unsafe_allow_html=True)
<div class="app-footer">
오픈소스 도구 <b>pdfplumber</b> 활용 &nbsp;|&nbsp; 제작: <b>eonow687</b> &nbsp;|&nbsp; 2026.06.08 업데이트
</div>
""", unsafe_allow_html=True)
