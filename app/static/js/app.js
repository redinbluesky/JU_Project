// app.js — 접수 폼 제출 처리 (WP-14-B1)
// Vanilla JS + fetch. React/Babel/CDN 사용 금지.

(function () {
  "use strict";

  var form = document.getElementById("request-form");

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

  function setLive(message, kind) {
    if (!liveStatus) return;
    liveStatus.textContent = message;
    liveStatus.classList.remove("is-success", "is-error");
    if (kind === "success") liveStatus.classList.add("is-success");
    if (kind === "error") liveStatus.classList.add("is-error");
  }

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
            setLive("접수 완료: " + data.request_no, "success");
            form.reset();
            return null;
          });
        }
        if (res.status === 422) {
          return res.json().then(function (body) {
            var detail = body.detail;
            var msg;
            if (typeof detail === "string") {
              msg = detail;
            } else if (Array.isArray(detail) && detail.length > 0) {
              msg = detail.map(function (d) {
                var field = (d.loc || []).filter(Boolean).join(".");
                return field ? field + ": " + d.msg : d.msg;
              }).join(" / ");
            } else {
              msg = "입력값을 확인해 주세요.";
            }
            setLive(msg, "error");
            return null;
          });
        }
        // 그 외 오류
        return res.json().catch(function () { return null; }).then(function (body) {
          var d = body && body.detail;
          setLive(typeof d === "string" ? d : "접수 처리 중 오류가 발생했습니다.", "error");
          return null;
        });
      })
      .catch(function () {
        setLive("네트워크 오류: 서버에 연결할 수 없습니다.", "error");
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  });
})();
