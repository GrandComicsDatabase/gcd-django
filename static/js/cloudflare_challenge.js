/*
 * Detect Cloudflare Challenge Pages returned to jQuery AJAX calls.
 *
 * A Challenge Page contains HTML instead of the JSON expected by
 * autocomplete controls.  The base template provides a translated
 * notice that this script reveals when verification is required.
 */
(function(window, document, $) {
  'use strict';

  // This template can be included more than once on a page.
  if (!$ || window.gcdCloudflareChallengeHandlerInstalled) {
    return;
  }
  window.gcdCloudflareChallengeHandlerInstalled = true;

  const bannerId = 'cloudflare_challenge_notice';

  function showChallengeNotice() {
    const notice = document.getElementById(bannerId);
    if (!notice) {
      return;
    }

    const verifyLink = notice.querySelector('a');
    if (!verifyLink) {
      return;
    }
    notice.classList.remove('hidden');
  }

  $(document).ajaxComplete(function(event, xhr, settings) {
    if (!xhr || typeof xhr.getResponseHeader !== 'function') {
      return;
    }
    // Cloudflare sets this header on every Challenge Page response.
    const mitigation = xhr.getResponseHeader('cf-mitigated');
    if (mitigation && mitigation.toLowerCase() === 'challenge') {
      showChallengeNotice();
    }
  });
})(window, document, window.jQuery);
