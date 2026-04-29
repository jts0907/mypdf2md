import streamlit as st
import pdfplumber
import io

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
st.caption("한글(HWP)에서 PDF로 저장한 문서 또는 PDF파일을 마크다운 텍스트로 변환합니다. 사용된 도구는 오픈소스 도구: pdfplumber 입니다. by eonow687")

st.info("💡 **사용 방법**: (HWP파일)한컴오피스에서 HWP 파일을 열고 → 다른 이름으로 저장 → PDF로 저장 → 아래에 업로드, (PDF파일) 별도 단계 필요없이 아래에 업로드")

uploaded_file = st.file_uploader(
    "PDF 파일을 업로드하세요",
    type=["pdf"],
    help="텍스트 기반 PDF만 지원합니다. 스캔 이미지 PDF는 변환되지 않습니다.",
)

if uploaded_file:
    with st.spinner("변환 중..."):
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
                    )

                # 파일명 설정
                original_name = uploaded_file.name.rsplit(".", 1)[0]
                download_name = f"{original_name}.md"

                st.download_button(
                    label="📥 마크다운 파일 다운로드 (.md)",
                    data=md_text.encode("utf-8"),
                    file_name=download_name,
                    mime="text/markdown",
                )

        except Exception as e:
            st.error(f"변환 중 오류 발생: {e}")
