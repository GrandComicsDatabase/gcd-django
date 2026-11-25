// Image upload card (templates/oi/bits/image_upload_card.html): preview of
// the selected or dropped image, with its dimensions and, where the card
// sets a minimum size, a warning below it.
/**
 * Wires one upload card.
 * @param {HTMLElement} card the element with data-image-upload
 */
function setupImageUpload(card) {
  'use strict';

  // Only raster images are opened in a new tab: an SVG opened as a
  // same-origin document could run scripts.
  const RASTER = ['image/jpeg', 'image/png', 'image/gif', 'image/webp',
                  'image/bmp', 'image/avif'];

  const scanInput = card.querySelector('input[type=file]');
  // The element highlighted while a file is dragged over it.
  const section = card.closest('[data-dragging]') || card;
  if (!scanInput || !window.DataTransfer) {
    return;
  }
  const choose = card.querySelector('[data-upload=choose]');
  const selected = card.querySelector('[data-upload=selected]');
  const scanOpen = card.querySelector('[data-upload=open]');
  const scanPreview = card.querySelector('[data-upload=preview]');
  const scanName = card.querySelector('[data-upload=name]');
  const scanInfo = card.querySelector('[data-upload=info]');
  const scanWarning = card.querySelector('[data-upload=warning]');
  const changeButton = card.querySelector('[data-upload=change]');
  // Set only where the card has a minimum size.
  const minShortSide = Number(card.dataset.minShortSide);
  let scanUrl = null;
  let shownFile = null;

  /**
   * Returns the class names listed in a data attribute of the element.
   * @param {HTMLElement} element
   * @param {string} name the attribute's key in `dataset`
   * @returns {string[]}
   */
  function classes(element, name) {
    return (element.dataset[name] || '').split(' ').filter(Boolean);
  }

  /**
   * Shows or hides the element, toggling the display classes listed in its
   * `data-shown` attribute.
   * @param {HTMLElement} element
   * @param {boolean} visible
   */
  function show(element, visible) {
    element.classList.toggle('hidden', !visible);
    classes(element, 'shown').forEach(function (className) {
      element.classList.toggle(className, visible);
    });
  }

  /**
   * Formats a file size in KB or MB.
   * @param {number} bytes
   * @returns {string}
   */
  function formatSize(bytes) {
    return bytes < 1024 * 1024 ? Math.round(bytes / 1024) + ' KB' :
           (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  /**
   * Puts the file in the scan input, as if it had been selected.
   * @param {File} file
   */
  function setFile(file) {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    scanInput.files = transfer.files;
  }

  scanInput.addEventListener('change', function () {
    // Some browsers empty the input when the picker is cancelled: the shown
    // file stays selected until another one is chosen.
    if (!scanInput.files.length && shownFile) {
      setFile(shownFile);
      return;
    }
    if (scanUrl) {
      URL.revokeObjectURL(scanUrl);
      scanUrl = null;
    }
    const file = scanInput.files[0];
    shownFile = file || null;
    show(choose, !file);
    show(selected, Boolean(file));
    if (!file) {
      return;
    }
    scanName.textContent = file.name;
    scanInfo.textContent = formatSize(file.size);
    if (scanWarning) {
      show(scanWarning, false);
    }
    const raster = RASTER.includes(file.type);
    // Files without a MIME type (e.g. an unknown extension) are previewed,
    // since an img does not run scripts, but not opened in a new tab.
    const previewed = raster || !file.type;
    show(scanOpen, previewed);
    scanOpen.disabled = !raster;
    if (!previewed) {
      return;
    }
    const url = URL.createObjectURL(file);
    scanUrl = url;
    scanPreview.onload = function () {
      const width = scanPreview.naturalWidth;
      const height = scanPreview.naturalHeight;
      scanInfo.textContent = width + ' x ' + height + ' pixels, ' +
                             formatSize(file.size);
      if (scanWarning) {
        show(scanWarning, Math.min(width, height) < minShortSide);
      }
    };
    // The browser cannot decode the image; it can still be uploaded.
    scanPreview.onerror = function () {
      if (scanUrl !== url) {
        return;
      }
      URL.revokeObjectURL(url);
      scanUrl = null;
      show(scanOpen, false);
      scanInfo.textContent = 'This browser cannot show the image; it can ' +
                             'still be uploaded (' + formatSize(file.size) +
                             ').';
    };
    scanPreview.src = url;
  });

  // Open the full-size image in a new tab.
  scanOpen.addEventListener('click', function () {
    if (scanUrl) {
      window.open(scanUrl, '_blank');
    }
  });

  // Open the picker; the current file is kept if none is chosen.
  changeButton.addEventListener('click', function () {
    scanInput.click();
  });

  // Highlight the card while a file is dragged over it.
  ['dragenter', 'dragover'].forEach(function (type) {
    section.addEventListener(type, function (event) {
      event.preventDefault();
      section.classList.add.apply(section.classList,
                                  classes(section, 'dragging'));
    });
  });
  ['dragleave', 'drop'].forEach(function (type) {
    section.addEventListener(type, function (event) {
      if (type === 'drop' || !section.contains(event.relatedTarget)) {
        section.classList.remove.apply(section.classList,
                                       classes(section, 'dragging'));
      }
    });
  });
  // Take a dropped file as if it had been selected; the server validates it.
  section.addEventListener('drop', function (event) {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) {
      setFile(file);
      scanInput.dispatchEvent(new Event('change'));
    }
  });

  // Restore the preview of a file the browser kept, e.g. after going back.
  if (scanInput.files.length) {
    scanInput.dispatchEvent(new Event('change'));
  }
}

// Wire the cards once the page is parsed.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-image-upload]').forEach(setupImageUpload);
});
