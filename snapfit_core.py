# -*- coding: utf-8 -*-
"""
Чистая математика и геометрия защёлки (без зависимости от Fusion API).
Все размеры в миллиметрах, углы в градусах. Перевод в см/радианы делает аддин.

Локальная система координат защёлки (2D-профиль):
    d  - ось вдоль нормали к плоскости реза, + это сторона половины с балкой
    n  - наружная нормаль стенки, 0 = наружная поверхность стенки
Балка уходит в сторону -d (через плоскость реза в другую половину),
крючок смотрит наружу (+n) и заходит в окно стенки другой половины.
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Стартовые значения для FDM. Это консервативные точки отсчёта, а не истина:
# деформация ~10-15% от удлинения при разрыве (с запасом на межслойную адгезию),
# E - модуль для нагрузки ВДОЛЬ слоёв.
MATERIALS = {
    'PLA':  dict(arm_t=1.2, engage=0.6, clearance=0.20, strain=1.0, E=3000.0, lead=30.0),
    'PETG': dict(arm_t=1.6, engage=0.8, clearance=0.25, strain=2.5, E=2000.0, lead=30.0),
    'ABS':  dict(arm_t=1.6, engage=0.8, clearance=0.30, strain=1.5, E=2100.0, lead=30.0),
    'ASA':  dict(arm_t=1.6, engage=0.8, clearance=0.30, strain=1.5, E=2000.0, lead=30.0),
    'PA (нейлон)': dict(arm_t=1.6, engage=1.0, clearance=0.30, strain=4.0, E=1500.0, lead=30.0),
}
DEFAULT_MATERIAL = 'PETG'

# Типы защёлок: угол возврата (сторона, которая держит) и описание для диалога.
#   style='inset'   - балка лежит внутри толщины стенки (нужна стенка от ~2.5 мм);
#   style='overlay' - накладная: балка стоит ВНУТРИ корпуса вдоль стенки, крючок уходит в окно
#                     стенки другой половины (для тонких стенок 1.2-2 мм).
TYPES = {
    'Консольный разъёмный (60°)': dict(
        ret=60.0, style='inset', shape='straight',
        text='Балка с крючком внутри стенки, возврат под 60°: защёлку можно открыть без поломки '
             '(корпуса, батарейные отсеки, сервисные крышки). Нужна стенка от ~2.5 мм.'),
    'Консольный неразъёмный (90°)': dict(
        ret=90.0, style='inset', shape='straight',
        text='Балка с крючком внутри стенки, возврат под 90°: не открывается без отжатия или '
             'разрушения балки. Для крышек, которые открывать не нужно.'),
    'Накладной для тонких стенок, разъёмный (60°)': dict(
        ret=60.0, style='overlay', shape='straight',
        text='Балка стоит внутри корпуса вдоль стенки (не в толще стенки), крючок заходит в окно '
             'стенки другой половины. Для стенок 1.2-2 мм. Окно лучше сквозное.'),
    'Накладной для тонких стенок, неразъёмный (90°)': dict(
        ret=90.0, style='overlay', shape='straight',
        text='То же, но возврат 90°: открыть без отжатия балки нельзя.'),
    'U-образный накладной, разъёмный (60°)': dict(
        ret=60.0, style='overlay', shape='u',
        text='Балка сложена буквой U: большой прогиб на короткой длине, крючок на свободной ветви '
             'у линии разъёма. Занимает ~4.5 мм вглубь корпуса. Длина и усилия приближённые.'),
}
DEFAULT_TYPE = 'Консольный разъёмный (60°)'

FRICTION = 0.3          # коэффициент трения пластик-пластик
MIN_LENGTH = 6.0        # минимальная длина балки, мм
LIP_FLAT = 1.0          # длина площадки на вершине крючка, мм
ROOT_OVERLAP = 1.0      # заход балки вглубь своей половины, мм
MIN_SKIN = 0.8          # минимальная толщина «упора» в окне, мм
PIN_W = 2.0             # ширина направляющего штифта, мм
PIN_L = 3.0             # длина штифта, мм
PIN_GAP = 1.5           # зазор между балкой и штифтом (по материалу), мм
OVERLAY_ROOT_W = 2.0    # ширина опоры накладной балки у стенки своей половины, мм
U_GAP = 1.0             # просвет между ветвями U-образной балки, мм
U_TIP_GAP = 2.0         # расстояние от свободного конца U-ветви до опоры (упор для крючка), мм
SQRT2 = math.sqrt(2.0)


@dataclass
class Params:
    arm_t: float = 1.6          # толщина балки у корня
    engage: float = 0.8         # высота крючка (величина зацепа) = прогиб балки
    arm_w: float = 5.0          # ширина балки
    wall: float = 2.4           # толщина стенки корпуса в месте защёлки
    clearance: float = 0.25     # зазор
    strain_pct: float = 2.5     # допустимая деформация, %
    E: float = 2000.0           # модуль упругости, МПа
    lead_deg: float = 30.0      # угол заведения
    ret_deg: float = 60.0       # угол возврата (90 = неразъёмная)
    length: Optional[float] = None   # None = авторасчёт
    through: bool = True        # сквозное окно
    taper_pct: float = 50.0     # толщина на конце балки, % от корня (100 = без конуса)
    fillet: bool = True         # скругление корня балки
    pins: bool = True           # направляющие штифты по бокам
    overlay: bool = False       # накладная защёлка для тонких стенок
    shape: str = 'straight'     # 'straight' или 'u' (U-образная, только накладная)


@dataclass
class Result:
    length: float
    strain_pct: float
    lead_len: float
    ret_len: float
    deflection_force: float     # Н, сила прогиба на величину engage
    insertion_force: float      # Н
    removal_force: Optional[float]  # None = неразъёмная
    warnings: List[str] = field(default_factory=list)
    root_r: float = 0.0         # радиус скругления корня, мм (0 = нет)
    pins_ok: bool = True        # штифты можно строить (стенка достаточно толстая)


def taper_k1(taper_pct: float) -> float:
    """
    K1 = integral_0^1 (1-u)^2 / (1 - a*u)^3 du, a = 1 - h_tip/h_root.
    Для постоянного сечения K1 = 1/3. Нужен для конической балки.
    """
    a = 1.0 - max(min(taper_pct, 100.0), 10.0) / 100.0
    n = 200
    h = 1.0 / n
    s = 0.0
    for i in range(n + 1):
        u = i * h
        f = (1.0 - u) ** 2 / (1.0 - a * u) ** 3
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        s += w * f
    return s * h / 3.0


def beam_length(t: float, y: float, strain: float, taper_pct: float = 100.0) -> float:
    """
    Длина консоли: eps = t*y / (2*K1*L^2).
    Для постоянного сечения 2*K1 = 2/3 и формула сводится к L = sqrt(1.5*t*y/eps).
    """
    return math.sqrt(t * y / (2.0 * taper_k1(taper_pct) * strain))


def _ramp_force(P: float, angle_deg: float) -> float:
    a = math.radians(angle_deg)
    den = 1.0 - FRICTION * math.tan(a)
    if den <= 0.05:
        return float('inf')
    return P * (FRICTION + math.tan(a)) / den


def compute(p: Params) -> Result:
    warns: List[str] = []
    is_u = p.overlay and p.shape == 'u'
    taper = 100.0 if is_u else p.taper_pct          # у U-образной ветви сечение постоянное
    k1 = taper_k1(taper)
    eps = max(p.strain_pct, 0.01) / 100.0

    lead_len = p.engage / math.tan(math.radians(p.lead_deg))
    ret_len = 0.0 if p.ret_deg >= 89.5 else p.engage / math.tan(math.radians(p.ret_deg))
    hook_len = lead_len + LIP_FLAT + ret_len

    if is_u:
        # две ветви работают как две консоли подряд: эквивалентная длина = sqrt(2) * длина ветви
        auto_len = beam_length(p.arm_t, p.engage, eps, 100.0) / SQRT2
        min_len = max(MIN_LENGTH, p.arm_t + U_TIP_GAP + hook_len + 1.5)
        auto_len = max(auto_len, min_len)
        leg_k = SQRT2
    else:
        auto_len = beam_length(p.arm_t, p.engage, eps, taper)
        min_len = MIN_LENGTH
        leg_k = 1.0
    if p.length is None:
        L = max(min_len, math.ceil(auto_len * 2.0) / 2.0)
    else:
        L = p.length
        if L < auto_len - 1e-6:
            warns.append('Длина балки меньше расчётной (%.1f мм): деформация выше допустимой.' % auto_len)
        if is_u and L < min_len - 1e-6:
            warns.append('Для U-образной балки длина не меньше %.1f мм (иначе крючок упирается в изгиб).' % min_len)
    L_eq = L * leg_k
    strain = p.arm_t * p.engage / (2.0 * k1 * L_eq * L_eq) * 100.0

    # сила на конце балки, дающая прогиб engage (изгиб вдоль слоёв)
    P = p.E * p.arm_w * p.arm_t ** 3 * p.engage / (12.0 * k1 * L_eq ** 3)
    if is_u:
        P *= SQRT2
    ins = _ramp_force(P, p.lead_deg)
    rem = None if p.ret_deg >= 89.5 else _ramp_force(P, p.ret_deg)

    skin = p.wall - p.arm_t
    pins_ok = True
    if p.overlay:
        if not p.through:
            left = p.wall - (p.engage + p.clearance)
            if left < MIN_SKIN - 1e-6:
                warns.append('Для глухого окна нужна стенка не меньше %.1f мм (сейчас %.1f мм). '
                             'Включите «Сквозное окно».' % (p.engage + p.clearance + MIN_SKIN, p.wall))
        if p.wall < 0.8:
            warns.append('Стенка тоньше 0.8 мм: окно ослабит её слишком сильно.')
        if p.pins and p.wall - 0.4 < 0.8:
            pins_ok = False
            warns.append('Штифты отключены: для них нужна стенка не меньше 1.2 мм.')
    else:
        if p.through:
            if skin < MIN_SKIN - 1e-6:
                warns.append('Стенка %.1f мм при балке %.1f мм: упор в окне тоньше %.1f мм. '
                             'Для тонкой стенки выберите «Накладной» тип.' % (p.wall, p.arm_t, MIN_SKIN))
        else:
            left = skin - (p.engage + p.clearance)
            if left < MIN_SKIN - 1e-6:
                warns.append('Для глухого окна нужна стенка не меньше %.1f мм (сейчас %.1f мм). '
                             'Включите «Сквозное окно» или увеличьте стенку.'
                             % (p.arm_t + p.engage + p.clearance + MIN_SKIN, p.wall))
        if p.pins and skin < MIN_SKIN - 1e-6:
            warns.append('Штифты: стенка слишком тонкая, остаток над штифтом меньше %.1f мм.' % MIN_SKIN)

    lip_total = hook_len + 2 * p.clearance
    if not is_u and lip_total > L - 2.0:
        warns.append('Крючок слишком длинный для балки: увеличьте длину или уменьшите зацеп.')
    if p.arm_w < 3.0 * 0.4:
        warns.append('Ширина балки меньше 3 линий сопла.')
    if not is_u and p.arm_t * taper / 100.0 < 0.8:
        warns.append('Толщина балки на конце меньше 0.8 мм (2 линии сопла): увеличьте толщину или конус.')

    root_r = 0.0
    if p.fillet and not is_u:
        if p.overlay:
            avail = p.clearance + 0.4                  # высота ступеньки между балкой и стенкой
        else:
            avail = skin - MIN_SKIN - p.clearance      # сколько можно «съесть» из упора у корня
        rf = min(0.5 * p.arm_t, avail, L - lip_total - 1.0)
        if rf >= 0.3:
            root_r = round(rf * 10.0) / 10.0
        else:
            warns.append('Скругление корня отключено: не хватает места (стенка или длина балки).')
    return Result(L, strain, lead_len, ret_len, P, ins, rem, warns, root_r, pins_ok)


Poly = List[Tuple[float, float]]


def inset_arm_polygon(p: Params, r: Result) -> Poly:
    """
    Профиль балки с крючком в координатах (d, n), мм.
    Наружная грань плоская (n_a), внутренняя сужается к концу (конус).
    У корня наружной грани добавляется дуга-галтель.
    """
    n_in = -p.wall
    n_a = -p.wall + p.arm_t
    n_tip_in = n_a - p.arm_t * (min(max(p.taper_pct, 10.0), 100.0) / 100.0)
    y = p.engage
    L = r.length
    d0 = -L
    pts: Poly = [
        (ROOT_OVERLAP, n_in),
        (0.0, n_in),
        (d0, n_tip_in),
        (d0, n_a),
        (d0 + r.lead_len, n_a + y),
        (d0 + r.lead_len + LIP_FLAT, n_a + y),
        (d0 + r.lead_len + LIP_FLAT + r.ret_len, n_a),
    ]
    rf = r.root_r
    if rf > 0:
        cd, cn = -rf, n_a + rf       # центр дуги галтели
        for k in range(6):
            th = math.radians(-90.0 + k * 18.0)
            pts.append((cd + rf * math.cos(th), cn + rf * math.sin(th)))
        pts.append((ROOT_OVERLAP, n_a + rf))
    else:
        pts.append((ROOT_OVERLAP, n_a))
    return pts


def inset_pocket_polygon(p: Params, r: Result) -> Poly:
    """Профиль выреза в противоположной половине: канал под балку + окно под крючок."""
    n_in = -p.wall
    n_a = -p.wall + p.arm_t
    cl = p.clearance
    L = r.length
    d_ledge = -L + r.lead_len + LIP_FLAT + r.ret_len + cl     # упор крючка
    top = 1.0 if p.through else n_a + p.engage + cl
    pts: Poly = [
        (0.5, n_in - 0.5),
        (-L - cl, n_in - 0.5),
        (-L - cl, top),
        (d_ledge, top),
        (d_ledge, n_a + cl),
    ]
    rf = r.root_r
    if rf > 0:      # выемка под галтель корня
        pts += [(-rf - cl, n_a + cl), (-rf - cl, n_a + rf + cl), (0.5, n_a + rf + cl)]
    else:
        pts.append((0.5, n_a + cl))
    return pts


def _tip_k(p: Params) -> float:
    return min(max(p.taper_pct, 10.0), 100.0) / 100.0


def overlay_arm_polygon(p: Params, r: Result) -> Poly:
    """
    Накладная балка (координаты (d, n), мм): стоит ВНУТРИ корпуса вдоль стенки на расстоянии clearance,
    опора (мост) соединяет её со стенкой своей половины (d >= 0), крючок смотрит наружу.
    """
    cl = p.clearance
    n_top = -p.wall - cl                  # наружная грань балки
    n_bot = n_top - p.arm_t
    n_tip_bot = n_top - p.arm_t * _tip_k(p)
    n_root = -p.wall + 0.5                # заход опоры в стенку своей половины
    h = cl + p.engage                     # высота крючка над гранью балки
    d0 = -r.length
    pts: Poly = [
        (OVERLAY_ROOT_W, n_root),
        (OVERLAY_ROOT_W, n_bot),
        (0.0, n_bot),
        (d0, n_tip_bot),
        (d0, n_top),
        (d0 + r.lead_len, n_top + h),
        (d0 + r.lead_len + LIP_FLAT, n_top + h),
        (d0 + r.lead_len + LIP_FLAT + r.ret_len, n_top),
    ]
    rf = r.root_r
    if rf > 0:                            # галтель в вогнутом углу между балкой и опорой
        cd, cn = -rf, n_top + rf
        for k in range(6):
            th = math.radians(-90.0 + k * 18.0)
            pts.append((cd + rf * math.cos(th), cn + rf * math.sin(th)))
    else:
        pts.append((0.0, n_top))
    pts.append((0.0, n_root))
    return pts


def u_arm_polygon(p: Params, r: Result) -> Poly:
    """
    U-образная накладная балка: внутренняя ветвь идёт от опоры (d >= 0) в глубину корпуса, изгиб на
    d = -L, наружная ветвь возвращается к линии разъёма и несёт крючок на свободном конце.
    """
    cl = p.clearance
    t = p.arm_t
    n_top = -p.wall - cl
    n_o_bot = n_top - t                   # низ наружной ветви
    n_i_top = n_o_bot - U_GAP             # верх внутренней ветви
    n_bot = n_i_top - t
    n_root = -p.wall + 0.5
    h = cl + p.engage
    d_turn = -r.length
    d_tip = -U_TIP_GAP                    # свободный конец наружной ветви
    d_h0 = d_tip - (r.lead_len + LIP_FLAT + r.ret_len)
    return [
        (OVERLAY_ROOT_W, n_root),
        (OVERLAY_ROOT_W, n_bot),
        (d_turn, n_bot),
        (d_turn, n_top),
        (d_h0, n_top),
        (d_h0 + r.lead_len, n_top + h),
        (d_h0 + r.lead_len + LIP_FLAT, n_top + h),
        (d_tip, n_top),
        (d_tip, n_o_bot),
        (d_turn + t, n_o_bot),
        (d_turn + t, n_i_top),
        (0.0, n_i_top),
        (0.0, n_root),
    ]


def overlay_pocket_polygon(p: Params, r: Result) -> Poly:
    """Окно в стенке другой половины под крючок накладной балки (канал не нужен: балка внутри корпуса)."""
    cl = p.clearance
    n_lo = -p.wall - 0.2
    top = 1.0 if p.through else -p.wall + p.engage + cl
    if p.shape == 'u':
        d_a = -U_TIP_GAP - (r.lead_len + LIP_FLAT + r.ret_len) - cl
        d_ledge = -U_TIP_GAP + cl
    else:
        d_a = -r.length - cl
        d_ledge = -r.length + r.lead_len + LIP_FLAT + r.ret_len + cl
    return [(d_ledge, n_lo), (d_a, n_lo), (d_a, top), (d_ledge, top)]


def arm_polygon(p: Params, r: Result) -> Poly:
    if p.overlay:
        return u_arm_polygon(p, r) if p.shape == 'u' else overlay_arm_polygon(p, r)
    return inset_arm_polygon(p, r)


def pocket_polygon(p: Params, r: Result) -> Poly:
    return overlay_pocket_polygon(p, r) if p.overlay else inset_pocket_polygon(p, r)


def pin_t(p: Params) -> float:
    """Толщина штифта: у накладной защёлки не больше толщины стенки минус 0.4 мм."""
    return min(p.arm_t, p.wall - 0.4) if p.overlay else p.arm_t


def pin_offset(p: Params) -> float:
    """Смещение оси штифта от оси балки вдоль стенки, мм."""
    return p.arm_w / 2.0 + p.clearance + PIN_GAP + PIN_W / 2.0


def pin_polygon(p: Params) -> Poly:
    """Профиль штифта на половине с балкой (с фаской на конце)."""
    n0 = -p.wall
    n1 = n0 + pin_t(p)
    ch = min(0.6, pin_t(p) / 2.0)
    return [
        (ROOT_OVERLAP, n0),
        (-PIN_L, n0),
        (-PIN_L, n1 - ch),
        (-PIN_L + ch, n1),
        (ROOT_OVERLAP, n1),
    ]


def pin_pocket_polygon(p: Params) -> Poly:
    """Профиль гнезда под штифт на другой половине."""
    n0 = -p.wall
    n1 = n0 + pin_t(p)
    cl = p.clearance
    return [
        (0.5, n0 - 0.5),
        (-PIN_L - cl, n0 - 0.5),
        (-PIN_L - cl, n1 + cl),
        (0.5, n1 + cl),
    ]


def polygon_area(poly: Poly) -> float:
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def format_report(p: Params, r: Result) -> str:
    rem = 'неразъёмная' if r.removal_force is None else ('%.0f Н' % r.removal_force)
    ins = '∞' if math.isinf(r.insertion_force) else '%.1f Н' % r.insertion_force
    lines = [
        'Длина балки: <b>%.1f мм</b> (деформация %.2f %%)' % (r.length, r.strain_pct),
        'Крючок: заведение %.1f мм, возврат %.1f мм' % (r.lead_len, r.ret_len),
        'Конец балки: %.1f мм, галтель корня: %s' % (
            p.arm_t * min(max(p.taper_pct, 10.0), 100.0) / 100.0,
            ('%.1f мм' % r.root_r) if r.root_r > 0 else 'нет'),
        'Усилие защёлкивания ~ %s, разъединения: %s' % (ins, rem),
        'Минимальная стенка: %.1f мм' % (p.arm_t + MIN_SKIN),
    ]
    for w in r.warnings:
        lines.append('<font color="#c0392b">⚠ %s</font>' % w)
    return '<br>'.join(lines)
