// Cover upload form: the cover taken with the camera. As document scanners
// do, the camera is live in a full-screen view, a worker finds the cover in
// its frames and the photo can be taken once it is all in view, near,
// faced, lit, without glare, still and sharp. One press, and the camera's
// photo, turned as the video shows the scene, goes to the worker, and the
// cover straightened and trimmed goes to the form as a file chosen would,
// where cover_upload.js shows it; the camera goes on, for the photo to be
// taken again if wanted.
(function () {
  'use strict';

  const scanInput = document.getElementById('id_scan');
  const startButton = document.getElementById('capture_start');
  const captureView = document.getElementById('capture_view');
  if (!scanInput || !startButton || !captureView || !captureView.showModal ||
      !window.DataTransfer || !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia || !window.Worker ||
      !window.OffscreenCanvas) {
    return;
  }
  // the camera running, if any
  let capture = null;
  // the last photo, shown small on the video
  let lastUrl = null;

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
   * Adds or removes the class names listed in a data attribute of the element.
   * @param {HTMLElement} element
   * @param {string} name the attribute's key in `dataset`
   * @param {boolean} on
   */
  function toggleClasses(element, name, on) {
    classes(element, name).forEach(function (className) {
      element.classList.toggle(className, on);
    });
  }

  /**
   * Shows or hides the element, toggling the display classes listed in its
   * `data-shown` attribute.
   * @param {HTMLElement} element
   * @param {boolean} visible
   */
  function show(element, visible) {
    element.classList.toggle('hidden', !visible);
    toggleClasses(element, 'shown', visible);
  }

  /**
   * Puts the file in the form's scan input and fires its change event, as a
   * file chosen by the user would; cover_upload.js then shows it.
   * @param {File} file
   */
  function selectScan(file) {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    scanInput.files = transfer.files;
    scanInput.dispatchEvent(new Event('change'));
  }

  const video = document.getElementById('capture_video');
  const overlay = document.getElementById('capture_overlay');
  const captureStatus = document.getElementById('capture_status');
  const shootButton = document.getElementById('capture_shoot');
  const switchButton = document.getElementById('capture_switch');
  const cancelButton = document.getElementById('capture_cancel');
  const flash = document.getElementById('capture_flash');
  const lastButton = document.getElementById('capture_last');
  const lastImage = document.getElementById('capture_last_image');
  // the long side of the copies of the frames the worker checks
  const FRAME_LONG_SIDE = 640;
  // what to do for the first check the frame fails (see the worker)
  const HINTS = {
    found: 'Show all of the cover, flat, on a background that stands out ' +
           'from it.',
    inView: 'Keep all of the cover in view.',
    near: 'Come closer: let the cover fill the view.',
    faced: 'Hold the camera parallel to the cover.',
    lit: 'More light is needed.',
    noGlare: 'Glare on the cover: tilt it a little or move the light.',
    still: 'Hold still.',
    sharp: 'Focusing...'
  };
  // the checks that pass and fail from one frame to the next as the hand
  // shakes or the focus moves: while only they fail, "Take photo" stays
  // enabled. A press takes the photo with the first frame that passes all
  // the checks, however long it takes.
  const PASSING = {still: true, sharp: true};
  // a hint is shown once it holds for this many frames in a row, so that
  // the status, read out by screen readers, does not change with each one
  const HINT_FRAMES = 3;
  // the worker's failures on this many frames in a row stop the capture
  const FRAME_FAILURES = 10;
  // a photo that comes out blurred is taken again by itself, at most this
  // many times in a row
  const RETAKES = 2;
  // no event tells that a camera hangs, as one did for a minute after its
  // system service had crashed. A camera that has not answered in SILENT_MS
  // is said not to answer, and the page goes on waiting for it until it is
  // closed; a photo, or the camera's photo sizes, not come in PHOTO_WAIT ms
  // give way to the video, as where the browser takes no photos.
  const SILENT_MS = 10000;
  const PHOTO_WAIT = 5000;
  // what takePhoto gives where the camera took no photo with the video at
  // LIVE, and the video was raised for the next one
  const RAISED = 'raised';
  // browsers turn the video as the screen turns, not always the photo: on
  // a convertible held upright the video came 2160 x 3840 and the photo
  // 4160 x 3120. The photo is turned the quarter turns whose centre, cut to
  // the frame's proportions (the video is the middle of the sensor), looks
  // most like the frame the checks passed on: their grey levels, evened out
  // and MATCH_SIDE px on the long side, correlate best.
  const MATCH_SIDE = 48;
  // the pixels a comic book needs on its long side at 300 dpi: 10.25 inches
  // for a US comic book. A camera where a cover filling COVER_SHARE of the
  // long side of its largest photo, or video, gets fewer is left out.
  const PIXELS_NEEDED = 3075;
  const COVER_SHARE = 0.9;
  // the largest native mode up to 4K: where the browser takes no photos,
  // or smaller ones, the photo is a frame of it
  const VIDEO = {
    width: {ideal: 3840}, height: {ideal: 2160}, frameRate: {ideal: 30},
    resizeMode: {ideal: 'none'}
  };
  // where the browser takes photos at least as large as the camera's
  // largest video, the video is only seen and checked, at LIVE: on synthetic
  // streams in a Windows convertible's browser the checks ran on 13 frames
  // a second at 1080p and 2.5 at 4K, which held the page up for up to
  // 0.2 s at a time
  const LIVE = {
    width: {ideal: 1920}, height: {ideal: 1080}, frameRate: {ideal: 30},
    resizeMode: {ideal: 'none'}
  };
  // a USB camera may send its largest size compressed (MJPEG) at full speed
  // and uncompressed only at a lower rate, as the bus allows. So where the
  // frames show JPEG's 8 px blocks, the camera's slower native mode at the
  // same size is tried, down to SLOW_RATE frames a second, and kept if its
  // frames have none. Blocks are measured on BLOCK_FRAMES frames, over a
  // central square of up to BLOCK_SIDE px, as the mean gradient across
  // block borders over the one across block middles, a simplified form of
  // Wu and Yuen's block-edge impairment metric (1997). Uncompressed frames
  // gave 0.99 to 1.01 (a 720p webcam at 10 fps, a 4K tablet camera), MJPEG
  // ones 1.32 to 1.44; under BLOCK_TEXTURE levels of mean gradient across
  // block middles the view is too dark or plain to tell.
  const SLOW_RATE = 10;
  const BLOCKY = 1.15;
  const BLOCK_FRAMES = 3;
  const BLOCK_SIDE = 640;
  const BLOCK_TEXTURE = 1;

  /**
   * Shows the message at the top of the camera view. The element is an
   * aria-live region, so it is written only when the text changes.
   * @param {string} message
   */
  function setStatus(message) {
    if (captureStatus.textContent !== message) {
      captureStatus.textContent = message;
    }
  }

  /**
   * Marks the shutter button while a press waits for the checks to pass.
   * @param {?Object} current the capture state, or null
   */
  function armed(current) {
    toggleClasses(shootButton, 'armed', Boolean(current && current.wanted));
  }

  /**
   * Confirms the photo: a short flash on the video, and a short vibration
   * where the device supports it.
   */
  function flashed() {
    flash.addEventListener('transitionend', function () {
      flash.classList.remove.apply(flash.classList,
                                   classes(flash, 'flashing'));
    }, {once: true});
    flash.classList.add.apply(flash.classList, classes(flash, 'flashing'));
    if (navigator.vibrate) {
      navigator.vibrate(40);
    }
  }

  /**
   * Draws the closed outline through the points, with a dark halo so that it
   * shows on any background.
   * @param {CanvasRenderingContext2D} context
   * @param {number[][]} points [x, y] in canvas pixels
   * @param {string} colour CSS colour of the line
   * @param {number} ratio device pixels per CSS pixel
   */
  function outline(context, points, colour, ratio) {
    context.beginPath();
    points.forEach(function (at, k) {
      if (k) {
        context.lineTo(at[0], at[1]);
      } else {
        context.moveTo(at[0], at[1]);
      }
    });
    context.closePath();
    context.lineWidth = 6 * ratio;
    context.strokeStyle = 'rgba(0, 0, 0, 0.35)';
    context.stroke();
    context.lineWidth = 3 * ratio;
    context.strokeStyle = colour;
    context.stroke();
  }

  /**
   * Draws the cover's outline over the video, which shows the whole frame
   * centred in its box: white while a check fails, green when the photo can
   * be taken. Clears the overlay when there is nothing to show.
   * @param {?Object} current the capture state, or null
   */
  function drawFrame(current) {
    const ratio = window.devicePixelRatio || 1;
    const width = Math.round(overlay.clientWidth * ratio);
    const height = Math.round(overlay.clientHeight * ratio);
    if (overlay.width !== width || overlay.height !== height) {
      overlay.width = width;
      overlay.height = height;
    }
    const context = overlay.getContext('2d');
    context.clearRect(0, 0, width, height);
    const last = current && current.mode === 'live' && current.last;
    if (!last || !last.corners || !video.videoWidth) {
      return;
    }
    const scale = Math.min(width / video.videoWidth,
                           height / video.videoHeight);
    const shownWidth = video.videoWidth * scale;
    const shownHeight = video.videoHeight * scale;
    const left = (width - shownWidth) / 2;
    const top = (height - shownHeight) / 2;
    outline(context, last.corners.map(function (p) {
      return [left + p[0] * shownWidth, top + p[1] * shownHeight];
    }), last.hint === null ? '#16a34a' : '#ffffff', ratio);
  }

  /**
   * Handles the worker's checks of a frame: updates the outline, the shutter
   * button and the hint, and takes the photo if one was asked for and all the
   * checks pass.
   * @param {Object} current the capture state
   * @param {{corners: ?number[][], hint: ?string}} reply the worker's reply
   */
  function framed(current, reply) {
    current.last = reply;
    current.failures = 0;
    if (current.wanted && reply.hint === null) {
      shoot(current);
      return;
    }
    drawFrame(current);
    shootButton.disabled = reply.hint !== null && !PASSING[reply.hint];
    armed(current);
    if (reply.hint === null) {
      current.notice = null;
    }
    // once asked for, the photo is taken as soon as the checks pass; the
    // hints still say what is missing
    const message = reply.hint === null ? 'Ready: take the photo.' :
                    current.wanted && PASSING[reply.hint] ?
                    'Hold still: the photo is taken as soon as it can be.' :
                    current.notice || HINTS[reply.hint];
    current.held = current.hint === message ? current.held + 1 : 1;
    current.hint = message;
    if (current.held >= HINT_FRAMES) {
      setStatus(message);
    }
  }

  /**
   * Counts the frames the video shows, so that each goes to the worker once at
   * most: the same frame twice would look still.
   * @param {Object} current the capture state
   */
  function watchFrames(current) {
    if (!video.requestVideoFrameCallback) {
      return;
    }
    const watching = ++current.watching;
    /** Counts one frame shown and waits for the next. */
    function shown() {
      if (capture === current && current.watching === watching) {
        current.shown++;
        video.requestVideoFrameCallback(shown);
      }
    }
    video.requestVideoFrameCallback(shown);
  }

  /**
   * Sends a small copy of the frame shown to the worker, and the next one when
   * the worker is done with it, until the capture stops.
   * @param {Object} current the capture state
   */
  function pump(current) {
    /** Sends the current frame if it is new and the worker is free. */
    function next() {
      if (capture !== current) {
        return;
      }
      const fresh = !video.requestVideoFrameCallback ||
                    current.shown !== current.sent;
      if (current.mode === 'live' && current.ready && !current.busy &&
          fresh && current.track && !current.track.muted &&
          video.readyState >= video.HAVE_CURRENT_DATA &&
          video.videoWidth) {
        current.sent = current.shown;
        const scale = FRAME_LONG_SIDE / Math.max(video.videoWidth,
                                                 video.videoHeight);
        const session = current.session;
        current.busy = true;
        createImageBitmap(video, {
          resizeWidth: Math.round(video.videoWidth * scale),
          resizeHeight: Math.round(video.videoHeight * scale),
          resizeQuality: 'medium'
        }).then(function (bitmap) {
          if (capture !== current || !current.worker ||
              current.session !== session || current.mode !== 'live') {
            bitmap.close();
            current.busy = false;
            return;
          }
          current.worker.postMessage({type: 'frame', bitmap: bitmap},
                                     [bitmap]);
        }, function () {
          current.busy = false;
        });
      }
      requestAnimationFrame(next);
    }
    next();
  }

  /**
   * Takes the camera's photo at its largest size (read when it opened).
   * @param {Object} current the capture state
   * @returns {Promise<?ImageBitmap>} the photo, or null where the browser takes
   *     none at least as large as the video's frames
   */
  async function largestPhoto(current) {
    const camera = new ImageCapture(current.track);
    const largest = current.photoSize ?
                    {imageWidth: current.photoSize[0],
                     imageHeight: current.photoSize[1]} : {};
    for (const asked of [largest, {}]) {
      try {
        const bitmap = await createImageBitmap(await camera.takePhoto(asked));
        if (bitmap.width * bitmap.height >=
            video.videoWidth * video.videoHeight) {
          return bitmap;
        }
        bitmap.close();
        return null;
      } catch (refused) {
        // with the default settings, else none
      }
    }
    return null;
  }

  /**
   * Waits up to PHOTO_WAIT ms for what was asked of the camera.
   * @param {Promise} asked
   * @param {function(*)=} letGo releases an answer that comes too late
   * @returns {Promise} the answer, or null if it failed or came too late
   */
  function within(asked, letGo) {
    return new Promise(function (resolve) {
      let late = false;
      const timer = setTimeout(function () {
        late = true;
        resolve(null);
      }, PHOTO_WAIT);
      asked.then(function (answer) {
        clearTimeout(timer);
        if (!late) {
          resolve(answer);
        } else if (answer && letGo) {
          letGo(answer);
        }
      }, function () {
        clearTimeout(timer);
        resolve(null);
      });
    });
  }

  /**
   * Waits up to PHOTO_WAIT ms for a photo, closing one that comes too late.
   * @param {Promise<?ImageBitmap>} taking
   * @returns {Promise<?ImageBitmap>}
   */
  function photoWithin(taking) {
    return within(taking, function (bitmap) { bitmap.close(); });
  }

  /**
   * Reads the size of the camera's largest photo.
   * @param {MediaStreamTrack} track
   * @returns {Promise<?number[]>} [width, height], or null where the browser
   *     takes no photos or does not tell
   */
  async function largestPhotoSize(track) {
    if (!window.ImageCapture) {
      return null;
    }
    const capabilities = await within(
      new ImageCapture(track).getPhotoCapabilities());
    return capabilities && capabilities.imageWidth &&
           capabilities.imageWidth.max && capabilities.imageHeight ?
           [capabilities.imageWidth.max, capabilities.imageHeight.max] : null;
  }

  /**
   * Leaves the video at LIVE where the camera's photos are at least as large as
   * its largest video, else raises it to VIDEO.
   * @param {Object} current the capture state
   * @param {MediaStreamTrack} track
   */
  async function liveMode(current, track) {
    current.photoSize = await largestPhotoSize(track);
    const capabilities = track.getCapabilities ? track.getCapabilities() : {};
    const largest = capabilities.width && capabilities.width.max &&
                    capabilities.height && capabilities.height.max ?
                    capabilities.width.max * capabilities.height.max :
                    Infinity;
    current.reduced = Boolean(current.photoSize &&
                              current.photoSize[0] * current.photoSize[1] >=
                              largest);
    if (!current.reduced) {
      try {
        await track.applyConstraints(VIDEO);
      } catch (refused) {
        // the mode it opened at
      }
    }
  }

  /**
   * Turns the source by quarter turns clockwise, cuts its centre to
   * width:height and returns it as grey levels with zero mean and unit spread.
   * @param {ImageBitmap} source
   * @param {number} turn quarter turns clockwise, 0 to 3
   * @param {number} width
   * @param {number} height
   * @returns {Promise<Float32Array>} width x height grey levels
   */
  async function greys(source, turn, width, height) {
    const small = await createImageBitmap(source, {
      resizeWidth: Math.max(1, Math.round(source.width * MATCH_SIDE * 4 /
                                          Math.max(source.width,
                                                   source.height))),
      resizeHeight: Math.max(1, Math.round(source.height * MATCH_SIDE * 4 /
                                           Math.max(source.width,
                                                    source.height))),
      resizeQuality: 'medium'
    });
    const turnedWidth = turn % 2 ? small.height : small.width;
    const turnedHeight = turn % 2 ? small.width : small.height;
    const scale = Math.min(turnedWidth / width, turnedHeight / height);
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext('2d', {willReadFrequently: true});
    context.translate(width / 2, height / 2);
    context.rotate(turn * Math.PI / 2);
    context.scale(1 / scale, 1 / scale);
    context.drawImage(small, -small.width / 2, -small.height / 2);
    small.close();
    const data = context.getImageData(0, 0, width, height).data;
    const grey = new Float32Array(width * height);
    let mean = 0;
    for (let i = 0; i < grey.length; i++) {
      grey[i] = 0.2126 * data[4 * i] + 0.7152 * data[4 * i + 1] +
                0.0722 * data[4 * i + 2];
      mean += grey[i] / grey.length;
    }
    let spread = 0;
    for (let i = 0; i < grey.length; i++) {
      grey[i] -= mean;
      spread += grey[i] * grey[i] / grey.length;
    }
    spread = Math.sqrt(spread) || 1;
    for (let i = 0; i < grey.length; i++) {
      grey[i] /= spread;
    }
    return grey;
  }

  /**
   * Turns the photo as the video shows the scene: by the quarter turns whose
   * grey levels correlate best with the frame's (see MATCH_SIDE).
   * @param {ImageBitmap} photo closed if a turned copy is returned
   * @param {ImageBitmap} frame the frame the checks passed on
   * @returns {Promise<ImageBitmap>}
   */
  async function turnedAsFrame(photo, frame) {
    const ratio = MATCH_SIDE / Math.max(frame.width, frame.height);
    const width = Math.max(8, Math.round(frame.width * ratio));
    const height = Math.max(8, Math.round(frame.height * ratio));
    const seen = await greys(frame, 0, width, height);
    let best = 0;
    let bestScore = -Infinity;
    for (let turn = 0; turn < 4; turn++) {
      const grey = await greys(photo, turn, width, height);
      let score = 0;
      for (let i = 0; i < grey.length; i++) {
        score += grey[i] * seen[i];
      }
      if (score > bestScore) {
        best = turn;
        bestScore = score;
      }
    }
    if (!best) {
      return photo;
    }
    const turnedWidth = best % 2 ? photo.height : photo.width;
    const turnedHeight = best % 2 ? photo.width : photo.height;
    const canvas = new OffscreenCanvas(turnedWidth, turnedHeight);
    const context = canvas.getContext('2d');
    context.translate(turnedWidth / 2, turnedHeight / 2);
    context.rotate(best * Math.PI / 2);
    context.drawImage(photo, -photo.width / 2, -photo.height / 2);
    photo.close();
    return canvas.transferToImageBitmap();
  }

  /**
   * Takes the camera's photo at its largest (see largestPhoto), turned as the
   * video shows the scene; where there is none, the video's frame, taken
   * first, which is the one the checks passed on.
   * @param {Object} current the capture state
   * @returns {Promise<?(ImageBitmap|string)>} the image, null if none could be
   *     taken, or RAISED if the video was raised for the next attempt
   */
  async function takePhoto(current) {
    let frame = null;
    try {
      frame = await createImageBitmap(video);
    } catch (refused) {
      // the photo only
    }
    let photo = window.ImageCapture ?
                await photoWithin(largestPhoto(current)) : null;
    if (!photo && current.reduced) {
      // no photo with the video at LIVE: the video raised to its largest,
      // for the photo to be taken from it, as where the browser takes none
      if (frame) {
        frame.close();
      }
      current.reduced = false;
      try {
        await current.track.applyConstraints(VIDEO);
      } catch (refused) {
        // the mode it was in
      }
      return RAISED;
    }
    if (photo && frame) {
      try {
        photo = await turnedAsFrame(photo, frame);
      } catch (refused) {
        // the photo as it came
      }
    }
    if (photo) {
      if (frame) {
        frame.close();
      }
      return photo;
    }
    return frame;
  }

  /**
   * Takes the photo and sends it to the worker, which finds the cover in it
   * again and straightens it.
   * @param {Object} current the capture state
   */
  async function shoot(current) {
    current.mode = 'shooting';
    current.wanted = false;
    armed(current);
    shootButton.disabled = true;
    setStatus('Taking the photo...');
    drawFrame(current);
    const last = current.last;
    const bitmap = await takePhoto(current);
    if (capture !== current || current.mode !== 'shooting') {
      if (bitmap && bitmap !== RAISED) {
        bitmap.close();
      }
      return;
    }
    if (bitmap === RAISED) {
      backToLive(current, 'The camera took no photo: it is taken from the ' +
                          'video instead, hold still.');
      current.wanted = true;
      armed(current);
      return;
    }
    if (!bitmap) {
      backToLive(current, 'The photo could not be taken: try again.');
      return;
    }
    flashed();
    setStatus('Making the image...');
    current.worker.postMessage({
      type: 'photo', bitmap: bitmap, corners: last && last.corners,
      frameAspect: video.videoWidth / video.videoHeight,
      frameLongSide: FRAME_LONG_SIDE
    }, [bitmap]);
  }

  /**
   * Returns to the live view for another photo.
   * @param {Object} current the capture state
   * @param {string=} message what went wrong, kept until a photo can be taken
   *     again
   */
  function backToLive(current, message) {
    current.mode = 'live';
    current.last = null;
    current.wanted = false;
    armed(current);
    // what went wrong stays said until the photo can be taken again
    current.notice = message || null;
    current.worker.postMessage({type: 'reset'});
    watchFrames(current);
    drawFrame(current);
    setStatus(message || HINTS.found);
  }

  /**
   * Handles a photo the worker rejected: a blurred one is taken again by itself
   * as soon as the frames pass the checks, at most RETAKES times in a row;
   * otherwise the user is asked to take it again.
   * @param {Object} current the capture state
   * @param {string} reason 'blurred' or 'lost'
   */
  function retake(current, reason) {
    const again = reason === 'blurred' && current.retakes < RETAKES;
    current.retakes = again ? current.retakes + 1 : 0;
    backToLive(current, reason === 'blurred' ?
               'The photo came out blurred: hold still' +
               (again ? ', it is taken again.' : ' and take it again.') :
               'The cover was not found in the photo: take it again.');
    current.wanted = again;
    armed(current);
  }

  /**
   * Returns the pixels the camera gives a cover filling COVER_SHARE of the long
   * side of its largest photo or video.
   * @param {Object} current the capture state
   * @returns {number} the pixels, or Infinity where the browser does not tell
   */
  function coverPixels(current) {
    const settings = current.track.getSettings();
    const capabilities = current.track.getCapabilities ?
                         current.track.getCapabilities() : {};
    const longSide = Math.max(
      settings.width || 0, settings.height || 0,
      capabilities.width && capabilities.width.max || 0,
      capabilities.height && capabilities.height.max || 0,
      current.photoSize ? Math.max.apply(null, current.photoSize) : 0);
    return longSide ? COVER_SHARE * longSide : Infinity;
  }

  /**
   * Builds the error that no camera gives a cover enough pixels, naming each
   * camera with the pixels it gives.
   * @param {Object} current the capture state
   * @param {string[]} failed notes on the cameras that could not start
   * @returns {Error} named 'TooFewPixels'
   */
  function tooFew(current, failed) {
    const error = new Error(
      'No camera here can take a cover at 300 dpi, which needs ' +
      PIXELS_NEEDED + ' pixels on its long side: ' +
      current.unfit.map(function (camera) {
        return camera.label + ' gives about ' + camera.pixels;
      }).join(', ') + '. Scan the cover, or photograph it with a better ' +
      'camera, and choose the file.' +
      (failed.length ? ' ' + failed.join(' ') : ''));
    error.name = 'TooFewPixels';
    return error;
  }

  /**
   * Returns the cameras among the media devices.
   * @param {MediaDeviceInfo[]} devices
   * @returns {MediaDeviceInfo[]}
   */
  function cameras(devices) {
    return devices.filter(function (device) {
      return device.kind === 'videoinput';
    });
  }

  /**
   * Shows the "Use your camera" button where the browser lists a camera.
   * Before the permission is given, browsers list one at most, without its
   * name.
   */
  function showStart() {
    navigator.mediaDevices.enumerateDevices().then(function (devices) {
      show(startButton, cameras(devices).length > 0);
    }, function () {
      show(startButton, false);
    });
  }

  /**
   * Tells whether the camera was found to give a cover too few pixels.
   * @param {Object} current the capture state
   * @param {MediaDeviceInfo} device
   * @returns {boolean}
   */
  function leftOut(current, device) {
    return current.unfit.some(function (camera) {
      return camera.id === device.deviceId;
    });
  }

  /**
   * Returns the cameras to switch between: all but those left out.
   * @param {Object} current the capture state
   * @returns {MediaDeviceInfo[]}
   */
  function choices(current) {
    return current.devices.filter(function (device) {
      return !leftOut(current, device);
    });
  }

  /**
   * Stops the camera's stream, if any, and detaches it from the video.
   * @param {Object} current the capture state
   */
  function stopStream(current) {
    if (!current.stream) {
      return;
    }
    current.stream.getTracks().forEach(function (track) { track.stop(); });
    if (video.srcObject === current.stream) {
      video.srcObject = null;
    }
    current.stream = null;
  }

  /**
   * Stops the capture (stream, worker and permission listener), clears the
   * view and closes it.
   */
  function stopCapture() {
    const current = capture;
    capture = null;
    stopStream(current);
    if (current.worker) {
      current.worker.terminate();
      current.worker = null;
    }
    if (current.permissionStatus) {
      current.permissionStatus.removeEventListener('change',
                                                   current.permissionUpdate);
    }
    show(switchButton, false);
    show(lastButton, false);
    if (lastUrl) {
      lastImage.removeAttribute('src');
      URL.revokeObjectURL(lastUrl);
      lastUrl = null;
    }
    armed(null);
    shootButton.disabled = true;
    setStatus('');
    drawFrame(null);
    if (captureView.open) {
      captureView.close();
    }
  }

  /**
   * Stops the camera and the worker after an error and shows the message; the
   * view stays open until the user closes it.
   * @param {Object} current the capture state
   * @param {string} message
   */
  function fail(current, message) {
    if (capture !== current) {
      return;
    }
    stopStream(current);
    if (current.worker) {
      current.worker.terminate();
      current.worker = null;
    }
    current.error = message;
    current.mode = 'failed';
    shootButton.disabled = true;
    drawFrame(current);
    show(switchButton, false);
    setStatus(message);
  }

  /**
   * Returns the message for an error from the camera.
   * @param {Error} error
   * @returns {string}
   */
  function cameraError(error) {
    const messages = {
      NotAllowedError: 'The camera permission was denied: allow it in the ' +
                       'browser settings and try again.',
      NotFoundError: 'No camera was found.',
      OverconstrainedError: 'No camera was found.',
      NotReadableError: 'The camera could not start: another application ' +
                        'may be using it, or the system cannot open it. ' +
                        'Close that application, then close the camera ' +
                        'here and try again, or choose a file.',
      SecurityError: 'The camera needs a secure (https) page.'
    };
    return error.name === 'TooFewPixels' ? error.message :
           messages[error.name] ||
           'The camera could not start: ' + error.name + ' ' + error.message;
  }

  /**
   * Starts the worker and handles its messages.
   * @param {Object} current the capture state
   * @returns {Promise} resolved once OpenCV.js is ready in the worker
   */
  function startWorker(current) {
    return new Promise(function (resolve, reject) {
      const worker = new Worker(captureView.dataset.worker);
      current.worker = worker;
      worker.onerror = function (event) {
        event.preventDefault();
        const message = event.message || 'the worker could not run';
        reject(new Error(message));
        fail(current, 'The processing stopped: ' + message);
      };
      worker.onmessage = function (event) {
        const message = event.data;
        if (capture !== current) {
          return;
        }
        if (message.type === 'ready') {
          resolve();
        } else if (message.type === 'frame') {
          current.busy = false;
          if (current.mode === 'live' && !current.track.muted) {
            framed(current, message);
          }
        } else if (message.type === 'retake') {
          if (current.mode === 'shooting') {
            retake(current, message.reason);
          }
        } else if (message.type === 'result') {
          // the cover straightened goes to the form as a file chosen would;
          // the camera goes on, so that a photo found wanting is taken
          // again at once, replacing it
          if (current.mode === 'shooting') {
            const file = new File([message.png], 'cover.png',
                                  {type: 'image/png'});
            selectScan(file);
            if (lastUrl) {
              URL.revokeObjectURL(lastUrl);
            }
            lastUrl = URL.createObjectURL(file);
            lastImage.src = lastUrl;
            show(lastButton, true);
            current.retakes = 0;
            backToLive(current, 'The photo is in the form. Take another ' +
                                'to replace it, or close the camera.');
          }
        } else if (message.type === 'failed') {
          if (message.step === 'init') {
            reject(new Error(message.error));
          } else if (message.step === 'frame') {
            current.busy = false;
            current.failures++;
            if (current.failures >= FRAME_FAILURES) {
              fail(current, 'The processing stopped: ' + message.error);
            }
          } else if (current.mode === 'shooting') {
            backToLive(current, 'The photo could not be processed (' +
                                message.error + '): take it again.');
          }
        }
      };
      worker.postMessage({type: 'init'});
    });
  }

  /**
   * Measures JPEG's blocks in the track's frames (see SLOW_RATE).
   * @param {MediaStreamTrack} track
   * @returns {Promise<?number>} the median ratio over the first BLOCK_FRAMES
   *     frames with enough texture, out of three times as many, or null
   */
  async function blocking(track) {
    const grabber = new ImageCapture(track);
    const ratios = [];
    for (let tries = 0; tries < 3 * BLOCK_FRAMES &&
                        ratios.length < BLOCK_FRAMES; tries++) {
      let bitmap;
      try {
        bitmap = await grabber.grabFrame();
      } catch (error) {
        return null;
      }
      // the central square, on the frame's 8 px grid
      const width = Math.min(BLOCK_SIDE, bitmap.width - bitmap.width % 8);
      const height = Math.min(BLOCK_SIDE, bitmap.height - bitmap.height % 8);
      const x0 = Math.floor((bitmap.width - width) / 16) * 8;
      const y0 = Math.floor((bitmap.height - height) / 16) * 8;
      const canvas = new OffscreenCanvas(width, height);
      const context = canvas.getContext('2d', {willReadFrequently: true});
      context.drawImage(bitmap, x0, y0, width, height, 0, 0, width, height);
      bitmap.close();
      const data = context.getImageData(0, 0, width, height).data;
      const luma = new Float32Array(width * height);
      for (let i = 0; i < luma.length; i++) {
        luma[i] = 0.2126 * data[4 * i] + 0.7152 * data[4 * i + 1] +
                  0.0722 * data[4 * i + 2];
      }
      let across = 0;
      let middle = 0;
      let count = 0;
      for (let y = 0; y < height; y++) {
        for (let x = y * width; x + 8 < (y + 1) * width; x += 8) {
          across += Math.abs(luma[x + 8] - luma[x + 7]);
          middle += Math.abs(luma[x + 4] - luma[x + 3]);
          count++;
        }
      }
      for (let y = 0; y + 8 < height; y += 8) {
        for (let x = y * width; x < (y + 1) * width; x++) {
          across += Math.abs(luma[x + 8 * width] - luma[x + 7 * width]);
          middle += Math.abs(luma[x + 4 * width] - luma[x + 3 * width]);
          count++;
        }
      }
      if (middle / count >= BLOCK_TEXTURE) {
        ratios.push(across / middle);
      }
    }
    ratios.sort(function (a, b) { return a - b; });
    return ratios.length ? ratios[ratios.length >> 1] : null;
  }

  /**
   * Switches the camera to its slower native mode at the same size if its
   * frames show JPEG's blocks and those of the slower mode do not (see
   * SLOW_RATE); otherwise keeps the mode it opened at.
   * @param {MediaStreamTrack} track
   */
  async function slowerMode(track) {
    const opened = track.getSettings();
    if (opened.resizeMode !== 'none' || !(opened.frameRate > SLOW_RATE) ||
        !window.ImageCapture) {
      return;
    }
    const size = {width: {exact: opened.width},
                  height: {exact: opened.height},
                  resizeMode: {ideal: 'none'}};
    const blocks = [await blocking(track), null];
    try {
      if (blocks[0] !== null && blocks[0] >= BLOCKY) {
        await track.applyConstraints(Object.assign({
          frameRate: {min: SLOW_RATE, ideal: SLOW_RATE}
        }, size));
        const settings = track.getSettings();
        if (settings.resizeMode === 'none' &&
            settings.frameRate < opened.frameRate) {
          blocks[1] = await blocking(track);
        }
        if (blocks[1] === null || blocks[1] >= BLOCKY) {
          await track.applyConstraints(Object.assign({
            frameRate: {ideal: opened.frameRate}
          }, size));
        }
      }
    } catch (error) {
      // the mode it opened at
    }
  }

  /**
   * Says that the camera does not answer if it has not answered within
   * SILENT_MS, unless the browser is still asking for the permission. The wait
   * ends when answered is called.
   * @param {Object} current the capture state
   */
  function sayIfSilent(current) {
    const asked = ++current.asked;
    setTimeout(function () {
      const status = current.permissionStatus;
      if (capture === current && current.asked === asked && !current.error &&
          !(status && status.state === 'prompt')) {
        setStatus('The camera does not answer: close the other applications ' +
                  'that may use it, or close it here and choose a file.');
      }
    }, SILENT_MS);
  }

  /**
   * Ends the wait started by sayIfSilent.
   * @param {Object} current the capture state
   */
  function answered(current) {
    current.asked++;
  }

  /**
   * Opens a camera and shows its video. A camera that gives a cover too few
   * pixels is closed and left out.
   * @param {Object} current the capture state
   * @param {MediaTrackConstraints} camera which camera to open
   * @returns {Promise<boolean>} false if the capture stopped meanwhile; rejected
   *     if the camera cannot start, or with TooFewPixels
   */
  async function openCamera(current, camera) {
    stopStream(current);
    sayIfSilent(current);
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: Object.assign({}, window.ImageCapture ? LIVE : VIDEO, camera)
      });
      if (capture !== current || current.error) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        return false;
      }
      // kept at once, so that closing stops it while its mode is checked
      current.stream = stream;
      current.photoSize = null;
      current.reduced = false;
      if (window.ImageCapture) {
        await liveMode(current, stream.getVideoTracks()[0]);
      }
      await slowerMode(stream.getVideoTracks()[0]);
    } finally {
      answered(current);
    }
    if (capture !== current || current.error || current.stream !== stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      return false;
    }
    const track = stream.getVideoTracks()[0];
    // a camera that stopped while its mode was checked, as one does when
    // its system service fails, did not start
    if (track.readyState === 'ended') {
      stopStream(current);
      throw new DOMException('The camera stopped as it started.',
                             'NotReadableError');
    }
    current.track = track;
    // a camera that cannot give a cover enough pixels is left out
    const pixels = coverPixels(current);
    if (pixels < PIXELS_NEEDED) {
      // its id read while it runs: a stopped camera may no longer tell it
      current.unfit.push({id: track.getSettings().deviceId,
                          label: track.label || 'a camera',
                          pixels: Math.round(pixels / 100) * 100});
      current.track = null;
      stopStream(current);
      throw tooFew(current, []);
    }
    current.session++;
    current.last = null;
    if (current.worker) {
      current.worker.postMessage({type: 'reset'});
    }
    track.addEventListener('ended', function () {
      if (current.track === track) {
        fail(current, 'The camera stopped: close it here and try again, or ' +
                      'choose a file.');
      }
    });
    // a camera sends no images for a while when the system pauses it, as
    // phones do while another application is in front: no photo then, and
    // the checks again from the start when it sends them again
    track.addEventListener('mute', function () {
      if (current.track === track && current.mode === 'live') {
        current.last = null;
        current.wanted = false;
        shootButton.disabled = true;
        drawFrame(current);
        setStatus('The camera is paused: it goes on when it sends images ' +
                  'again.');
      }
    });
    track.addEventListener('unmute', function () {
      if (current.track === track && current.mode === 'live') {
        backToLive(current);
      }
    });
    const settings = track.getSettings();
    // the camera facing the user is shown as in a mirror
    const mirrored = settings.facingMode ?
                     settings.facingMode === 'user' :
                     !/back|rear|environment/i.test(track.label);
    toggleClasses(video, 'mirrored', mirrored);
    toggleClasses(overlay, 'mirrored', mirrored);
    drawFrame(current);
    video.srcObject = stream;
    video.play().catch(function () {});
    current.devices = cameras(await navigator.mediaDevices.enumerateDevices());
    show(switchButton, choices(current).length > 1);
    return true;
  }

  /**
   * Opens the first of the cameras that starts. Without the permission none
   * would, so it stops there.
   * @param {Object} current the capture state
   * @param {MediaDeviceInfo[]} devices in the order to try them
   * @param {?Error} error the error to throw if none starts
   * @returns {Promise<?string>} a note on the cameras that could not start, or
   *     null if the capture stopped meanwhile
   */
  async function openFirst(current, devices, error) {
    const failed = [];
    for (const device of devices) {
      if (leftOut(current, device)) {
        continue;
      }
      try {
        if (!await openCamera(current,
                              {deviceId: {exact: device.deviceId}})) {
          return null;
        }
        return failed.join(' ');
      } catch (refused) {
        if (refused.name === 'NotAllowedError' ||
            refused.name === 'SecurityError') {
          throw refused;
        }
        // one with too few pixels is said once none is left (see tooFew)
        if (refused.name !== 'TooFewPixels') {
          failed.push((device.label || 'A camera') + ' could not start (' +
                      refused.name + ').');
          error = refused;
        }
      }
      if (capture !== current || current.error) {
        return null;
      }
    }
    throw current.unfit.length ? tooFew(current, failed) : error;
  }

  /**
   * Marks the camera ready for the checks and the photo.
   * @param {Object} current the capture state
   * @param {string} note what to say before the first hint
   */
  function cameraReady(current, note) {
    switchButton.disabled = false;
    current.mode = 'live';
    current.wanted = false;
    current.retakes = 0;
    watchFrames(current);
    setStatus((note ? note + ' ' : '') + HINTS.found);
  }

  /**
   * Says so while the browser asks for the camera permission.
   * @param {Object} current the capture state
   */
  function watchPermission(current) {
    if (!navigator.permissions) {
      return;
    }
    navigator.permissions.query({name: 'camera'}).then(function (status) {
      if (capture !== current) {
        return;
      }
      /** Shows the permission state until the camera has started. */
      function update() {
        if (capture === current && !current.track && !current.error) {
          setStatus(status.state === 'prompt' ?
                    'Allow the camera in the request the browser shows ' +
                    'next to the address bar.' : 'Starting the camera...');
        }
      }
      current.permissionStatus = status;
      current.permissionUpdate = update;
      status.addEventListener('change', update);
      update();
    }, function () {
      // the page says it is starting the camera
    });
  }

  /**
   * Starts the capture: the worker, then the preferred camera or the first one
   * that starts, then the checks of the frames.
   */
  async function startCapture() {
    const current = {
      session: 0, devices: [], worker: null, stream: null, track: null,
      error: null, mode: 'starting', ready: false, busy: false, last: null,
      watching: 0, shown: 0, sent: -1, wanted: false, failures: 0,
      hint: null, held: 0, notice: null, retakes: 0, asked: 0,
      photoSize: null, reduced: false, unfit: []
    };
    capture = current;
    shootButton.disabled = true;
    show(switchButton, false);
    setStatus('Starting the camera...');
    const ready = startWorker(current);
    // its failure is handled once the camera is open
    ready.catch(function () {});
    watchPermission(current);
    let note = '';
    try {
      if (!await openCamera(current, {facingMode: {ideal: 'environment'}})) {
        return;
      }
    } catch (error) {
      if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
        fail(current, cameraError(error));
        return;
      }
      // a camera that cannot start gives way to the others
      try {
        const devices = cameras(await navigator.mediaDevices
                                               .enumerateDevices());
        note = await openFirst(current, devices.filter(function (device) {
          return device.deviceId;
        }), error);
      } catch (again) {
        fail(current, cameraError(again));
        return;
      }
      if (note === null) {
        return;
      }
    }
    setStatus('Getting ready...');
    try {
      await ready;
    } catch (error) {
      fail(current, 'The processing could not start: ' + error.message);
      return;
    }
    if (capture !== current || current.error) {
      return;
    }
    current.ready = true;
    cameraReady(current, note);
    pump(current);
  }

  startButton.addEventListener('click', function () {
    if (!capture) {
      // the page does not scroll, nor shows its scroll bar, under the view;
      // the view itself focused, so that Space takes the photo
      document.documentElement.classList.add('overflow-hidden');
      captureView.showModal();
      captureView.focus();
      startCapture();
    }
  });

  shootButton.addEventListener('click', function () {
    const current = capture;
    if (!current || current.mode !== 'live' || !current.last) {
      return;
    }
    if (current.wanted) {
      // pressed again while waiting: not taken
      current.wanted = false;
      armed(current);
      setStatus(HINTS[current.last.hint] || HINTS.found);
    } else if (current.last.hint === null) {
      shoot(current);
    } else if (PASSING[current.last.hint]) {
      current.wanted = true;
      armed(current);
      setStatus('Hold still: the photo is taken as soon as it can be.');
    }
  });

  // closing the view, also with Esc, stops the camera; the last photo,
  // pressed, closes it too, back to the form where it is
  captureView.addEventListener('close', function () {
    document.documentElement.classList.remove('overflow-hidden');
    if (capture) {
      stopCapture();
    }
  });
  cancelButton.addEventListener('click', function () {
    captureView.close();
  });
  lastButton.addEventListener('click', function () {
    captureView.close();
  });

  // Space takes the photo while the camera runs, as the button would,
  // unless typing in a field
  document.addEventListener('keydown', function (event) {
    if (!capture || event.key !== ' ' || event.repeat ||
        /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName) ||
        event.target.isContentEditable ||
        event.target.tagName === 'BUTTON') {
      return;
    }
    event.preventDefault();
    if (!shootButton.disabled) {
      shootButton.click();
    }
  });

  // a camera plugged in or out: the button shown again, or while one is
  // running, the cameras to switch to (the running one, if out, ends by
  // itself)
  navigator.mediaDevices.addEventListener('devicechange', function () {
    const current = capture;
    if (!current) {
      showStart();
      return;
    }
    if (!current.track) {
      return;
    }
    navigator.mediaDevices.enumerateDevices().then(function (devices) {
      if (capture !== current) {
        return;
      }
      current.devices = cameras(devices);
      show(switchButton, choices(current).length > 1);
    }, function () {
      // the cameras known before
    });
  });

  // the camera let go when the page is left, also where the browser keeps
  // the page to come back to it
  window.addEventListener('pagehide', function () {
    if (capture) {
      stopCapture();
    }
  });

  switchButton.addEventListener('click', function () {
    const current = capture;
    if (!current || !current.track || !current.worker ||
        current.mode !== 'live' || choices(current).length < 2) {
      return;
    }
    const deviceId = current.track.getSettings().deviceId;
    const devices = choices(current);
    const index = devices.findIndex(function (device) {
      return device.deviceId === deviceId;
    });
    // the next cameras in turn; if none starts, the one running before
    const order = devices.slice(index + 1).concat(devices.slice(0, index + 1));
    switchButton.disabled = true;
    current.mode = 'switching';
    shootButton.disabled = true;
    setStatus('Switching the camera...');
    openFirst(current, order, null).then(function (note) {
      if (note !== null && capture === current && !current.error) {
        cameraReady(current, note);
      }
    }, function (error) {
      fail(current, cameraError(error));
    });
  });

  if (window.ResizeObserver) {
    // the outline follows the video's box when the page changes
    new ResizeObserver(function () {
      if (capture) {
        drawFrame(capture);
      }
    }).observe(captureView);
  }

  showStart();
}());
