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
TYPES = {
    'Консольный разъёмный (60°)': dict(
        ret=60.0,
        text='Балка с крючком, возврат под 60°: защёлку можно открыть без поломки (корпуса, '
             'батарейные отсеки, сервисные крышки). Сквозное окно позволяет подцепить крючок.'),
    'Консольный неразъёмный (90°)': dict(
        ret=90.0,
        text='Балка с крючком, возврат под 90°: после защёлкивания не открывается без '
             'разрушения или отжатия балки. Для крышек, которые открывать не нужно.'),
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
    k1 = taper_k1(p.taper_pct)
    eps = max(p.strain_pct, 0.01) / 100.0
    auto_len = beam_length(p.arm_t, p.engage, eps, p.taper_pct)
    if p.length is None:
        L = max(MIN_LENGTH, math.ceil(auto_len * 2.0) / 2.0)
    else:
        L = p.length
        if L < auto_len - 1e-6:
            warns.append('Длина балки меньше расчётной (%.1f мм): деформация выше допустимой.' % auto_len)
    strain = p.arm_t * p.engage / (2.0 * k1 * L * L) * 100.0

    lead_len = p.engage / math.tan(math.radians(p.lead_deg))
    ret_len = 0.0 if p.ret_deg >= 89.5 else p.engage / math.tan(math.radians(p.ret_deg))

    # сила на конце балки, дающая прогиб engage (изгиб вдоль слоёв)
    P = p.E * p.arm_w * p.arm_t ** 3 * p.engage / (12.0 * k1 * L ** 3)
    ins = _ramp_force(P, p.lead_deg)
    rem = None if p.ret_deg >= 89.5 else _ramp_force(P, p.ret_deg)

    skin = p.wall - p.arm_t
    if p.through:
        if skin < MIN_SKIN - 1e-6:
            warns.append('Стенка %.1f мм при балке %.1f мм: упор в окне тоньше %.1f мм.'
                         % (p.wall, p.arm_t, MIN_SKIN))
    else:
        left = skin - (p.engage + p.clearance)
        if left < MIN_SKIN - 1e-6:
            warns.append('Для глухого окна нужна стенка не меньше %.1f мм (сейчас %.1f мм). '
                         'Включите «Сквозное окно» или увеличьте стенку.'
                         % (p.arm_t + p.engage + p.clearance + MIN_SKIN, p.wall))
    lip_total = lead_len + LIP_FLAT + ret_len + 2 * p.clearance
    if lip_total > L - 2.0:
        warns.append('Крючок слишком длинный для балки: увеличьте длину или уменьшите зацеп.')
    if p.arm_w < 3.0 * 0.4:
        warns.append('Ширина балки меньше 3 линий сопла.')
    if p.arm_t * p.taper_pct / 100.0 < 0.8:
        warns.append('Толщина балки на конце меньше 0.8 мм (2 линии сопла): увеличьте толщину или конус.')

    root_r = 0.0
    if p.fillet:
        avail = skin - MIN_SKIN - p.clearance          # сколько можно «съесть» из упора у корня
        rf = min(0.5 * p.arm_t, avail)
        room = L - lip_total - 1.0
        rf = min(rf, room)
        if rf >= 0.3:
            root_r = round(rf * 10.0) / 10.0
        else:
            warns.append('Скругление корня отключено: стенка слишком тонкая или балка слишком короткая.')

    if p.pins and skin < MIN_SKIN - 1e-6:
        warns.append('Штифты: стенка слишком тонкая, остаток над штифтом меньше %.1f мм.' % MIN_SKIN)
    return Result(L, strain, lead_len, ret_len, P, ins, rem, warns, root_r)


Poly = List[Tuple[float, float]]


def arm_polygon(p: Params, r: Result) -> Poly:
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


def pocket_polygon(p: Params, r: Result) -> Poly:
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


def pin_offset(p: Params) -> float:
    """Смещение оси штифта от оси балки вдоль стенки, мм."""
    return p.arm_w / 2.0 + p.clearance + PIN_GAP + PIN_W / 2.0


def pin_polygon(p: Params) -> Poly:
    """Профиль штифта на половине с балкой (с фаской на конце)."""
    n0 = -p.wall
    n1 = n0 + p.arm_t
    ch = min(0.6, p.arm_t / 2.0)
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
    n1 = n0 + p.arm_t
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
