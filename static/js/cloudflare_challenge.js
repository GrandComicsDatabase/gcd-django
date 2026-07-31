/*
 * Detect Cloudflare Challenge Pages returned to jQuery AJAX calls.
 *
 * A Challenge Page contains HTML instead of the JSON expected by
 * autocomplete controls.  The verification link opens the challenged
 * request in another tab so that this tab keeps its unsaved form data.
 */
(function(window, document, $) {
  'use strict';

  // This template can be included more than once on a page.
  if (!$ || window.gcdCloudflareChallengeHandlerInstalled) {
    return;
  }
  window.gcdCloudflareChallengeHandlerInstalled = true;

  const bannerId = 'cloudflare_challenge_notice';

  function challengeUrl(requestUrl) {
    try {
      const url = new URL(requestUrl, window.location.href);
      // Do not open a third-party URL supplied by an AJAX request.
      if (url.origin === window.location.origin) {
        return url.href;
      }
    } catch (error) {
      // Use the current page when the request URL cannot be parsed.
    }
    return window.location.href;
  }

  function showChallengeNotice(requestUrl) {
    let notice = document.getElementById(bannerId);
    if (notice) {
      notice.querySelector('a').href = challengeUrl(requestUrl);
      return;
    }

    notice = document.createElement('div');
    notice.id = bannerId;
    notice.className = 'cloudflare_challenge_notice';
    notice.setAttribute('role', 'alert');

    const message = document.createElement('span');
    message.textContent = 'Cloudflare verification is required. ';
    notice.appendChild(message);

    const verifyLink = document.createElement('a');
    verifyLink.href = challengeUrl(requestUrl);
    verifyLink.target = '_blank';
    verifyLink.rel = 'noopener';
    verifyLink.textContent = 'Verify in a new tab';
    notice.appendChild(verifyLink);

    const instructions = document.createElement('span');
    instructions.textContent = ', close that tab, then retry this field. ' +
      'Your unsaved changes will remain here.';
    notice.appendChild(instructions);

    document.body.appendChild(notice);
  }

  $(document).ajaxComplete(function(event, xhr, settings) {
    // Cloudflare sets this header on every Challenge Page response.
    const mitigation = xhr.getResponseHeader('cf-mitigated');
    if (mitigation && mitigation.toLowerCase() === 'challenge') {
      showChallengeNotice(settings.url);
    }
  });
})(window, document, window.jQuery);
