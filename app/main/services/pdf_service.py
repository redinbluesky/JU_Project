"""WP-09 소독완료 이후 PDF 다운로드 서비스.

reportlab 로 접수 PDF 를 생성한다.

- 디폴트 출력: 프로젝트 루트 runtime/pdf/ (개발 실행 시 실제 PDF 생성 위치)
- 테스트는 generate_request_pdf(request, out_dir=tmp_path) 로 출력 경로를 주입
- 문서에는 '기술 프로토타입 - 공단 제출용 아님' 표시와 접수번호, 현재 상태 포함
- 외부 공유 URL / 만료 / 취소 기능은 미구현 (1단계 범위 외)
- 한글 렌더링용 TTF 를 시스템에서 찾으면 등록하고, 없으면 Helvetica 로 대체
  (Title 메타데이터에는 폰트와 무관하게 notice 문자열이 항상 기록됨)
"""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.main.models.models import Request

# 문서 상단에 반드시 표시할 프로토타입 안내 문구
PROTOTYPE_NOTICE = "기술 프로토타입 - 공단 제출용 아님"

# 한글 렌더링용 TTF 후보 (OS 기본 설치 위치). 순서대로 존재하는 것 사용.
_KR_FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "malgun.ttf"),
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "NotoSansKR-VF.ttf"),
    "/System/Library/Fonts/AppleSDGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


def _project_root() -> Path:
    """프로젝트 루트: app/main/services/pdf_service.py → 상위 3단계."""
    return Path(__file__).resolve().parents[3]


def _default_pdf_dir() -> Path:
    """개발 실행 디폴트 PDF 출력 디렉터리: runtime/pdf/."""
    return _project_root() / "runtime" / "pdf"


def _kr_font_name() -> str:
    """한글 TTF 를 등록해 반환. 없으면 Helvetica (Title 메타는 무관)."""
    for cand in _KR_FONT_CANDIDATES:
        if cand and os.path.isfile(cand):
            try:
                pdfmetrics.getFont("Malgun")
            except KeyError:
                pdfmetrics.registerFont(TTFont("Malgun", cand))
            return "Malgun"
    return "Helvetica"


def generate_request_pdf(request: Request, out_dir: Path | str | None = None) -> Path:
    """접수 PDF 를 생성하고 파일 경로를 반환한다.

    - out_dir 지정 시 그 디렉터리, 미지정 시 runtime/pdf/
    - 파일명: {request_no}.pdf (request_no 고유 → 덮어쓰기 안전)
    - pageCompression=0 (비압축, 프로토타입 표시 검증 용이)
    """
    out = Path(out_dir) if out_dir is not None else _default_pdf_dir()
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{request.request_no}.pdf"

    font = _kr_font_name()
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=0)
    c.setTitle(PROTOTYPE_NOTICE)
    c.setAuthor("ju-prototype")
    c.setCreator("ju-prototype")

    # 상단 프로토타입 표시
    c.setFont(font, 11)
    c.drawString(72, 780, PROTOTYPE_NOTICE)
    c.setStrokeColorRGB(0.6, 0.2, 0.2)
    c.line(72, 772, 540, 772)

    c.setFont(font, 15)
    c.drawString(72, 740, "위탁소독 접수서")

    rows = [
        ("접수번호", request.request_no),
        ("현재 상태", request.current_status.value),
        ("사업소 ID", str(request.business_office_id)),
        ("수거희망일", str(request.pickup_date)),
        ("수거 유형", request.pickup_location_type.value),
        ("수거 주소", request.pickup_address),
        ("전동침대 수량", str(request.electric_bed_quantity)),
        ("휠체어 수량", str(request.wheelchair_quantity)),
        ("기타 소형 수량", str(request.other_small_quantity)),
    ]
    if request.completion_date is not None:
        rows.append(("완료일", str(request.completion_date)))

    y = 700
    c.setFont(font, 11)
    for label, value in rows:
        c.drawString(72, y, label)
        c.drawString(240, y, str(value))
        y -= 24

    c.save()
    return path
