"""정적 신청자·관리자 목업의 회귀 방지 검증."""
from pathlib import Path


ROOT = Path("docs/20-design")


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_both_mockups_are_responsive_at_375px():
    for name in ("pc-applicant-info.html", "admin-login.html"):
        html = _read(name)
        assert 'content="width=device-width, initial-scale=1"' in html
        assert "min-width:1280px" not in html
        assert "@media (max-width: 959px)" in html


def test_applicant_verification_is_invalidated_when_phone_or_code_changes():
    js = _read("pc-applicant-info.html")
    assert 'phoneInput.addEventListener("input"' in js
    assert 'certCodeInput.addEventListener("input"' in js
    assert "certVerified = false" in js
    assert "confirmBtn.disabled = true" in js


def test_pickup_date_requires_two_business_days():
    js = _read("pc-applicant-info.html")
    assert "function minimumPickupDate" in js
    assert "getDay()" in js
    assert "pickupDate.setAttribute(\"min\"" in js
    assert "최소 2영업일 이후" in js
    assert "수거 희망일은 신청일 기준 최소 2영업일 이후" in js


def test_product_picker_has_confirm_cancel_and_fixed_categories():
    html = _read("pc-applicant-info.html")
    assert 'data-category="전체"' in html
    assert 'data-category="의자"' in html
    assert 'data-category="침대"' in html
    assert 'data-category="보조차"' in html
    assert 'data-category="보행기"' in html
    assert 'id="product-picker"' in html
    assert 'id="product-picker-cancel"' in html
    assert 'id="product-picker-confirm"' in html


def test_product_picker_enforces_quantity_boundaries_and_deduplicates():
    js = _read("pc-applicant-info.html")
    assert "MAX_PRODUCT_QUANTITY = 5" in js
    assert "value < 1 || value > MAX_PRODUCT_QUANTITY" in js
    assert "draftProducts.set(key" in js
    assert "selectedProducts.delete(key" in js
    assert "합계 수량" in js


def test_minimum_date_uses_local_calendar_not_utc_conversion():
    js = _read("pc-applicant-info.html")
    assert "function formatLocalDate" in js
    assert "getFullYear()" in js
    assert "getMonth() + 1" in js
    assert "getDate()" in js
    assert "formatLocalDate(minimumDate)" in js
    assert "toISOString().slice(0, 10)" not in js


def test_category_buttons_open_picker_and_initial_table_has_two_blank_rows():
    html = _read("pc-applicant-info.html")
    assert 'id="open-product-picker"' not in html
    assert 'id="selected-products-body"' in html
    assert 'class="placeholder-row"' in html
    assert html.count('class="placeholder-row"') == 2
    js = _read("pc-applicant-info.html")
    assert "category-tab" in js
    assert "picker.hidden = false" in js


def test_selected_rows_have_quantity_stepper_with_zero_delete_and_max_five():
    html = _read("pc-applicant-info.html")
    assert "수량 줄이기" in html
    assert "수량 늘리기" in html
    js = _read("pc-applicant-info.html")
    assert "quantity <= 0" in js
    assert "quantity >= MAX_PRODUCT_QUANTITY" in js
    assert "plusButton.disabled" in js
