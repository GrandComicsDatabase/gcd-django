// The cover capture's worker. As document scanners do, it finds the cover in
// small copies of the camera's frames and tells the page whether a photo
// can be taken: the cover all in view, near enough, faced, lit, without
// glare, still and sharp. Then it finds the cover again in the photo,
// straightens it at the photo's own resolution, trimmed inside uneven
// paper edges, as a PNG, or asks for the photo again where it came out
// blurred. All of it with OpenCV.js.
'use strict';

// OpenCV.js 4.13.0 (Apache 2.0)
const OPENCV = '../opencv_4_13_0.js';
// the cover is searched in a copy of the photo at the frames' scale, where
// the search was checked: at twice that, a textured table's edges merged
// into an outline of the whole photo. What is found there is taken unless
// it touches the photo's borders (see MARGIN) or, where the photo is turned
// as the frames are, its area is more than PHOTO_AREA times or less than
// 1 / PHOTO_AREA times that of the last frame's corners in the photo; then
// those are taken, where the photo is turned as the frames are.
const PHOTO_AREA = 1.5;
// the cover, found as in OpenCV's squares sample and the usual document
// scanners: edges by Canny with thresholds from the median (Rosebrock's
// "auto Canny"), closed by a dilation, then of the outlines the largest
// one whose convex hull is a quadrilateral. The hull leaves out
// fingers over a side; the quadrilateral must cover the hull nearly all,
// its angles near enough to right ones, and the frame at least MIN_AREA.
// The search runs on a copy halved by pyrDown, as in the squares sample:
// at full size the weave of a mesh chair behind a cover gave edges that
// joined the cover's outline, and on 48 frames of a tablet held upright
// all the checks passed on 17 at full size and 45 at half size (on 77
// frames held across, 19 and 40). The sides are then fitted at full size.
const CANNY_SPREAD = 0.33;
const HULL_SHARE = 0.92;
const MIN_AREA = 0.08;
const MIN_ANGLE = 45;
const APPROX = [0.02, 0.03, 0.05, 0.08];
// the checks for the photo, on the small frames (see checkFrame), in the
// order the page asks for them. The sharpness, glare and light are
// measured inside the cover, inset by INSET of its size off its sides.
// - in view: each corner at least MARGIN of the frame off its borders;
const MARGIN = 0.01;
// - near: the cover spans at least FILL of the frame across or down, so
//   that the photo's pixels are on it;
const FILL = 0.7;
// - faced: each side at least FACED of the one opposite, so that the far
//   side keeps most of the near one's resolution. A cover lying on a table
//   under a tablet held over it by hand measured 0.84 to 0.88;
const FACED = 0.75;
// - lit: a mean luma of at least DARK;
const DARK = 50;
// - no glare: under GLARE_SHARE of it clipped, at GLARE_LEVEL or above.
//   Clipped pixels are as much white print as glare: a cover's white title
//   and border, with no glare in view, measured up to 2.8%. So only glare
//   over a large part of it stops the photo;
const GLARE_LEVEL = 250;
const GLARE_SHARE = 0.05;
// - still: the cover's corners converged, as document scanners verify the
//   cover across frames: each frame's corners, refined to the subpixel by
//   its sides fitted to the frame's edges (see refine) within FRAME_REACH
//   pixels, in the last STILL_FRAMES frames in a row, all within STILL of
//   the frame's diagonal from their mean and from the frame before. The
//   corners as found, vertices of the outline's approximation, moved up to
//   0.86% of the diagonal from frame to frame in one in four frames of a
//   cover held by hand. That mean is the outline shown, kept through a
//   frame or two without the cover, up to MISSED_FRAMES; the other checks
//   take the worse of it and the frame's own corners, so that they are not
//   looser for it;
const STILL = 0.006;
const STILL_FRAMES = 4;
const FRAME_REACH = 3;
const MISSED_FRAMES = 2;
// - sharp: the variance of its Laplacian (Pech-Pacheco et al., 2000) at
//   least SHARP_SHARE of the highest of the last SHARP_KEPT frames, where
//   the camera's focus has been, and at least SHARP_MIN.
const SHARP_SHARE = 0.7;
const SHARP_KEPT = 30;
const SHARP_MIN = 20;
const INSET = 0.05;
// the photo is blurred when its sharpness, at the frames' scale, is under
// this share of the last frame's
const PHOTO_BLURRED = 0.5;
// the cover's corners in the photo are refined where its sides, fitted to
// the photo's edges (see sideLine), meet: the edge searched every
// SIDE_STEP pixels along each side, leaving out SIDE_ENDS of it at each
// end, within SEARCH_REACH pixels of the copy it was found in either way;
// a step across it of MIN_STEP levels at least; a side fitted where its
// edge is found at SIDE_FOUND of the places at least
const SIDE_STEP = 2;
const SIDE_ENDS = 0.1;
const SEARCH_REACH = 3;
const MIN_STEP = 12;
const SIDE_FOUND = 0.5;
// the cover's image is cut inside its edges where the paper's edge is
// uneven, so that no background shows along them: each side moved in as
// far as TRIM_SHARE of its edge's points lie from the side fitted, at most
// TRIM_MOST of the cover's shorter side. A clean edge loses TRIM_LEAST
// pixels of the photo only: the edge is found in the middle of the step
// from the background to the paper, and the pixel there is half of each.
const TRIM_SHARE = 0.95;
const TRIM_MOST = 0.015;
const TRIM_LEAST = 1;
// the focal length, in units of the photo's long side, for the cover's
// proportions: that of the usual main cameras, about 26 mm equivalent.
// Faced as the checks want it, a wrong one changes the proportions little.
const FOCAL = 0.8;

let cv = null;
// the cover's corners in the last frames it was found in, and the frames
// since it was last found
let recent = [];
let missed = 0;
// the frames in a row the cover was found in
let streak = 0;
let sharpness = [];
let lastSharpness = null;

/**
 * Loads OpenCV.js and tells the page when it is ready; a runtime that cannot
 * start says so, rather than never being ready.
 */
function loadOpenCV() {
  self.Module = {
    onAbort: function (what) {
      postMessage({type: 'failed', step: 'init', error: String(what)});
    }
  };
  importScripts(OPENCV);
  self.cv.then(function (module) {
    cv = module;
    postMessage({type: 'ready'});
  });
}

/**
 * Returns the median of an 8 bit image.
 * @param {cv.Mat} gray
 * @returns {number}
 */
function median(gray) {
  const counts = new Uint32Array(256);
  const data = gray.data;
  for (let i = 0; i < data.length; i++) {
    counts[data[i]]++;
  }
  let seen = 0;
  for (let value = 0; value < 256; value++) {
    seen += counts[value];
    if (2 * seen >= data.length) {
      return value;
    }
  }
  return 255;
}

/**
 * Orders four points clockwise on the image, from the one nearest its top
 * left.
 * @param {number[][]} points [x, y]
 * @returns {number[][]}
 */
function ordered(points) {
  const cx = points.reduce(function (sum, p) { return sum + p[0]; }, 0) / 4;
  const cy = points.reduce(function (sum, p) { return sum + p[1]; }, 0) / 4;
  const sorted = points.slice().sort(function (a, b) {
    return Math.atan2(a[1] - cy, a[0] - cx) - Math.atan2(b[1] - cy, b[0] - cx);
  });
  let first = 0;
  sorted.forEach(function (p, k) {
    if (p[0] + p[1] < sorted[first][0] + sorted[first][1]) {
      first = k;
    }
  });
  return sorted.slice(first).concat(sorted.slice(0, first));
}

/**
 * Returns the smallest angle of the quadrilateral, in degrees.
 * @param {number[][]} corners
 * @returns {number}
 */
function smallestAngle(corners) {
  let smallest = 180;
  for (let k = 0; k < 4; k++) {
    const a = corners[(k + 3) % 4];
    const b = corners[k];
    const c = corners[(k + 1) % 4];
    const u = [a[0] - b[0], a[1] - b[1]];
    const v = [c[0] - b[0], c[1] - b[1]];
    const cos = (u[0] * v[0] + u[1] * v[1]) /
                (Math.hypot(u[0], u[1]) * Math.hypot(v[0], v[1]));
    smallest = Math.min(smallest, Math.acos(Math.max(-1, Math.min(1, cos))) *
                                  180 / Math.PI);
  }
  return smallest;
}

/**
 * Finds the cover in the 8 bit image.
 * @param {cv.Mat} gray
 * @returns {?number[][]} its corners, clockwise from the top left, or null
 */
function findCover(gray) {
  const blurred = new cv.Mat();
  const edges = new cv.Mat();
  const contours = new cv.MatVector();
  const hierarchy = new cv.Mat();
  const kernel = cv.Mat.ones(3, 3, cv.CV_8U);
  let best = null;
  try {
    cv.pyrDown(gray, blurred);
    cv.GaussianBlur(blurred, blurred, new cv.Size(5, 5), 0);
    const middle = median(blurred);
    cv.Canny(blurred, edges, Math.max(0, (1 - CANNY_SPREAD) * middle),
             Math.min(255, (1 + CANNY_SPREAD) * middle));
    cv.dilate(edges, edges, kernel);
    // all the outlines, inner ones too: the cover's may be inside another,
    // or joined to one, as on a stack of comics
    cv.findContours(edges, contours, hierarchy, cv.RETR_LIST,
                    cv.CHAIN_APPROX_SIMPLE);
    let bestArea = MIN_AREA * blurred.rows * blurred.cols;
    for (let i = 0; i < contours.size(); i++) {
      const contour = contours.get(i);
      const hull = new cv.Mat();
      const approx = new cv.Mat();
      try {
        cv.convexHull(contour, hull, false, true);
        const hullArea = cv.contourArea(hull);
        if (hullArea < bestArea) {
          continue;
        }
        const length = cv.arcLength(hull, true);
        for (const share of APPROX) {
          cv.approxPolyDP(hull, approx, share * length, true);
          if (approx.rows <= 4) {
            break;
          }
        }
        if (approx.rows !== 4) {
          continue;
        }
        const area = cv.contourArea(approx);
        const corners = [];
        for (let k = 0; k < 4; k++) {
          corners.push([2 * approx.data32S[2 * k],
                        2 * approx.data32S[2 * k + 1]]);
        }
        if (area >= bestArea && area >= HULL_SHARE * hullArea &&
            smallestAngle(ordered(corners)) >= MIN_ANGLE) {
          best = ordered(corners);
          bestArea = area;
        }
      } finally {
        contour.delete();
        hull.delete();
        approx.delete();
      }
    }
  } finally {
    blurred.delete();
    edges.delete();
    contours.delete();
    hierarchy.delete();
    kernel.delete();
  }
  return best;
}

/**
 * Returns a mask of the cover in the image, inset off its sides (see INSET).
 * The caller deletes it.
 * @param {cv.Mat} gray
 * @param {number[][]} corners
 * @returns {cv.Mat}
 */
function coverMask(gray, corners) {
  const cx = corners.reduce(function (sum, p) { return sum + p[0]; }, 0) / 4;
  const cy = corners.reduce(function (sum, p) { return sum + p[1]; }, 0) / 4;
  const mask = cv.Mat.zeros(gray.rows, gray.cols, cv.CV_8U);
  const points = cv.matFromArray(4, 1, cv.CV_32SC2, [].concat.apply([],
    corners.map(function (p) {
      return [Math.round(p[0] + (cx - p[0]) * 2 * INSET),
              Math.round(p[1] + (cy - p[1]) * 2 * INSET)];
    })));
  const polygons = new cv.MatVector();
  polygons.push_back(points);
  cv.fillPoly(mask, polygons, new cv.Scalar(255));
  polygons.delete();
  points.delete();
  return mask;
}

/**
 * Measures the inside of the cover: the variance of the Laplacian, the mean
 * luma and the share of clipped pixels.
 * @param {cv.Mat} gray
 * @param {number[][]} corners
 * @returns {{sharpness: number, luma: number, glare: number}}
 */
function measures(gray, corners) {
  const mask = coverMask(gray, corners);
  const laplacian = new cv.Mat();
  const mean = new cv.Mat();
  const deviation = new cv.Mat();
  const clipped = new cv.Mat();
  try {
    cv.Laplacian(gray, laplacian, cv.CV_64F);
    cv.meanStdDev(laplacian, mean, deviation, mask);
    const pixels = cv.countNonZero(mask);
    cv.threshold(gray, clipped, GLARE_LEVEL - 1, 255, cv.THRESH_BINARY);
    cv.bitwise_and(clipped, mask, clipped);
    return {sharpness: deviation.doubleAt(0, 0) ** 2,
            luma: cv.mean(gray, mask)[0],
            glare: pixels ? cv.countNonZero(clipped) / pixels : 0};
  } finally {
    mask.delete();
    laplacian.delete();
    mean.delete();
    deviation.delete();
    clipped.delete();
  }
}

/**
 * Rotates the order of the corners so that they are nearest to the
 * reference's, as the first one, nearest the top left, may change from view
 * to view.
 * @param {number[][]} corners
 * @param {number[][]} reference
 * @returns {number[][]}
 */
function aligned(corners, reference) {
  let best = corners;
  let far = Infinity;
  for (let shift = 0; shift < 4; shift++) {
    const shifted = corners.slice(shift).concat(corners.slice(0, shift));
    const distance = Math.max.apply(null, shifted.map(function (p, k) {
      return Math.hypot(p[0] - reference[k][0], p[1] - reference[k][1]);
    }));
    if (distance < far) {
      best = shifted;
      far = distance;
    }
  }
  return best;
}

/**
 * Returns the area of the quadrilateral (shoelace formula).
 * @param {number[][]} corners
 * @returns {number}
 */
function area(corners) {
  let twice = 0;
  corners.forEach(function (p, k) {
    const q = corners[(k + 1) % 4];
    twice += p[0] * q[1] - q[0] * p[1];
  });
  return Math.abs(twice) / 2;
}

/**
 * Returns the length of the side from corner k to the next one.
 * @param {number[][]} corners
 * @param {number} k
 * @returns {number}
 */
function side(corners, k) {
  const a = corners[k];
  const b = corners[(k + 1) % 4];
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

/**
 * Returns the largest distance between matching corners of a and b.
 * @param {number[][]} a
 * @param {number[][]} b
 * @returns {number}
 */
function farthest(a, b) {
  return Math.max.apply(null, a.map(function (p, k) {
    return Math.hypot(p[0] - b[k][0], p[1] - b[k][1]);
  }));
}

/**
 * Measures how far the cover is from the frame's borders, how much of the
 * frame it spans and how squarely it faces the camera.
 * @param {number[][]} corners
 * @param {number} width
 * @param {number} height
 * @returns {{margin: number, fill: number, faced: number}}
 */
function geometry(corners, width, height) {
  const xs = corners.map(function (p) { return p[0]; });
  const ys = corners.map(function (p) { return p[1]; });
  return {
    margin: Math.min(Math.min.apply(null, xs) / width,
                     Math.min.apply(null, ys) / height,
                     1 - Math.max.apply(null, xs) / width,
                     1 - Math.max.apply(null, ys) / height),
    fill: Math.max((Math.max.apply(null, xs) - Math.min.apply(null, xs)) /
                   width,
                   (Math.max.apply(null, ys) - Math.min.apply(null, ys)) /
                   height),
    faced: Math.min(Math.min(side(corners, 0), side(corners, 2)) /
                    Math.max(side(corners, 0), side(corners, 2)),
                    Math.min(side(corners, 1), side(corners, 3)) /
                    Math.max(side(corners, 1), side(corners, 3)))
  };
}

/**
 * Runs the checks for the photo on a frame (see MARGIN to SHARP_MIN), on the
 * cover's outline, which is the mean of its last corners.
 * @param {number[][]} corners
 * @param {number} width
 * @param {number} height
 * @param {{sharpness: number, luma: number, glare: number}} measured
 * @returns {{sharpness: number, hint: ?string}} the first check failed as the
 *     hint, or null
 */
function checkFrame(corners, width, height, measured) {
  const diagonal = Math.hypot(width, height);
  const outline = geometry(corners, width, height);
  const own = geometry(recent[recent.length - 1], width, height);
  sharpness.push(measured.sharpness);
  if (sharpness.length > SHARP_KEPT) {
    sharpness.shift();
  }
  const values = {
    margin: Math.min(outline.margin, own.margin),
    fill: Math.min(outline.fill, own.fill),
    faced: Math.min(outline.faced, own.faced),
    luma: measured.luma,
    glare: measured.glare,
    // the farthest any corner of the last frames is from their mean, and
    // from the frame before
    spread: Math.max.apply(null, recent.map(function (seen) {
      return farthest(seen, corners);
    })) / diagonal,
    step: Math.max.apply(null, recent.slice(1).map(function (seen, k) {
      return farthest(seen, recent[k]);
    }).concat([0])) / diagonal,
    sharpness: measured.sharpness,
    sharpest: Math.max.apply(null, sharpness)
  };
  const checks = [
    ['inView', values.margin >= MARGIN],
    ['near', values.fill >= FILL],
    ['faced', values.faced >= FACED],
    ['lit', values.luma >= DARK],
    ['noGlare', values.glare < GLARE_SHARE],
    ['still', streak >= STILL_FRAMES && values.spread < STILL &&
              values.step < STILL],
    ['sharp', values.sharpness >= SHARP_MIN &&
              values.sharpness >= SHARP_SHARE * values.sharpest]
  ];
  const failed = checks.find(function (check) { return !check[1]; });
  return {sharpness: values.sharpness, hint: failed ? failed[0] : null};
}

/**
 * Returns the image's luma, scaled down to the long side if given. The caller
 * deletes the Mat.
 * @param {ImageBitmap|OffscreenCanvas} image
 * @param {number=} longSide
 * @returns {{gray: cv.Mat, scale: number}}
 */
function grayOf(image, longSide) {
  const scale = longSide ?
                Math.min(1, longSide / Math.max(image.width, image.height)) :
                1;
  const width = Math.round(image.width * scale);
  const height = Math.round(image.height * scale);
  const canvas = new OffscreenCanvas(width, height);
  const context = canvas.getContext('2d', {willReadFrequently: true});
  context.drawImage(image, 0, 0, width, height);
  const rgba = cv.matFromImageData(context.getImageData(0, 0, width, height));
  const gray = new cv.Mat();
  cv.cvtColor(rgba, gray, cv.COLOR_RGBA2GRAY);
  rgba.delete();
  return {gray: gray, scale: scale};
}

/**
 * Checks a small frame and replies with the cover in it, normalised to the
 * frame, and the hint, null once all the checks pass.
 * @param {{bitmap: ImageBitmap}} message
 */
function frame(message) {
  const bitmap = message.bitmap;
  const width = bitmap.width;
  const height = bitmap.height;
  const gray = grayOf(bitmap).gray;
  bitmap.close();
  const reply = {type: 'frame', corners: null, hint: 'found'};
  try {
    let found = findCover(gray);
    if (found) {
      if (recent.length) {
        found = aligned(found, recent[recent.length - 1]);
      }
      recent.push(refine(gray, found, FRAME_REACH));
      if (recent.length > STILL_FRAMES) {
        recent.shift();
      }
      missed = 0;
      streak++;
    } else {
      streak = 0;
      if (++missed > MISSED_FRAMES) {
        recent = [];
      }
    }
    if (recent.length) {
      // the mean of the corners in the last frames
      const corners = recent[0].map(function (p, k) {
        return [0, 1].map(function (axis) {
          return recent.reduce(function (sum, seen) {
            return sum + seen[k][axis];
          }, 0) / recent.length;
        });
      });
      const checked = checkFrame(corners, width, height,
                                 measures(gray, corners));
      reply.corners = corners.map(function (p) {
        return [p[0] / width, p[1] / height];
      });
      // a frame without the cover is not still
      reply.hint = found ? checked.hint : checked.hint || 'still';
      lastSharpness = checked.sharpness;
    }
  } finally {
    gray.delete();
  }
  postMessage(reply);
}

/**
 * Fits the side from a to b to the image's edge: along it, the strongest step
 * across it within reach, to the subpixel, then a line through those points
 * (cv.fitLine, Huber's M-estimator). The ends are left out, as corners are
 * often worn.
 * @param {cv.Mat} gray
 * @param {number[]} a
 * @param {number[]} b
 * @param {number} reach pixels searched on each side
 * @returns {?number[]} [vx, vy, x0, y0] with `normal` and `uneven`, or null
 *     where too few points were found
 */
function sideLine(gray, a, b, reach) {
  const data = gray.data;
  const width = gray.cols;
  const height = gray.rows;
  const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const normal = [(a[1] - b[1]) / length, (b[0] - a[0]) / length];
  /**
   * Returns the grey level at the nearest pixel, or null outside the image.
   * @param {number} x
   * @param {number} y
   * @returns {?number}
   */
  function at(x, y) {
    const i = Math.round(x);
    const j = Math.round(y);
    return i >= 0 && j >= 0 && i < width && j < height ?
           data[j * width + i] : null;
  }
  const points = [];
  let tried = 0;
  for (let t = SIDE_ENDS; t <= 1 - SIDE_ENDS; t += SIDE_STEP / length) {
    tried++;
    const x = a[0] + t * (b[0] - a[0]);
    const y = a[1] + t * (b[1] - a[1]);
    const steps = [];
    for (let s = -reach - 1; s <= reach + 1; s++) {
      const before = at(x + (s - 1) * normal[0], y + (s - 1) * normal[1]);
      const after = at(x + (s + 1) * normal[0], y + (s + 1) * normal[1]);
      steps.push(before === null || after === null ? 0 :
                 Math.abs(after - before));
    }
    let best = 1;
    for (let k = 2; k < steps.length - 1; k++) {
      if (steps[k] > steps[best]) {
        best = k;
      }
    }
    if (steps[best] >= MIN_STEP) {
      // the parabola's vertex through the strongest step and its two
      // neighbours
      const left = steps[best - 1];
      const right = steps[best + 1];
      const curve = left - 2 * steps[best] + right;
      const offset = best - reach - 1 +
                     (curve < 0 ? 0.5 * (left - right) / curve : 0);
      points.push(x + offset * normal[0], y + offset * normal[1]);
    }
  }
  if (points.length / 2 < SIDE_FOUND * tried) {
    return null;
  }
  const mat = cv.matFromArray(points.length / 2, 1, cv.CV_32FC2, points);
  const fitted = new cv.Mat();
  try {
    cv.fitLine(mat, fitted, cv.DIST_HUBER, 0, 0.01, 0.01);
    const line = Array.from(fitted.data32F);
    // how far in the edge's points lie from the side fitted (the normal
    // points into the cover, its corners going round clockwise)
    const inward = [];
    for (let i = 0; i < points.length; i += 2) {
      inward.push((points[i] - line[2]) * normal[0] +
                  (points[i + 1] - line[3]) * normal[1]);
    }
    inward.sort(function (p, q) { return p - q; });
    line.normal = normal;
    line.uneven = Math.max(0, inward[Math.min(inward.length - 1,
                                              Math.floor(TRIM_SHARE *
                                                         inward.length))]);
    return line;
  } finally {
    mat.delete();
    fitted.delete();
  }
}

/**
 * Returns where two fitted sides meet, each moved in by its inset.
 * @param {number[]} one [vx, vy, x0, y0]
 * @param {number[]} other [vx, vy, x0, y0]
 * @param {number[]} inset the two insets, in pixels
 * @returns {?number[]} the point, or null where the sides are parallel
 */
function meeting(one, other, inset) {
  const cross = one[0] * other[1] - one[1] * other[0];
  if (Math.abs(cross) < 1e-6) {
    return null;
  }
  const a = [one[2] + inset[0] * one.normal[0],
             one[3] + inset[0] * one.normal[1]];
  const b = [other[2] + inset[1] * other.normal[0],
             other[3] + inset[1] * other.normal[1]];
  const t = ((b[0] - a[0]) * other[1] - (b[1] - a[1]) * other[0]) / cross;
  return [a[0] + t * one[0], a[1] + t * one[1]];
}

/**
 * Moves the corners to where the sides fitted to the image's edges meet. A
 * corner stays where it was found when one of its sides was not fitted, or
 * when they would move it farther than reach. When trimming, the sides are
 * moved in where their edges are uneven (see TRIM_SHARE).
 * @param {cv.Mat} gray
 * @param {number[][]} corners
 * @param {number} reach
 * @param {boolean=} trim
 * @returns {number[][]}
 */
function refine(gray, corners, reach, trim) {
  const lines = corners.map(function (corner, k) {
    return sideLine(gray, corner, corners[(k + 1) % 4], reach);
  });
  const most = TRIM_MOST * Math.min(side(corners, 0), side(corners, 1),
                                    side(corners, 2), side(corners, 3));
  return corners.map(function (corner, k) {
    const one = lines[(k + 3) % 4];
    const other = lines[k];
    if (!one || !other) {
      return corner;
    }
    const meet = meeting(one, other, [0, 0]);
    if (!meet ||
        Math.hypot(meet[0] - corner[0], meet[1] - corner[1]) > reach) {
      return corner;
    }
    return trim ? meeting(one, other,
                          [Math.min(Math.max(one.uneven, TRIM_LEAST), most),
                           Math.min(Math.max(other.uneven, TRIM_LEAST),
                                    most)]) :
                  meet;
  });
}

/**
 * Maps corners normalised to a video frame into the photo's pixels, taking
 * the video as the middle of the photo: as wide as it where the photo is
 * taller in proportion, else as high.
 * @param {number[][]} corners
 * @param {number} frameAspect the frame's width over its height
 * @param {number} width the photo's
 * @param {number} height the photo's
 * @returns {number[][]}
 */
function fromFrame(corners, frameAspect, width, height) {
  const shownWidth = frameAspect >= width / height ? width :
                     height * frameAspect;
  const shownHeight = shownWidth / frameAspect;
  return corners.map(function (p) {
    return [(width - shownWidth) / 2 + p[0] * shownWidth,
            (height - shownHeight) / 2 + p[1] * shownHeight];
  });
}

/**
 * Handles the photo: straightens the cover found again in it, else where the
 * last frame had it, or asks for the photo again where it came out blurred or
 * the cover is nowhere.
 * @param {{bitmap: ImageBitmap, corners: ?number[][], frameAspect: number,
 *     frameLongSide: number}} message
 * @returns {Promise}
 */
async function photograph(message) {
  const bitmap = message.bitmap;
  const width = bitmap.width;
  const height = bitmap.height;
  const canvas = new OffscreenCanvas(width, height);
  const context = canvas.getContext('2d', {willReadFrequently: true});
  context.drawImage(bitmap, 0, 0);
  bitmap.close();
  const photo = cv.matFromImageData(context.getImageData(0, 0, width, height));
  try {
    return await straightenPhoto(photo, canvas, message);
  } finally {
    photo.delete();
  }
}

/**
 * Finds the cover in the photo, checks it against the last frame, and replies
 * with the straightened PNG or a request to take the photo again.
 * @param {cv.Mat} photo RGBA
 * @param {OffscreenCanvas} canvas the photo drawn
 * @param {Object} message as for photograph
 * @returns {Promise}
 */
async function straightenPhoto(photo, canvas, message) {
  const width = photo.cols;
  const height = photo.rows;
  const small = grayOf(canvas, message.frameLongSide);
  let corners;
  let blurred = false;
  try {
    corners = findCover(small.gray);
    if (corners) {
      // fitted on the copy first, as the frames are, so that the photo's
      // sides are searched near enough to where they are
      corners = refine(small.gray, corners, FRAME_REACH);
      // its sharpness at the frames' scale, against theirs
      blurred = lastSharpness !== null &&
                measures(small.gray, corners).sharpness <
                PHOTO_BLURRED * lastSharpness;
    }
  } finally {
    small.gray.delete();
  }
  let rejected = false;
  if (corners) {
    corners = corners.map(function (p) {
      return [p[0] / small.scale, p[1] / small.scale];
    });
    const xs = corners.map(function (p) { return p[0]; });
    const ys = corners.map(function (p) { return p[1]; });
    rejected = Math.min.apply(null, xs) < MARGIN * width ||
               Math.min.apply(null, ys) < MARGIN * height ||
               Math.max.apply(null, xs) > (1 - MARGIN) * width ||
               Math.max.apply(null, ys) > (1 - MARGIN) * height;
  }
  // the frames' corners, where the photo is turned as the frames are
  const turned = (width > height) !== (message.frameAspect > 1);
  const framed = message.corners && !turned &&
                 fromFrame(message.corners, message.frameAspect, width,
                           height);
  if (corners && framed && !rejected) {
    const areas = area(corners) / area(framed);
    rejected = areas > PHOTO_AREA || areas < 1 / PHOTO_AREA;
  }
  if (rejected) {
    corners = null;
  }
  if (corners && framed) {
    corners = aligned(corners, framed);
  }
  corners = corners || framed;
  if (corners) {
    const gray = new cv.Mat();
    try {
      cv.cvtColor(photo, gray, cv.COLOR_RGBA2GRAY);
      corners = refine(gray, corners,
                       Math.ceil(SEARCH_REACH / small.scale) + 1, true);
    } finally {
      gray.delete();
    }
  }
  if (!corners || blurred) {
    postMessage({type: 'retake', reason: corners ? 'blurred' : 'lost'});
    return;
  }
  postMessage({type: 'result', png: await straighten(photo, corners)});
}

/**
 * Returns the cover's side from its first corner to the second over the one
 * from the first to the last, as a rectangle seen through a pinhole camera
 * with its principal point at the photo's centre (Zhang and He, "Whiteboard
 * scanning and image enhancement", 2007).
 * @param {number[][]} corners
 * @param {number} width
 * @param {number} height
 * @returns {number}
 */
function proportions(corners, width, height) {
  const focal = FOCAL * Math.max(width, height);
  const m = corners.map(function (p) {
    return [p[0] - width / 2, p[1] - height / 2, 1];
  });
  /**
   * Returns the cross product of two 3-vectors.
   * @param {number[]} a
   * @param {number[]} b
   * @returns {number[]}
   */
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]];
  }
  /**
   * Returns the dot product of two 3-vectors.
   * @param {number[]} a
   * @param {number[]} b
   * @returns {number}
   */
  function dot(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }
  // m1 top left, m2 top right, m4 bottom right, m3 bottom left
  const m1 = m[0];
  const m2 = m[1];
  const m4 = m[2];
  const m3 = m[3];
  const k2 = dot(cross(m1, m4), m3) / dot(cross(m2, m4), m3);
  const k3 = dot(cross(m1, m4), m2) / dot(cross(m3, m4), m2);
  const n2 = [k2 * m2[0] - m1[0], k2 * m2[1] - m1[1], k2 * m2[2] - m1[2]];
  const n3 = [k3 * m3[0] - m1[0], k3 * m3[1] - m1[1], k3 * m3[2] - m1[2]];
  const f2 = focal * focal;
  const ratio = Math.sqrt((n2[0] * n2[0] + n2[1] * n2[1] +
                           f2 * n2[2] * n2[2]) /
                          (n3[0] * n3[0] + n3[1] * n3[1] +
                           f2 * n3[2] * n3[2]));
  // in a degenerate view, or corners dragged nearly into a line, the sides
  // as they are seen
  const seen = (side(corners, 0) + side(corners, 2)) /
               (side(corners, 1) + side(corners, 3));
  return Number.isFinite(ratio) && ratio > seen / 2 && ratio < 2 * seen ?
         ratio : seen;
}

/**
 * Straightens the cover in the photo, with as many pixels across and down as
 * its longer sides have there.
 * @param {cv.Mat} photo RGBA
 * @param {number[][]} corners
 * @returns {Promise<Blob>} a PNG
 */
async function straighten(photo, corners) {
  const ratio = proportions(corners, photo.cols, photo.rows);
  let height = Math.round(Math.max(side(corners, 1), side(corners, 3),
                                   side(corners, 0) / ratio,
                                   side(corners, 2) / ratio));
  let width = Math.max(1, Math.round(height * ratio));
  // never more pixels than the photo has, whatever corners are dragged
  const most = Math.min(1, Math.sqrt(photo.cols * photo.rows /
                                     (width * height)));
  width = Math.max(1, Math.floor(width * most));
  height = Math.max(1, Math.floor(height * most));
  const mats = [];
  let canvas;
  try {
    const source = cv.matFromArray(4, 1, cv.CV_32FC2,
                                   [].concat.apply([], corners));
    mats.push(source);
    const target = cv.matFromArray(4, 1, cv.CV_32FC2,
                                   [0, 0, width, 0, width, height, 0, height]);
    mats.push(target);
    const transform = cv.getPerspectiveTransform(source, target);
    mats.push(transform);
    const straight = new cv.Mat();
    mats.push(straight);
    cv.warpPerspective(photo, straight, transform, new cv.Size(width, height),
                       cv.INTER_CUBIC, cv.BORDER_REPLICATE);
    canvas = new OffscreenCanvas(straight.cols, straight.rows);
    canvas.getContext('2d').putImageData(
      new ImageData(new Uint8ClampedArray(straight.data), straight.cols,
                    straight.rows), 0, 0);
  } finally {
    mats.forEach(function (mat) { mat.delete(); });
  }
  return canvas.convertToBlob({type: 'image/png'});
}

/** Forgets the frames seen: another camera, or the photo taken again. */
function reset() {
  recent = [];
  missed = 0;
  streak = 0;
  sharpness = [];
  lastSharpness = null;
}

/** Handles the page's messages: init, frame, photo and reset. */
onmessage = function (event) {
  const message = event.data;
  /**
   * Tells the page that the step failed.
   * @param {*} error
   */
  function failed(error) {
    postMessage({type: 'failed', step: message.type,
                 error: String(error && error.message || error)});
  }
  try {
    if (message.type === 'init') {
      loadOpenCV();
    } else if (message.type === 'frame') {
      frame(message);
    } else if (message.type === 'photo') {
      photograph(message).catch(failed);
    } else if (message.type === 'reset') {
      reset();
    }
  } catch (error) {
    if (message.bitmap) {
      message.bitmap.close();
    }
    failed(error);
  }
};
