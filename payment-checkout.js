(function() {
  var statusEl = document.getElementById('status');
  var selectionEl = document.getElementById('pa-uc-selection');
  var retryBtn = document.getElementById('pa-retry-btn');
  var raw = sessionStorage.getItem('pa_uc_checkout');
  if (!raw) {
    statusEl.textContent = 'Checkout session expired. Please start again from the course page.';
    statusEl.className = 'error';
    return;
  }
  var session;
  try { session = JSON.parse(raw); } catch (e) {
    statusEl.textContent = 'Invalid checkout session.';
    statusEl.className = 'error';
    return;
  }
  if (!session.order_id) {
    statusEl.textContent = 'Missing order. Please start again from the course page.';
    statusEl.className = 'error';
    return;
  }

  var activeClient = null;
  var activeCheckout = null;

  function parseJwt(token) {
    var seg = token.split('.')[1];
    if (!seg) return {};
    var pad = '='.repeat((4 - seg.length % 4) % 4);
    return JSON.parse(atob(seg.replace(/-/g, '+').replace(/_/g, '/') + pad));
  }

  function setError(msg, showRetry) {
    statusEl.textContent = msg;
    statusEl.className = 'error';
    retryBtn.style.display = showRetry ? 'block' : 'none';
  }

  function saveSession() {
    sessionStorage.setItem('pa_uc_checkout', JSON.stringify(session));
  }

  async function refreshCaptureContext() {
    statusEl.className = '';
    statusEl.textContent = 'Preparing secure payment…';
    var resp = await fetch('/api/refresh-capture-context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_id: session.order_id,
        // Must match window.location.origin exactly or Cybersource throws UNUSED_TARGET_ORIGINS
        origin: window.location.origin
      })
    });
    var d = await resp.json();
    if (!d.ok || !d.capture_context) {
      throw new Error(d.error || 'Could not prepare payment session');
    }
    session.capture_context = d.capture_context;
    saveSession();
    return session.capture_context;
  }

  function loadScript(src, integrity) {
    return new Promise(function(resolve, reject) {
      var existing = document.querySelector('script[data-pa-uc="1"]');
      if (existing) existing.remove();
      var s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.setAttribute('data-pa-uc', '1');
      if (integrity) {
        s.integrity = integrity;
        s.crossOrigin = 'anonymous';
      }
      s.onload = resolve;
      s.onerror = function() { reject(new Error('Failed to load payment library')); };
      document.head.appendChild(s);
    });
  }

  function extractLibrary(jwt) {
    var decoded = parseJwt(jwt);
    if (decoded.ctx && decoded.ctx.length > 0 && decoded.ctx[0].data) {
      return {
        lib: decoded.ctx[0].data.clientLibrary,
        integrity: decoded.ctx[0].data.clientLibraryIntegrity
      };
    }
    if (decoded.data) {
      return {
        lib: decoded.data.clientLibrary,
        integrity: decoded.data.clientLibraryIntegrity
      };
    }
    return { lib: null, integrity: null };
  }

  async function teardownWidget() {
    try {
      if (activeCheckout) await activeCheckout.destroy();
    } catch (e) {}
    try {
      if (activeClient) activeClient.destroy();
    } catch (e) {}
    activeCheckout = null;
    activeClient = null;
    selectionEl.innerHTML = '';
    var existing = document.querySelector('script[data-pa-uc="1"]');
    if (existing) existing.remove();
    if (window.VAS) {
      try { delete window.VAS; } catch (e) { window.VAS = undefined; }
    }
  }

  function normalizePaymentResult(result) {
    if (result == null) return '';
    if (typeof result === 'string') return result;
    if (typeof result === 'object') {
      if (typeof result.jwt === 'string') return result.jwt;
      if (typeof result.token === 'string') return result.token;
      if (typeof result.transientTokenJwt === 'string') return result.transientTokenJwt;
      return JSON.stringify(result);
    }
    return String(result);
  }

  function assertPaymentResult(jwt) {
    var decoded = parseJwt(jwt);
    var status = String(decoded.status || decoded.outcome || '').toUpperCase();
    if (status && status !== 'AUTHORIZED' && status !== 'CAPTURED') {
      throw new Error(status);
    }
    var details = decoded.details || {};
    var proc = details.processorInformation || {};
    var reason = String(proc.responseCode || decoded.reasonCode || '').trim();
    if (reason && reason !== '00' && reason !== '100' && reason !== '110') {
      var n = parseInt(reason, 10);
      if (!isNaN(n) && n >= 200) {
        throw new Error('DECLINED');
      }
    }
    return jwt;
  }

  function errorReason(err) {
    if (!err) return 'unknown';
    if (err.reason) return err.reason;
    if (err.message) return err.message;
    if (typeof err === 'string') return err;
    try { return JSON.stringify(err); } catch (e) { return 'unknown'; }
  }

  async function runCheckout(isRetry) {
    retryBtn.style.display = 'none';
    try {
      await teardownWidget();
      var jwt = await refreshCaptureContext();
      var libInfo = extractLibrary(jwt);
      if (!libInfo.lib) {
        setError('Payment configuration error (missing client library).', true);
        return;
      }
      await loadScript(libInfo.lib, libInfo.integrity);
      if (!window.VAS || !window.VAS.UnifiedCheckout) {
        setError('Payment widget unavailable.', true);
        return;
      }
      activeClient = await window.VAS.UnifiedCheckout(jwt);
      activeCheckout = await activeClient.createCheckout({ autoProcessing: true });
      statusEl.className = 'hidden';
      var result = await activeCheckout.mount({ paymentSelection: '#pa-uc-selection' });
      var paymentResult = normalizePaymentResult(result);
      if (!paymentResult) {
        setError('Payment did not return a result. Click Try again.', true);
        await teardownWidget();
        return;
      }
      if (paymentResult.split('.').length === 3) {
        try {
          paymentResult = assertPaymentResult(paymentResult);
        } catch (preErr) {
          setError('Payment was declined. Please try again or use another card.', true);
          await teardownWidget();
          return;
        }
      }
      statusEl.className = '';
      statusEl.textContent = 'Processing payment…';
      var resp = await fetch('/api/payment-complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_id: session.order_id,
          email: session.email,
          result: paymentResult
        })
      });
      var d = await resp.json();
      if (d.ok && d.redirect) {
        sessionStorage.removeItem('pa_uc_checkout');
        window.location.href = d.redirect;
        return;
      }
      setError(d.error || 'Payment could not be confirmed. Please contact support.', true);
      await teardownWidget();
    } catch (err) {
      var reason = errorReason(err);
      if (!isRetry && (reason === 'CAPTURE_CONTEXT_EXPIRED' || reason.indexOf('CAPTURE_CONTEXT') >= 0)) {
        try {
          return runCheckout(true);
        } catch (refreshErr) {
          setError('Payment session expired. Click Try again or go back to the course page.', true);
          return;
        }
      }
      if (reason === 'CHECKOUT_CANCELLED' || reason === 'PAYMENT_CANCELLED') {
        setError('Payment cancelled. Click Try again to restart.', true);
      } else if (reason.indexOf('CAPTURE_CONTEXT') >= 0) {
        setError('Payment session expired. Click Try again or go back to the course page.', true);
      } else {
        setError('Payment error (' + reason + '). Click Try again.', true);
      }
      await teardownWidget();
    }
  }

  retryBtn.addEventListener('click', function() {
    runCheckout(false);
  });

  runCheckout(false);
})();
