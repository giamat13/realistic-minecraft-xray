"""Radiograph patterns for one face of one model box (used by generate_mob_skeletons.py).

A pattern is an int array [rows, columns]: >0 is a bone of that gray, 0 is empty (soft tissue may show
there) and -1 is a real hole (eye socket, nostril) that stays black even inside flesh.

Face coordinates are anatomical, whatever the UV layout is:
  frontal (seen from the front/back)  columns = lateral, rows = top to bottom
  lateral (seen from a side)          columns = front to back, rows = top to bottom
  dorsal  (seen from above/below)     columns = lateral, rows = front to back"""
import math

import numpy as np

DENSE, BONE, MID, THIN, TOOTH = 215, 190, 168, 150, 232
HOLE = -1


def blank(rows, cols):
    return np.zeros((rows, cols), dtype=np.int16)


def put(a, row, col, value):
    row, col = int(row), int(col)
    if 0 <= row < a.shape[0] and 0 <= col < a.shape[1]:
        a[row, col] = value


def line(a, r0, c0, r1, c1, value):
    steps = int(max(abs(r1 - r0), abs(c1 - c0))) + 1
    for t in np.linspace(0, 1, steps * 2):
        put(a, math.floor(r0 + (r1 - r0) * t + 0.5), math.floor(c0 + (c1 - c0) * t + 0.5), value)


def centre(n, width):
    start = (n - width) // 2
    return range(max(0, start), min(n, start + width))


def edges(a, value, step=1):
    rows, cols = a.shape
    for r in range(rows):
        for c in range(cols):
            if (r in (0, rows - 1) or c in (0, cols - 1)) and (r + c) % step == 0:
                a[r, c] = value


def ring(a, cr, cc, rr, rc, value):
    for t in np.linspace(0, 2 * math.pi, int(8 * (rr + rc)) + 8):
        put(a, math.floor(cr + rr * math.sin(t)), math.floor(cc + rc * math.cos(t)), value)


# ---------------------------------------------------------------- skull and jaws
def vault(na, nb):
    """A wide cranium is thinner to the beam in the middle than a small one drawn solid."""
    return MID if min(na, nb) < 9 else 128


def skull(view, na, nb):
    a = blank(nb, na)
    if na <= 2 or nb <= 2:
        a[:] = BONE
        return a
    m = 1 if min(na, nb) >= 7 else 0
    if view == "frontal":
        side = 1 if na >= 9 else 0                              # keep a bridge between the eye sockets
        x0, x1, y0, y1 = side, na - 1 - side, m, nb - 1
        w, h = x1 - x0 + 1, y1 - y0 + 1
        a[y0:y1 + 1, x0:x1 + 1] = vault(na, nb)
        a[y0, x0:x1 + 1] = a[y0:y1 + 1, x0] = a[y0:y1 + 1, x1] = DENSE
        if w >= 4:
            a[y0, x0] = a[y0, x1] = 0
        if h >= 5:                                              # the mandible is narrower than the cranium
            jaw = max(1, h // 4)
            a[y1 - jaw + 1:y1 + 1, x0] = a[y1 - jaw + 1:y1 + 1, x1] = 0
            a[y1, x0 + 1:x1] = DENSE
        ew, eh = max(1, round(w / 4)), max(1, round(h / 5))
        ey = y0 + max(1, round(h * 0.3))
        left = x0 + max(1 if w >= 4 else 0, round(w * 0.26 - ew / 2))
        for ex in (left, x1 - (left - x0) - ew + 1):
            a[ey:ey + eh, ex:ex + ew] = HOLE
        if h >= 6:
            nose = ey + eh + (1 if h >= 8 else 0)
            for c in centre(na, 2 if w % 2 == 0 and w >= 6 else 1):
                put(a, nose, c, HOLE)
        if h >= 4:                                              # two interlocking tooth rows
            ty = y1 - 2 if h >= 7 else y1 - 1
            for c in range(x0 + 1, x1):
                put(a, ty, c, TOOTH if c % 2 == 0 else THIN)
                if h >= 8:
                    put(a, ty + 1, c, HOLE if c % 2 == 0 else TOOTH)
    elif view == "lateral":
        cr, cc, rr, rc = nb * 0.41, na * 0.58, max(1.0, nb * 0.41 - m * 0.5), max(1.0, na * 0.42 - m * 0.5)
        for r in range(nb):
            for c in range(na):
                d = ((r + 0.5 - cr) / rr) ** 2 + ((c + 0.5 - cc) / rc) ** 2
                if d <= 1.15:
                    a[r, c] = DENSE if d > 0.62 else MID
        top, low = int(nb * 0.3), max(int(nb * 0.3) + 1, int(nb * 0.68))
        a[top:low, m:max(m + 1, int(na * 0.45))] = MID                           # face
        a[top, m:int(na * 0.4)] = DENSE
        eh, ew = max(1, nb // 5), max(1, na // 5)
        er, ec = int(nb * 0.36), max(m + 1 if na >= 5 else 0, int(na * 0.2))
        a[er:er + eh, ec:ec + ew] = HOLE
        if na >= 6 and nb >= 6:
            put(a, int(nb * 0.52), int(na * 0.62), HOLE)                         # ear canal
        jaw_row = nb - 1
        if nb >= 5:
            for c in range(m, max(m + 1, int(na * 0.5))):
                put(a, low, c, TOOTH if c % 2 == 0 else THIN)
                if jaw_row - low >= 2:
                    put(a, low + 1, c, HOLE if c % 2 == 0 else TOOTH)
        a[jaw_row, m:max(m + 1, int(na * 0.66))] = DENSE
        line(a, jaw_row, int(na * 0.62), int(nb * 0.6), int(na * 0.68), BONE)    # jaw ramus
    else:
        for r in range(nb):
            t = (r + 0.5) / nb
            half = (na / 2 - m) * (0.65 + 0.35 * min(1.0, t / 0.55))
            if t > 0.8:
                half *= 1 - (t - 0.8) * 1.2
            lo, hi = int(round(na / 2 - half)), int(round(na / 2 + half)) - 1
            if (m and r in (0, nb - 1)) or hi < lo:
                continue
            a[r, lo:hi + 1] = vault(na, nb)
            put(a, r, lo, DENSE)
            put(a, r, hi, DENSE)
        a[m, :][a[m, :] > 0] = DENSE
        a[nb - 1 - m, :][a[nb - 1 - m, :] > 0] = DENSE
        for r in range(int(nb * 0.45), nb - 1 - m):                              # midline suture
            for c in centre(na, 1):
                if r % 2:
                    put(a, r, c, THIN)
        if na >= 5 and nb >= 5:
            ew, row = max(1, na // 5), max(1, int(nb * 0.18))
            for ec in (m + 1, na - 1 - m - ew):
                a[row:row + max(1, nb // 6), ec:ec + ew] = HOLE
    return a


def snout(view, na, nb):
    a = blank(nb, na)
    if view == "frontal":
        edges(a, BONE)
        if na >= 4 and nb >= 3:
            put(a, nb // 3, na // 4, HOLE)
            put(a, nb // 3, na - 1 - na // 4, HOLE)
            for c in centre(na, 1 if na % 2 else 2):
                a[:max(1, nb // 2), c] = THIN
        for c in range(na):
            a[nb - 1, c] = TOOTH if c % 2 == 0 else THIN
    elif view == "lateral":
        a[0, :] = BONE
        for c in range(na):
            a[nb - 1, c] = TOOTH if c % 2 == 0 else THIN
        if nb >= 3:
            a[nb - 2, :] = BONE
        if nb >= 5:
            line(a, nb - 2, na - 1, 0, na - 1, THIN)
    else:
        a[:, 0] = BONE
        a[:, na - 1] = BONE
        a[0, :] = TOOTH
        for c in centre(na, 1 if na % 2 else 2):
            a[:, c] = MID
    return a


def jaw(view, na, nb):
    a = blank(nb, na)
    if view == "lateral":
        a[nb - 1, :] = DENSE
        for c in range(na):
            a[0, c] = TOOTH if c % 2 == 0 else (THIN if nb < 3 else 0)
        line(a, nb - 1, na - 1, 0, na - 1, BONE)
    elif view == "frontal":
        a[nb - 1, :] = BONE
        for c in range(na):
            a[0, c] = TOOTH if c % 2 == 0 else (THIN if nb < 3 else 0)
        a[:, 0] = a[:, na - 1] = BONE
    else:
        a[:, 0] = a[:, na - 1] = BONE
        a[0, :] = DENSE
    return a


# ---------------------------------------------------------------- trunk
def spine_columns(n):
    return list(centre(n, 1 if n % 2 else (2 if n >= 4 else n)))


def trunk_vd(nl, ns, ribs, pelvis):
    """Ventrodorsal view: columns lateral, rows head to tail."""
    a = blank(ns, nl)
    mid = spine_columns(nl)
    margin = 1 if nl >= 8 else 0
    if ribs:
        first, last = int(ribs[0] * ns), max(int(ribs[0] * ns) + 1, int(math.ceil(ribs[1] * ns)))
        if ns >= 8 and ribs[0] > 0:
            a[max(0, first - 1), margin:nl - margin] = BONE                      # shoulder girdle
        for k, row in enumerate(range(first + (1 if ns >= 8 and ribs[0] > 0 else 0), last, 2)):
            for side in (-1, 1):
                start = mid[0] - 1 if side < 0 else mid[-1] + 1
                end = margin if side < 0 else nl - 1 - margin
                length = abs(end - start) + 1
                for i, col in enumerate(range(start, end + side, side)):
                    drop = 1 if length >= 4 and i >= length * 2 // 3 else 0
                    put(a, row + drop, col, BONE if k % 2 == 0 else MID)
    for r in range(ns):
        for c in mid:
            a[r, c] = DENSE if r % 2 == 0 else THIN
    if pelvis and ns >= 4:
        rows = max(2, round(ns * 0.24))
        top = ns - rows
        wing = max(1, nl // 4)
        a[top:ns, margin:nl - margin][a[top:ns, margin:nl - margin] != DENSE] = 0
        for k in range(rows):
            t = k / max(1, rows - 1)
            offset = margin + int(round(t * max(0, nl / 2 - margin - wing - 1)))
            for i in range(max(1, int(round(wing * (1.0 - 0.55 * t))))):
                put(a, top + k, offset + i, BONE)
                put(a, top + k, nl - 1 - offset - i, BONE)
        a[top, mid[0] - 1 if mid[0] else 0:mid[-1] + 2] = DENSE                   # sacrum
        if rows >= 3:
            a[ns - 1, nl // 4:nl - nl // 4] = MID                                # pubic arch
    return a


def trunk_lateral(ns, nv, ribs, pelvis):
    """Lateral view: columns head to tail, rows back (dorsal) to belly."""
    a = blank(nv, ns)
    row = 1 if nv >= 6 else 0
    thick = 2 if nv >= 10 else 1
    if ribs:
        first, last = int(ribs[0] * ns), max(int(ribs[0] * ns) + 1, int(math.ceil(ribs[1] * ns)))
        low = max(row + thick, int(nv * 0.8))
        for col in range(first + (1 if ns >= 6 else 0), last, 2):
            for v in range(row + thick, low):
                slant = 1 if v >= (row + low) // 2 + 1 else 0
                put(a, v, col + slant, BONE if v < low - 1 else MID)
        if nv >= 5 and ribs[0] < 0.5:
            a[min(nv - 1, low), first + 1:max(first + 2, int(first + (last - first) * 0.75))] = MID   # sternum
    if pelvis and ns >= 4:
        c0, c1 = int(ns * 0.74), ns - 1 - (1 if ns >= 8 else 0)
        bottom = max(row + thick + 1, int(nv * 0.62))
        a[row:min(nv, bottom + 1), c0:c1 + 1] = 0
        ring(a, (row + bottom + 1) / 2, (c0 + c1 + 1) / 2, max(0.8, (bottom - row) / 2),
             max(0.8, (c1 - c0) / 2), DENSE)
    for c in range(ns):
        for t in range(thick):
            put(a, row + t, c, DENSE if c % 2 == 0 else THIN)
    return a


def trunk_axial(nl, nv):
    """Looking along the spine: columns lateral, rows back to belly."""
    a = blank(nv, nl)
    if nl >= 4 and nv >= 4:
        ring(a, nv * 0.5, nl * 0.5, nv * 0.36, nl * 0.38, THIN)
        if nv >= 10 and nl >= 10:
            ring(a, nv * 0.5, nl * 0.5, nv * 0.22, nl * 0.24, THIN)
            for c in centre(nl, 1 if nl % 2 else 2):
                a[int(nv * 0.14):int(nv * 0.72), c] = 0
    size = 2 if nv >= 6 else 1
    for c in centre(nl, size if nl % 2 == 0 else max(1, size - 1)):
        a[(1 if nv >= 6 else 0):(1 if nv >= 6 else 0) + size, c] = DENSE
    for c in centre(nl, 2 if nl % 2 == 0 else 1):
        put(a, int(nv * 0.84), c, MID)
    return a


def torso(view, na, nb, upright, ribs=(0.08, 0.62), pelvis=True):
    if upright:
        if view == "frontal":
            return trunk_vd(na, nb, ribs, pelvis)
        if view == "lateral":
            return trunk_lateral(nb, na, ribs, pelvis)[::-1, :].T.copy()
        return trunk_axial(na, nb)[::-1, :].copy()
    if view == "frontal":
        return trunk_axial(na, nb)
    if view == "lateral":
        return trunk_lateral(na, nb, ribs, pelvis)
    return trunk_vd(na, nb, ribs, pelvis)


# ---------------------------------------------------------------- long parts: [rows = along, columns = across]
def cross_section(na, nb, hollow=True):
    a = blank(nb, na)
    wa = 1 if na <= 3 else max(2, na // 3)
    wb = 1 if nb <= 3 else max(2, nb // 3)
    for r in centre(nb, wb):
        for c in centre(na, wa):
            a[r, c] = BONE
    if hollow and wa >= 3 and wb >= 3:
        a[nb // 2, na // 2] = THIN
    return a


def limb(n_long, n_cross, flesh=True, foot=True):
    """Proximal end in row 0: thigh/upper arm, joint, two lower bones, toes."""
    a = blank(n_long, n_cross)
    if n_cross <= 1:
        a[:, 0] = BONE
        if n_long >= 6:
            a[n_long // 2, 0] = THIN
        return a
    if n_cross == 2:
        width = 1 if flesh else 2
    else:
        width = 2 if n_cross <= 5 else max(2, round(n_cross * 0.3))
    cols = list(centre(n_cross, width))
    flare = 2 if n_cross >= 6 else (1 if n_cross >= 3 else 0)       # ends never span the whole limb
    knob = list(centre(n_cross, min(n_cross, width + flare)))
    for c in cols:
        a[:, c] = BONE
    if n_long >= 6:
        for c in knob:
            a[0, c] = DENSE
    if n_long >= 5:
        knee = n_long // 2
        if n_cross >= 4:                                         # two bones below the joint
            a[knee:, :] = 0
            thick = max(1, width // 2)
            first = cols[0]
            second = min(n_cross - 1, first + thick + 1)
            a[knee + 1:, first:first + thick] = BONE
            a[knee + 1:, second:second + max(1, thick // 2)] = THIN
        if n_long >= 10:                                         # flared joint ends only where there is room
            for c in knob:
                a[knee - 1, c] = DENSE
                a[knee + 1, c] = DENSE
        a[knee, :] = 0
        if n_cross <= 3:
            put(a, knee, cols[0], THIN)
    if foot and n_long >= 4:
        if n_cross >= 4:
            if n_long >= 10:                                     # ankle bones
                a[n_long - 2, :] = 0
                for c in knob:
                    a[n_long - 2, c] = MID
            for c in range(n_cross):                             # separate toes
                a[n_long - 1, c] = BONE if c % 2 == (0 if n_cross % 2 else 1) else 0
        else:
            a[n_long - 1, :] = DENSE
    return a


def vertebrae(n_long, n_cross, thick=None, period=3):
    a = blank(n_long, n_cross)
    width = thick or max(1, round(n_cross * 0.35))
    cols = list(centre(n_cross, width))
    for r in range(n_long):
        phase = r % period
        if phase == period - 1 and n_long > 2:
            for c in cols[len(cols) // 2:len(cols) // 2 + 1]:
                a[r, c] = THIN
            continue
        for c in cols:
            a[r, c] = DENSE if phase == 0 else MID
        if phase == 0 and n_cross >= 5:
            put(a, r, cols[0] - 1, THIN)
            put(a, r, cols[-1] + 1, THIN)
    return a


# ---------------------------------------------------------------- wings and fins: [rows = chord, columns = span]
def membrane_wing(chord, span):
    a = blank(chord, span)
    w, h = span - 1, chord - 1
    wrist = (min(h, round(h * 0.08)), round(w * 0.45))
    line(a, round(h * 0.3), 0, wrist[0], wrist[1], DENSE)
    for end_row, end_col in ((0, w), (h * 0.55, w), (h, w * 0.78), (h, w * 0.52), (h, w * 0.24)):
        line(a, wrist[0], wrist[1], round(end_row), round(end_col), BONE if end_row == 0 else MID)
    if span >= 20:
        line(a, round(h * 0.3) + 1, 0, wrist[0] + 1, wrist[1], BONE)
    put(a, wrist[0], wrist[1], TOOTH)
    return a


def bird_wing(chord, span):
    a = blank(chord, span)
    w, h = span - 1, chord - 1
    shoulder, elbow, wrist, tip = (0, 0), (round(h * 0.75), round(w * 0.45)), (round(h * 0.2), round(w * 0.62)), (round(h * 0.55), w)
    for start, end in ((shoulder, elbow), (elbow, wrist), (wrist, tip)):
        line(a, start[0], start[1], end[0], end[1], BONE)
    for joint in (shoulder, elbow, wrist):
        put(a, joint[0], joint[1], DENSE)
    return a


def fin_rays(length, across):
    """Rays leaving the base (row 0)."""
    a = blank(length, across)
    a[0, :] = MID
    for c in range(0, across, 2):
        spread = (c - (across - 1) / 2) * 0.25
        line(a, 0, c, length - 1, c + spread, THIN)
    return a


# ---------------------------------------------------------------- fish and other bodies
def fish_trunk(view, na, nb):
    a = blank(nb, na)
    if view == "lateral":
        mid = nb // 2
        reach = max(1, int(nb * 0.34))
        for c in range(0, na, 2):
            for k in range(1, reach + 1):
                put(a, mid - k, c + (k > 1), MID if k < reach else THIN)
                put(a, mid + k, c + (k > 1), MID if k < reach else THIN)
        for c in range(na):
            a[mid, c] = DENSE if c % 2 == 0 else BONE
    elif view == "dorsal":
        for r in range(nb):
            for c in centre(na, 1 if na % 2 else 2):
                a[r, c] = DENSE if r % 2 == 0 else THIN
            if r % 2 == 0 and na >= 5:
                a[r, 1:na - 1][a[r, 1:na - 1] == 0] = THIN
    else:
        for c in centre(na, 1 if na % 2 else 2):
            a[nb // 2, c] = DENSE
            a[max(0, nb // 2 - nb // 3):nb // 2, c] = THIN
        if na >= 6:
            ring(a, nb * 0.55, na * 0.5, nb * 0.3, na * 0.32, THIN)
    return a


def fish_body(view, na, nb):
    """A whole fish in one box: skull in front, backbone behind it."""
    if view == "frontal":
        return skull("frontal", na, nb)
    if view == "lateral":
        head = max(2, round(na * 0.42))
        a = fish_trunk("lateral", na, nb)
        a[:, :head] = skull("lateral", head, nb)
        return a
    head = max(2, round(nb * 0.42))
    a = fish_trunk("dorsal", na, nb)
    a[:head, :] = skull("dorsal", na, head)
    return a


# ---------------------------------------------------------------- shells, exoskeletons, soft bodies
def chitin(na, nb):
    a = blank(nb, na)
    edges(a, 132 if min(na, nb) > 3 else 108, step=1 if min(na, nb) > 3 else 2)
    if na >= nb and na >= 6:
        a[:, 3:na - 2:4] = np.where(a[:, 3:na - 2:4] == 0, 118, a[:, 3:na - 2:4])
        a[1:nb - 1, :][:, 3:na - 2:4] = 0
        a[1:nb - 1:2, 3:na - 2:4] = 112
    elif nb > na and nb >= 6:
        a[3:nb - 2:4, 1:na - 1:2] = 112
    return a


def jointed_leg(n_long, n_cross):
    a = blank(n_long, n_cross)
    col = (n_cross - 1) // 2
    for r in range(n_long):
        phase = r % 5
        a[r, col] = DENSE if phase == 0 else (0 if phase == 4 and n_long > 6 else THIN)
    return a


def shell(view, na, nb):
    a = blank(nb, na)
    edges(a, THIN)
    if view == "dorsal":
        mid = list(centre(na, 1 if na % 2 else 2))
        for c in mid:
            a[:, c] = DENSE
        for r in range(2, nb - 1, 4):
            for c in range(1, na - 1):
                drop = abs(c - na // 2) // 4
                if r + drop < nb - 1:
                    a[r + drop, c] = max(a[r + drop, c], THIN)
        if na >= 8 and nb >= 8:
            ring(a, nb * 0.5, na * 0.5, nb * 0.38, na * 0.38, MID)
    elif view == "lateral":
        if nb >= 4:
            a[1, 1:na - 1] = MID
        for c in range(3, na - 2, 4):
            a[1:nb - 1:1 if nb < 6 else 2, c] = THIN
    return a


def box_shell(view, na, nb):
    """Calcareous box shell (shulker): walls and growth bands."""
    a = blank(nb, na)
    edges(a, MID)
    if view != "dorsal":
        for r in range(3, nb - 1, 4):
            for c in range(1, na - 1):
                if (c + r // 4) % 3:
                    a[r, c] = 112
    elif na >= 8:
        ring(a, nb * 0.5, na * 0.5, nb * 0.28, na * 0.28, 112)
    return a


def spiral_shell(view, na, nb):
    a = blank(nb, na)
    small = min(na, nb) < 8                                         # a tiny wall would fill the whole face
    edges(a, 132, step=2 if small else 1)
    cr, cc = nb * 0.52, na * 0.55
    if view == "lateral":
        previous = None
        turns = 2.6 * 2 * math.pi
        grow = math.log(max(na, nb) * 0.5) / turns
        for t in np.linspace(0, turns, 420):
            radius = math.exp(grow * t)
            point = (cr + radius * math.sin(t) * nb / max(na, nb), cc + radius * math.cos(t) * na / max(na, nb))
            if previous:
                line(a, previous[0], previous[1], point[0], point[1], DENSE)
            previous = point
        for t in np.arange(turns - 2 * math.pi, turns, math.pi / 4):             # septa of the chambers
            outer, inner = math.exp(grow * t), math.exp(grow * (t - 2 * math.pi))
            line(a, cr + inner * math.sin(t) * nb / max(na, nb), cc + inner * math.cos(t) * na / max(na, nb),
                 cr + outer * math.sin(t) * nb / max(na, nb), cc + outer * math.cos(t) * na / max(na, nb), THIN)
    elif not small:
        for scale in (0.38, 0.2):
            ring(a, cr, na * 0.5, nb * scale, na * scale, MID)
    return a


def eggs(na, nb):
    a = blank(nb, na)
    if na >= 4 and nb >= 4:
        for r in range(2, nb - 2, 4):
            for c in range(2 + (r // 4 % 2), na - 2, 4):
                ring(a, r + 0.5, c + 0.5, 1.3, 1.3, BONE)
    return a


def soft_outline(na, nb, value=96, step=2):
    a = blank(nb, na)
    edges(a, value, step=step)
    return a


def wood(na, nb):
    a = soft_outline(na, nb, 128)
    for c in range(1, na - 1, 3):
        for r in range(nb):
            if (r + c * 2) % 7 < 5:
                a[r, c] = 104
    return a


def branches(na, nb):
    a = blank(nb, na)
    line(a, nb - 1, na // 2, 0, na // 2, BONE)
    for k, r in enumerate(range(nb - 3, 0, -3)):
        side = -1 if k % 2 else 1
        line(a, r, na // 2, max(0, r - 2), na // 2 + side * max(1, na // 2 - 1), MID)
    return a


def filled(na, nb, value=BONE, rim=DENSE):
    a = np.full((nb, na), value, dtype=np.int16)
    edges(a, rim)
    return a
