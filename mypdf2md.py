import logging

import streamlit as st
import pdfplumber
import io

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


# ── PDF → 마크다운 변환 ───────────────────────────────────────
def pdf_to_markdown(uploaded_file) -> str:
    md_lines = []

    with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
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


# ── UI ────────────────────────────────────────────────────────
st.title("📄 PDF → 마크다운 변환기")
st.caption("- 한글(HWP)에서 PDF로 저장한 문서 또는 기존 PDF파일을 마크다운 텍스트로 변환합니다.")

# ── 보안 경고 ────────────────────────────────────────────────
st.warning(
    "**🔒 보안 안내 — 공개 자료 전용**\n\n"
    "이 변환기는 외부 클라우드 서버(Streamlit)에서 동작하며, 업로드한 파일은 "
    "변환 처리 과정에서 외부 서버 메모리를 거칩니다.\n\n"
    "- ✅ **사용 가능**: 이미 공개된 자료 (의안정보시스템상 의안, 공포된 법령·고시, 판례, 헌재결정례, 보도자료, 공개 간행물 등)\n"
    "- ❌ **사용 금지**: 비공개·내부 검토 문서, 개인정보가 포함된 문서\n\n"
    "공개 자료 여부가 조금이라도 불확실하면 업로드하지 마십시오. "
    "업로드 시 발생하는 책임은 사용자에게 있습니다.",
    icon="⚠️",
)

st.markdown("""
<div style='background-color:#f0f2f6; padding:14px 18px; border-radius:8px; margin-bottom:16px; display:inline-block;'>
<b>📌 사용 방법</b><br>
① <b>HWP 파일</b>: 한컴오피스에서 열기 → 다른 이름으로 저장 → PDF로 저장<br>
② <b>PDF 파일</b>: 아래 업로드 버튼으로 바로 업로드<br>
③ <b>복수 파일</b>: Ctrl(또는 Shift)을 누른 상태로 여러 파일 동시 선택 가능 (파일당 최대 200MB, 한 번에 10개 이내 권장)
</div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "PDF 파일을 업로드하세요 (여러 파일 동시 선택 가능)",
    type=["pdf"],
    accept_multiple_files=True,
    help="텍스트 기반 PDF만 지원합니다. 스캔 이미지 PDF는 변환되지 않습니다.",
)

if uploaded_files:
    st.info(f"📂 {len(uploaded_files)}개 파일 선택됨")
    for uploaded_file in uploaded_files:
        st.divider()
        st.subheader(f"📄 {uploaded_file.name}")
        with st.spinner(f"{uploaded_file.name} 변환 중..."):
            try:
                md_text = pdf_to_markdown(uploaded_file)

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
            except Exception:
                # 상세 오류는 서버 로그에만 기록 (화면에는 예외 객체를 노출하지 않음)
                logger.exception("PDF 변환 실패: %s", uploaded_file.name)
                st.error("변환 중 오류가 발생했습니다. 텍스트 기반 PDF인지 확인 후 다시 시도해 주세요.")
st.divider()
st.markdown("""
<div style='text-align:right; color:gray; font-size:0.8em;'>
오픈소스 도구 <b>pdfplumber</b> 활용 &nbsp;|&nbsp; 제작: <b>eonow687</b> &nbsp;|&nbsp; 2026.06.08 업데이트
</div>
""", unsafe_allow_html=True)
