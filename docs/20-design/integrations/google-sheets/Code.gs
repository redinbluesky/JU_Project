/**
 * 가상 데이터 전용 Google Sheets 데모 수신기.
 * 배포 전 이 파일을 사용자 계정의 대상 스프레드시트 Apps Script에 복사하세요.
 */
const DEMO_ONLY = true;
const SHEET_NAME = '접수 데이터';
const HEADERS = ['접수시각', 'request_id', '신청자', '연락처', '사업소', '수거희망일', '주소', '품목', '알림동의'];

function json_(body) {
  return ContentService.createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000);
    if (!e || !e.postData || !e.postData.contents) return json_({ok: false, error: 'empty_payload'});
    const payload = JSON.parse(e.postData.contents);
    validate_(payload);

    const sheet = getSheet_();
    const requestIds = sheet.getLastRow() > 1
      ? sheet.getRange(2, 2, sheet.getLastRow() - 1, 1).getValues().flat().map(String)
      : [];
    if (requestIds.includes(payload.request_id)) return json_({ok: true, duplicate: true, request_id: payload.request_id});

    const safeProducts = payload.products.map(function (item) {
      return sanitizeCell_(item.name) + ' (' + item.rental_purchase + ') x' + item.quantity;
    }).join(', ');
    const rowValues = [
      new Date(), sanitizeCell_(payload.request_id), '데모 신청자', '010-0000-0000',
      sanitizeCell_(payload.office), sanitizeCell_(payload.pickup_date), '광주광역시 데모 주소',
      safeProducts, payload.kakao_notify === true ? 'Y' : 'N'
    ];
    sheet.appendRow(rowValues);
    const rowNumber = sheet.getLastRow();
    const savedValues = sheet.getRange(rowNumber, 2, 1, rowValues.length - 1).getValues()[0];
    const expectedValues = rowValues.slice(1).map(String);
    const actualValues = savedValues.map(String);
    if (actualValues.some(function (value, index) { return value !== expectedValues[index]; })) {
      throw new Error('row_write_verification_failed');
    }
    return json_({ok: true, duplicate: false, request_id: payload.request_id, row: rowNumber});
  } catch (error) {
    return json_({ok: false, error: error.message || 'invalid_request'});
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

function validate_(payload) {
  if (!DEMO_ONLY || payload.demo !== true) throw new Error('demo_only');
  if (!/^[A-Za-z0-9_-]{16,80}$/.test(String(payload.request_id || ''))) throw new Error('invalid_request_id');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(payload.pickup_date || ''))) throw new Error('invalid_pickup_date');
  if (!payload.office || typeof payload.office !== 'string' || payload.office.length > 100) throw new Error('invalid_office');
  if (!Array.isArray(payload.products) || payload.products.length < 1 || payload.products.length > 20) throw new Error('invalid_products');
  payload.products.forEach(function (item) {
    if (!item || typeof item.name !== 'string' || item.name.length > 100) throw new Error('invalid_product');
    if (!['대여', '구매'].includes(item.rental_purchase)) throw new Error('invalid_rental_purchase');
    if (!Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 5) throw new Error('invalid_quantity');
  });
}

function sanitizeCell_(value) {
  const text = String(value == null ? '' : value);
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function getSheet_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = spreadsheet.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) sheet.appendRow(HEADERS);
  return sheet;
}
