// Mark the characters of a cover sequence on its scan.  The slider turns the
// cover until the chosen character stands upright, then a box is drawn by
// dragging, by tapping two opposite corners, or with the arrow keys (Shift
// resizes).  The chosen row gets three corners of the box on the scan, x in
// 1/10000 of its width and y in 1/10000 of its height, and scan_aspect.
(() => {
    const root = document.querySelector('[data-cover-boxes]');
    const img = root && root.querySelector('[data-box-image]');
    if (!img) return;
    const slider = root.querySelector('[data-box-angle]');
    const NAMES = ['top_left_x', 'top_left_y', 'top_right_x', 'top_right_y',
                   'bottom_left_x', 'bottom_left_y', 'scan_aspect'];
    // The value kept between low and high
    const clamp = (value, low, high) => Math.min(Math.max(value, low), high);
    // A new SVG element with the attributes, added to the parent
    const make = (parent, tag, attributes) => {
        const node = document.createElementNS('http://www.w3.org/2000/svg',
                                              tag);
        Object.entries(attributes).forEach(
            ([name, value]) => node.setAttribute(name, value));
        return parent.appendChild(node);
    };
    // The drawing over the scan, once it is loaded or failed to load
    const start = () => {
        // The hidden attribute loses to the class block
        img.style.display = 'none';
        root.querySelector('[data-box-missing]').hidden = img.naturalWidth > 0;
        if (!img.naturalWidth) {
            // Nothing to turn or clear without the scan
            slider.closest('label').hidden = true;
            root.querySelector('[data-box-clear]').style.display = 'none';
            return;
        }
        const measured = 10000 * img.naturalHeight / img.naturalWidth;
        // In units as pixels the scan is 10000 wide and H high: y = field * S
        const aspect = Math.round(measured), H = aspect, S = aspect / 10000;
        const svg = make(root, 'svg', {
            class: img.className, tabindex: 0, role: 'application',
            'aria-label': img.alt, 'aria-describedby': 'box-keys',
            cursor: 'crosshair'});
        const chosen = root.querySelector('[data-box-chosen]');
        img.after(svg);
        svg.style.touchAction = 'pinch-zoom';
        const cover = make(svg, 'g', {});
        make(cover, 'image', {href: img.currentSrc || img.src, width: 10000,
                              height: H, preserveAspectRatio: 'none'});
        const layer = make(cover, 'g', {'pointer-events': 'none',
                                        class: 'text-red-600'});
        // The values of the fields of a row, to see whether they changed
        const fields = row => row.inputs.map(input => input.value).join();
        const rows = [...document.querySelectorAll('[data-box-row]')].map(
            row => ({
                number: row.dataset.boxNumber,
                radio: row.querySelector('[data-box-select]'),
                inputs: NAMES.map(
                    name => row.querySelector(`[name$="-${name}"]`)),
                remove: row.querySelector('[name$="-DELETE"]'),
                status: row.querySelector('[data-box-status]'),
                cutOut: row.querySelector('[data-box-cut-out]')}));
        rows.forEach(row => {
            row.loaded = fields(row);
            // A row sent back by the server with Remove ticked is saved too
            row.saved = Boolean(row.inputs[0].value) || row.remove.checked;
            row.removedLoaded = row.remove.checked;
            row.savedStatus = row.status.textContent;
        });
        // Whether a row holds what the page loaded, box and Remove
        const unchanged = row => fields(row) === row.loaded
            && row.remove.checked === row.removedLoaded;
        let current, theta = 0, cos, sin, first, from, down, moved;
        let before, removed;
        // Top left, top right, bottom right, bottom left of a row, null if
        // not marked or removed
        const corners = row => {
            if (row.remove.checked) return null;
            const v = row.inputs.slice(0, 6).map(input => input.value);
            if (v.includes('')) return null;
            const [a, b, c, d, e, f] = v.map(Number);
            return [[a, b * S], [c, d * S], [c + e - a, (d + f - b) * S],
                    [e, f * S]];
        };
        // The angle of the top side of a box on the scan, in degrees
        const angle = ([tl, tr]) => Math.round(
            Math.atan2(tr[1] - tl[1], tr[0] - tl[0]) * 180 / Math.PI);
        // Centre and sides of a row, null if not marked.  The box last written
        // is kept while the fields hold it, so turning adds no rounding errors.
        const box = row => {
            const points = corners(row);
            if (!points) return null;
            if (row.kept === fields(row)) return row.box;
            const [tl, tr, , bl] = points;
            return {x: (tr[0] + bl[0]) / 2, y: (tr[1] + bl[1]) / 2,
                    w: Math.hypot(tr[0] - tl[0], tr[1] - tl[1]),
                    h: Math.hypot(bl[0] - tl[0], bl[1] - tl[1])};
        };
        // Every marked row: the chosen one solid, the others dashed and
        // numbered
        const draw = () => {
            layer.replaceChildren();
            rows.forEach(row => {
                const points = corners(row), mine = row === current;
                row.status.textContent = unchanged(row) ? row.savedStatus
                    : points ? 'drawn, not saved' : 'removed, not saved';
                // The cut-out of the saved box, until the box changes
                if (row.cutOut) row.cutOut.hidden = !unchanged(row);
                if (!points) return;
                make(layer, 'polygon', {points: points.join(' '),
                    fill: mine ? 'currentColor' : 'none', 'fill-opacity': 0.15,
                    stroke: 'currentColor', 'stroke-width': 2,
                    'stroke-dasharray': mine ? 'none' : '6 4',
                    'vector-effect': 'non-scaling-stroke'});
                const {x, y} = box(row);
                if (mine) return;
                make(layer, 'text', {
                    x, y, transform: `rotate(${theta} ${x} ${y})`,
                    'font-size': 800, 'text-anchor': 'middle', fill: 'white',
                    stroke: 'black', 'stroke-width': 60,
                    'paint-order': 'stroke'}).textContent = row.number;
            });
            if (first) make(layer, 'circle', {cx: first.x, cy: first.y,
                                              r: 120, fill: 'currentColor'});
        };
        // Show the cover turned back by theta, in the box around it; the slider
        // gives that turn on screen, from 180 to the left to 180 to the right
        const turn = degrees => {
            theta = Number(degrees);
            cos = Math.cos(theta * Math.PI / 180);
            sin = Math.sin(theta * Math.PI / 180);
            slider.value = -theta;
            root.querySelector('[data-box-angle-value]').textContent =
                slider.value;
            const w = 10000 * Math.abs(cos) + H * Math.abs(sin);
            const h = 10000 * Math.abs(sin) + H * Math.abs(cos);
            svg.setAttribute('viewBox',
                             `${5000 - w / 2} ${(H - h) / 2} ${w} ${h}`);
            cover.setAttribute('transform', `rotate(${-theta} 5000 ${H / 2})`);
            draw();
        };
        // Write the chosen row from the centre and sides of a box upright on
        // screen; half a unit inside the edge, the rounded centre stays on it
        const put = ({x, y, w, h}) => {
            [x, y, w, h] = [clamp(x, 0.5, 9999.5), clamp(y, S / 2, H - S / 2),
                            Math.max(w, 10), Math.max(h, 10)];
            const tl = [x - w / 2 * cos + h / 2 * sin,
                        y - w / 2 * sin - h / 2 * cos];
            const values = [tl, [tl[0] + w * cos, tl[1] + w * sin],
                            [tl[0] - h * sin, tl[1] + h * cos]]
                .flatMap(([px, py]) => [px, py / S]).concat(aspect);
            current.inputs.forEach((input, i) => {
                input.value = Math.round(values[i]);
            });
            current.box = {x, y, w, h};
            current.kept = fields(current);
            draw();
        };
        // A marked row brings its angle, a new one keeps the current angle; the
        // chosen row is in bold and named above the cover
        const select = row => {
            current = row;
            first = null;
            rows.forEach(r => r.radio.closest('tr').classList.toggle(
                'font-bold', r === row));
            chosen.textContent = row ? 'Marking: ' + row.radio.labels[0]
                .textContent.trim().replace(/\s+/g, ' ') : '';
            const points = row && corners(row);
            turn(points ? angle(points) : theta);
        };
        // Pointer on the scan, kept on the drawing
        const point = event => {
            const r = svg.getBoundingClientRect();
            return new DOMPoint(clamp(event.clientX, r.left, r.right),
                                clamp(event.clientY, r.top, r.bottom))
                .matrixTransform(cover.getScreenCTM().inverse());
        };
        // Upright box with the opposite corners a and b; drawing keeps the row
        const span = (a, b) => {
            const dx = b.x - a.x, dy = b.y - a.y;
            current.remove.checked = false;
            put({x: (a.x + b.x) / 2, y: (a.y + b.y) / 2,
                 w: Math.abs(dx * cos + dy * sin),
                 h: Math.abs(dy * cos - dx * sin)});
        };
        svg.addEventListener('pointerdown', event => {
            if (!event.isPrimary) stop(event);
            if (!current || event.button || !event.isPrimary) return;
            event.preventDefault();
            svg.focus();
            svg.setPointerCapture(event.pointerId);
            before = current.inputs.map(input => input.value);
            removed = current.remove.checked;
            down = [event.clientX, event.clientY];
            moved = Boolean(first);  // the second of two taps draws at once
            from = first || point(event);
            first = null;
            if (moved) span(from, point(event));
        });
        svg.addEventListener('pointermove', event => {
            if (!from || !moved && Math.hypot(
                event.clientX - down[0], event.clientY - down[1]) < 5) return;
            moved = true;
            span(from, point(event));
        });
        // A tap marks the first of two opposite corners; a pinch zoom cancels,
        // and so does a second finger, which may come after the first has moved
        const stop = event => {
            if (from && (event.type === 'pointercancel' || !event.isPrimary)) {
                current.inputs.forEach((input, i) => {
                    input.value = before[i];
                });
                current.remove.checked = removed;
            } else if (from && !moved) first = from;
            from = null;
            draw();
        };
        svg.addEventListener('pointerup', stop);
        svg.addEventListener('pointercancel', stop);
        svg.addEventListener('keydown', event => {
            const [dx, dy] = {ArrowLeft: [-100, 0], ArrowRight: [100, 0],
                              ArrowUp: [0, -100],
                              ArrowDown: [0, 100]}[event.key] || [];
            if (dx === undefined || !current || event.altKey || event.ctrlKey
                || event.metaKey) return;
            event.preventDefault();
            current.remove.checked = false;
            const b = box(current) || {x: 5000, y: H / 2, w: 2000, h: 2000};
            put(event.shiftKey ? {...b, w: b.w + dx, h: b.h + dy}
                               : {...b, x: b.x + dx * cos - dy * sin,
                                  y: b.y + dx * sin + dy * cos});
        });
        slider.addEventListener('input', () => {
            turn(-slider.value);
            const b = current && box(current);
            if (b) put(b);
        });
        rows.forEach(row => {
            row.radio.addEventListener('change', () => select(row));
            row.remove.addEventListener('change', draw);
        });
        // Clear takes the box off the chosen row and puts the cover straight;
        // a saved box needs Remove as well, an empty row changes nothing on
        // saving.
        root.querySelector('[data-box-clear]').addEventListener('click', () => {
            if (!current) return;
            current.inputs.forEach(input => { input.value = ''; });
            current.remove.checked = current.saved;
            first = null;
            turn(0);
        });
        select(rows.find(row => row.radio.checked));
    };
    if (img.complete) start();
    else ['load', 'error'].forEach(type => img.addEventListener(type, start));
})();
