// app.js — 접수 폼 제출 처리 (WP-14-B1)
// Vanilla JS + fetch. React/Babel/CDN 사용 금지.

(function () {
  "use strict";

  var form = document.getElementById("request-form");
  var navToggle = document.getElementById("nav-toggle");
  var appNav = document.getElementById("app-nav");
  if (navToggle && appNav) {
    navToggle.addEventListener("click", function () {
      var expanded = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", String(!expanded));
      navToggle.setAttribute("aria-label", expanded ? "메뉴 열기" : "메뉴 닫기");
      appNav.classList.toggle("is-open", !expanded);
    });
  }

  var detailActions = document.querySelectorAll("[data-status-action]");
  if (detailActions.length) {
    detailActions.forEach(function (button) {
      button.addEventListener("click", function () {
        var statusBox = document.getElementById("detail-status") || document.getElementById("live-status");
        var original = button.textContent;
        button.disabled = true;
        if (statusBox) statusBox.textContent = "상태를 변경하는 중입니다...";
        fetch(button.getAttribute("data-status-url"), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_status: button.getAttribute("data-target-status") }),
        }).then(function (res) {
          if (!res.ok) {
            return res.json().catch(function () { return {}; }).then(function (body) {
              throw new Error(typeof body.detail === "string" ? body.detail : "상태 변경에 실패했습니다.");
            });
          }
          return res.json();
        }).then(function () {
          if (statusBox) statusBox.textContent = "상태가 변경되었습니다. 화면을 새로 고칩니다.";
          window.location.reload();
        }).catch(function (error) {
          if (statusBox) statusBox.textContent = error.message || "네트워크 오류가 발생했습니다.";
          button.disabled = false;
          button.textContent = original;
        });
      });
    });
  }

  if (!form) return;

  var liveStatus = document.getElementById("live-status");
  var submitBtn = document.getElementById("submit-btn");
  var errorAlert = document.getElementById("error-alert");
  var errorAlertMessage = document.getElementById("error-alert-message");
  var errorAlertClose = errorAlert && errorAlert.querySelector(".error-alert__close");

  function setLive(message, kind) {
    if (!liveStatus) return;
    liveStatus.textContent = message;
    liveStatus.classList.remove("is-success", "is-error");
    if (kind === "success") liveStatus.classList.add("is-success");
    if (kind === "error") liveStatus.classList.add("is-error");
  }

  function hideErrorAlert() {
    if (!errorAlert) return;
    errorAlert.setAttribute("aria-hidden", "true");
    if (errorAlertMessage) errorAlertMessage.textContent = "";
  }

  function showErrorAlert(message) {
    if (!errorAlert || !errorAlertMessage) return;
    errorAlertMessage.textContent = message;
    errorAlert.setAttribute("aria-hidden", "false");
    errorAlert.focus();
  }

  function friendlyValidationMessage(detail) {
    if (typeof detail === "string") return "입력한 내용을 확인해 주세요.";
    if (!Array.isArray(detail) || !detail.length) return "입력값을 확인해 주세요.";
    var messages = detail.map(function (item) {
      var field = (item.loc || []).filter(Boolean).pop() || "";
      var text = String(item.msg || "");
      if (/quantity|수량|greater than|positive|non-negative|음수/i.test(field + " " + text)) {
        return "수량은 0 이상으로 입력해 주세요.";
      }
      if (/pickup_date/i.test(field)) {
        return "수거 희망일은 오늘 이후 날짜로 선택해 주세요.";
      }
      if (/date|날짜/i.test(field + " " + text)) {
        return "수거 희망일을 확인해 주세요.";
      }
      if (/required|missing|필수/i.test(text)) return "필수 입력값을 확인해 주세요.";
      if (/business_office_id/i.test(field)) return "사업소를 선택해 주세요.";
      if (/pickup_address/i.test(field)) return "수거 주소를 입력해 주세요.";
      if (/pickup_location_type/i.test(field)) return "장소 유형을 선택해 주세요.";
      return "입력한 내용을 확인해 주세요.";
    });
    return messages.filter(function (message, index) {
      return messages.indexOf(message) === index;
    }).join(" ");
  }

  if (errorAlertClose) errorAlertClose.addEventListener("click", hideErrorAlert);
  if (errorAlert) errorAlert.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      event.preventDefault();
      hideErrorAlert();
    }
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var payload = {
      business_office_id: parseInt(form.business_office_id.value, 10),
      pickup_date: form.pickup_date.value,
      pickup_location_type: form.pickup_location_type.value,
      pickup_address: form.pickup_address.value.trim(),
      electric_bed_quantity: parseInt(form.electric_bed_quantity.value, 10) || 0,
      wheelchair_quantity: parseInt(form.wheelchair_quantity.value, 10) || 0,
      other_small_quantity: parseInt(form.other_small_quantity.value, 10) || 0,
    };

    if (payload.electric_bed_quantity < 0 || payload.wheelchair_quantity < 0 || payload.other_small_quantity < 0) {
      var negativeMessage = "수량은 0 이상으로 입력해 주세요.";
      setLive(negativeMessage, "error");
      showErrorAlert(negativeMessage);
      return;
    }
    if (payload.electric_bed_quantity + payload.wheelchair_quantity + payload.other_small_quantity === 0) {
      var quantityMessage = "품목 수량을 하나 이상 입력해 주세요.";
      setLive(quantityMessage, "error");
      showErrorAlert(quantityMessage);
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    setLive("접수 중입니다...", "info");
    fetch("/api/requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (res.status === 201) {
          return res.json().then(function (data) {
            window.location.assign("/requests/complete/" + data.id);
            return null;
          });
        }
        if (res.status === 422) {
          return res.json().then(function (body) {
            var msg = friendlyValidationMessage(body.detail);
            setLive(msg, "error");
            showErrorAlert(msg);
            return null;
          });
        }
        return res.json().catch(function () { return null; }).then(function () {
          var serverMessage = "접수 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
          setLive(serverMessage, "error");
          showErrorAlert(serverMessage);
          return null;
        });
      })
      .catch(function () {
        var networkMessage = "서버에 연결할 수 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.";
        setLive(networkMessage, "error");
        showErrorAlert(networkMessage);
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  });
})();
