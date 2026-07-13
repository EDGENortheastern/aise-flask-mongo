// Live password strength meter for the "Create user" form.
//
// These rules intentionally mirror password_strength.py on the server. The
// server is the real gatekeeper; this script only gives the user instant
// feedback as they type. Keep the two in sync when you change the rules.
(function () {
  "use strict";

  var MIN_LENGTH = 8;

  // Keys match the data-req attributes rendered in new_user.html.
  var RULES = [
    { key: "length", test: function (p) { return p.length >= MIN_LENGTH; } },
    { key: "lowercase", test: function (p) { return /[a-z]/.test(p); } },
    { key: "uppercase", test: function (p) { return /[A-Z]/.test(p); } },
    { key: "digit", test: function (p) { return /\d/.test(p); } },
    { key: "symbol", test: function (p) { return /[^A-Za-z0-9]/.test(p); } },
  ];

  var LABELS = ["Too weak", "Too weak", "Too weak", "Fair", "Good", "Strong"];

  var password = document.getElementById("password");
  var meter = document.querySelector("[data-strength]");
  if (!password || !meter) {
    return;
  }

  var fill = meter.querySelector("[data-strength-fill]");
  var label = meter.querySelector("[data-strength-label]");
  var items = {};
  meter.querySelectorAll("[data-req]").forEach(function (item) {
    items[item.getAttribute("data-req")] = item;
  });

  function update() {
    var value = password.value;

    if (value === "") {
      meter.hidden = true;
      return;
    }
    meter.hidden = false;

    var score = 0;
    RULES.forEach(function (rule) {
      var met = rule.test(value);
      if (met) {
        score += 1;
      }
      var item = items[rule.key];
      if (item) {
        item.classList.toggle("is-met", met);
      }
    });

    var strength = score >= RULES.length ? "strong" : score >= 3 ? "fair" : "weak";
    fill.style.width = (score / RULES.length) * 100 + "%";
    meter.setAttribute("data-level", strength);
    label.textContent = LABELS[score] || "";
  }

  password.addEventListener("input", update);
})();
