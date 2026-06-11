(function () {
  function findFormRoot(btn) {
    return btn.closest('.preview-content-holder') || btn.closest('.shrinker-content');
  }

  function wireContactForm(btn) {
    var root = findFormRoot(btn);
    if (!root || !root.querySelector('[name="Name"]')) return;
    if (btn.dataset.paContactWired === '1') return;

    var nameField = root.querySelector('[name="Name"]');
    var emailField = root.querySelector('[name="Email"]');
    var messageField = root.querySelector('[name="Message"]');
    if (!nameField || !emailField || !messageField) return;

    btn.dataset.paContactWired = '1';
    btn.setAttribute('href', '#');
    btn.removeAttribute('target');
    btn.classList.add('pa-contact-send');

    var linksWrap = btn.closest('.preview-item-links');
    var msgDiv = root.querySelector('.pa-contact-msg');
    if (!msgDiv && linksWrap) {
      msgDiv = document.createElement('div');
      msgDiv.className = 'pa-contact-msg';
      linksWrap.insertAdjacentElement('afterend', msgDiv);
    }

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopImmediatePropagation();

      var name = (nameField.value || '').trim();
      var email = (emailField.value || '').trim();
      var message = (messageField.value || '').trim();

      if (!name || !email || !message) {
        if (msgDiv) {
          msgDiv.style.display = 'block';
          msgDiv.style.color = '#ff6b6b';
          msgDiv.textContent = 'Please fill in all fields.';
        }
        return;
      }

      btn.style.opacity = '0.6';
      btn.style.pointerEvents = 'none';
      if (msgDiv) msgDiv.style.display = 'none';

      fetch('/send-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, email: email, message: message })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          btn.style.opacity = '1';
          btn.style.pointerEvents = 'auto';
          if (!msgDiv) return;
          msgDiv.style.display = 'block';
          if (data.ok) {
            if (data.email_sent === false && data.email_error) {
              msgDiv.style.color = '#ffb347';
              msgDiv.textContent = 'Message saved, but email could not be sent. We will follow up soon.';
            } else {
              msgDiv.style.color = '#4caf50';
              msgDiv.textContent = 'Message sent! Thank you.';
            }
            nameField.value = '';
            emailField.value = '';
            messageField.value = '';
          } else {
            msgDiv.style.color = '#ff6b6b';
            msgDiv.textContent = 'Failed to send: ' + (data.error || 'unknown error');
          }
        })
        .catch(function () {
          btn.style.opacity = '1';
          btn.style.pointerEvents = 'auto';
          if (!msgDiv) return;
          msgDiv.style.display = 'block';
          msgDiv.style.color = '#ff6b6b';
          msgDiv.textContent = 'Network error — please try again.';
        });
    }, true);
  }

  function initContactForms() {
    document.querySelectorAll('a[data-link-type="SUBMIT"], a.pa-contact-send, #contact-submit-btn').forEach(wireContactForm);
  }

  window.addEventListener('load', function () {
    initContactForms();
    setTimeout(initContactForms, 300);
    setTimeout(initContactForms, 1200);
  });
})();
