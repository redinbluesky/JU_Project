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

function doGet(e) {
  try {
    const params = e && e.parameter ? e.parameter : {};
    if (params.demo !== 'true') return json_({ok: false, error: 'demo_only'});
    if (params.mode === 'list') return listDemoRequests_(params);
    const requestId = String(params.request_id || '');
    const phone = String(params.phone || '');
    if (!/^[A-Za-z0-9_-]{16,80}$/.test(requestId)) return json_({ok: false, error: 'invalid_request_id'});
    if (!/^01[016789]-\d{3,4}-\d{4}$/.test(phone)) return json_({ok: false, error: 'invalid_phone'});
    const cache = CacheService.getScriptCache();
    const rateKey = 'lookup:' + requestId + ':' + phone;
    if (cache.get(rateKey)) return json_({ok: false, error: 'too_many_requests'});
    cache.put(rateKey, '1', 2);

    const sheet = getSheet_();
    if (sheet.getLastRow() < 2) return json_({ok: true, found: false});
    const rows = sheet.getRange(2, 2, sheet.getLastRow() - 1, 8).getValues();
    const row = rows.find(function (values) { return String(values[0]) === requestId && String(values[2]) === phone; });
    if (!row) return json_({ok: true, found: false});
    return json_({ok: true, found: true, data: {
      request_id: String(row[0]), applicant_name: String(row[1]), phone: String(row[2]),
      office: String(row[3]), pickup_date: normalizeDate_(row[4]), address: String(row[5]), products: String(row[6]),
      kakao_notify: String(row[7]) === 'Y'
    }});
  } catch (error) {
    return json_({ok: false, error: error.message || 'invalid_request'});
  }
}

function listDemoRequests_(params) {
  const from = String(params.from || '');
  const to = String(params.to || '');
  const office = String(params.office || '전체');
  const status = String(params.status || '전체');
  if (from && !/^\d{4}-\d{2}-\d{2}$/.test(from)) return json_({ok: false, error: 'invalid_from'});
  if (to && !/^\d{4}-\d{2}-\d{2}$/.test(to)) return json_({ok: false, error: 'invalid_to'});
  if (from && to && from > to) return json_({ok: false, error: 'invalid_date_range'});
  if (office.length > 100 || status.length > 30) return json_({ok: false, error: 'invalid_filter'});
  const page = Math.max(1, Math.min(1000, Number(params.page || 1)));
  const pageSize = Math.max(1, Math.min(50, Number(params.page_size || 20)));
  if (!Number.isInteger(page) || !Number.isInteger(pageSize)) return json_({ok: false, error: 'invalid_pagination'});
  const cache = CacheService.getScriptCache();
  const rateKey = 'list:' + [from, to, office, status, page, pageSize].join('|');
  if (cache.get(rateKey)) return json_({ok: false, error: 'too_many_requests'});
  cache.put(rateKey, '1', 2);
  const sheet = getSheet_();
  if (sheet.getLastRow() < 2) return json_({ok: true, items: [], total: 0, page: page, page_size: pageSize, has_more: false});
  const rows = sheet.getRange(2, 2, sheet.getLastRow() - 1, 8).getValues();
  const filtered = rows.filter(function (row) {
    const pickupDate = normalizeDate_(row[4]);
    const rowOffice = String(row[3]);
    return (!from || pickupDate >= from) && (!to || pickupDate <= to) &&
      (office === '전체' || rowOffice.indexOf(office) === 0) && (status === '전체' || status === '접수');
  });
  const start = (page - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize).map(function (row) {
    return {request_id: String(row[0]), office: String(row[3]), pickup_date: String(row[4]), status: '접수'};
  });
  return json_({ok: true, items: items, total: filtered.length, page: page, page_size: pageSize, has_more: start + pageSize < filtered.length});
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
    const applicantName = sanitizeCell_(payload.applicant_name);
    const phone = sanitizeCell_(payload.phone);
    const address = sanitizeCell_(payload.address);
    const rowValues = [
      new Date(), sanitizeCell_(payload.request_id), applicantName, phone,
      sanitizeCell_(payload.office), sanitizeCell_(payload.pickup_date), address,
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
  if (!payload.applicant_name || typeof payload.applicant_name !== 'string' || payload.applicant_name.length > 80) throw new Error('invalid_applicant_name');
  if (!/^01[016789]-\d{3,4}-\d{4}$/.test(String(payload.phone || ''))) throw new Error('invalid_phone');
  if (!payload.address || typeof payload.address !== 'string' || payload.address.length > 300) throw new Error('invalid_address');
  if (!payload.office || typeof payload.office !== 'string' || payload.office.length > 100) throw new Error('invalid_office');
  if (!Array.isArray(payload.products) || payload.products.length < 1 || payload.products.length > 20) throw new Error('invalid_products');
  payload.products.forEach(function (item) {
    if (!item || typeof item.name !== 'string' || item.name.length > 100) throw new Error('invalid_product');
    if (!['대여', '구매'].includes(item.rental_purchase)) throw new Error('invalid_rental_purchase');
    if (!Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 5) throw new Error('invalid_quantity');
  });
}

function normalizeDate_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return Utilities.formatDate(value, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  const text = String(value == null ? '' : value).trim();
  const iso = text.match(/^(\d{4}-\d{2}-\d{2})/);
  if (iso) return iso[1];
  const parsed = new Date(text);
  return isNaN(parsed.getTime()) ? '' : Utilities.formatDate(parsed, Session.getScriptTimeZone(), 'yyyy-MM-dd');
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
