// Cover upload form: preview of the selected or dropped scan, with its
// dimensions and a warning if it is below the minimum size.
(function () {
  'use strict';

  const MIN_SHORT_SIDE = 400;
  // Only raster images are opened in a new tab: an SVG opened as a
  // same-origin document could run scripts.
  const RASTER = ['image/jpeg', 'image/png', 'image/gif', 'image/webp',
                  'image/bmp', 'image/avif'];

  const scanInput = document.getElementById('id_scan');
  const section = document.getElementById('scan_section');
  if (!scanInput || !section || !window.DataTransfer) {
    return;
  }
  const choose = document.getElementById('scan_choose');
  const selected = document.getElementById('scan_selected');
  const scanOpen = document.getElementById('scan_open');
  const scanPreview = document.getElementById('scan_preview');
  const scanName = document.getElementById('scan_name');
  const scanInfo = document.getElementById('scan_info');
  const scanWarning = document.getElementById('scan_warning');
  const changeButton = document.getElementById('scan_change');
  let scanUrl = null;

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

  scanInput.addEventListener('change', function () {
    if (scanUrl) {
      URL.revokeObjectURL(scanUrl);
      scanUrl = null;
    }
    const file = scanInput.files[0];
    show(choose, !file);
    show(selected, Boolean(file));
    if (!file) {
      return;
    }
    scanName.textContent = file.name;
    scanInfo.textContent = formatSize(file.size);
    show(scanWarning, false);
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
      show(scanWarning, Math.min(width, height) < MIN_SHORT_SIDE);
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

  changeButton.addEventListener('click', function () {
    scanInput.value = '';
    scanInput.dispatchEvent(new Event('change'));
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
      const transfer = new DataTransfer();
      transfer.items.add(file);
      scanInput.files = transfer.files;
      scanInput.dispatchEvent(new Event('change'));
    }
  });

  // Restore the preview of a file the browser kept, e.g. after going back.
  if (scanInput.files.length) {
    scanInput.dispatchEvent(new Event('change'));
  }
}());
