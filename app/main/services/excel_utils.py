"""
엑셀 수식 인젝션 방지 유틸리티.
사용자 입력 문자열이 =, +, -, @로 시작하면 수식으로 실행되지 않도록 안전하게 처리.
"""


def sanitize_excel_cell(value: str) -> str:
    """
    엑셀 셀에 저장할 값을 안전하게 sanitization.
    값이 =, +, -, @로 시작하면 작은따옴표(')를 앞에 붙여 수식으로 해석되지 않게 함.
    """
    if not isinstance(value, str):
        return value
    if value and value[0] in ('=', '+', '-', '@'):
        return "'" + value
    return value
