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
# деформация учитывает слабую межслойную адгезию, E - модуль для нагрузки ВДОЛЬ слоёв.
MATERIALS = {
    'PLA':  dict(arm_t=1.2, engage=0.6, clearance=0.20, strain=1.0, E=3000.0, lead=30.0, ret=90.0),
    'PETG': dict(arm_t=1.6, engage=0.8, clearance=0.25, strain=2.5, E=2000.0, lead=30.0, ret=90.0),
    'ABS':  dict(arm_t=1.6, engage=0.8, clearance=0.30, strain=2.0, E=2100.0, lead=30.0, ret=90.0),
    'ASA':  dict(arm_t=1.6, engage=0.8, clearance=0.30, strain=2.0, E=2000.0, lead=30.0, ret=90.0),
    'PA (нейлон)': dict(arm_t=1.6, engage=1.0, clearance=0.30, strain=4.0, E=1500.0, lead=30.0, ret=90.0),
}
DEFAULT_MATERIAL = 'PETG'

FRICTION = 0.3          # коэффициент трения пластик-пластик
MIN_LENGTH = 6.0        # минимальная длина балки, мм
LIP_FLAT = 1.0          # длина площадки на вершине крючка, мм
ROOT_OVERLAP = 1.0      # заход балки вглубь своей половины, мм
MIN_SKIN = 0.8          # минимальная толщина «упора» в окне, мм


@dataclass
class Params:
    arm_t: float = 1.6          # толщина балки
    engage: float = 0.8         # высота крючка (величина зацепа) = прогиб балки
    arm_w: float = 5.0          # ширина балки
    wall: float = 2.4           # толщина стенки корпуса в месте защёлки
    clearance: float = 0.25     # зазор
    strain_pct: float = 2.5     # допустимая деформация, %
    E: float = 2000.0           # модуль упругости, МПа
    lead_deg: float = 30.0      # угол заведения
    ret_deg: float = 90.0       # угол возврата (90 = неразъёмная, 45 = разъёмная)
    length: Optional[float] = None   # None = авторасчёт
    through: bool = True        # сквозное окно


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


def beam_length(t: float, y: float, strain: float) -> float:
    """Длина консоли постоянного сечения: eps = 1.5 * t * y / L^2."""
    return math.sqrt(1.5 * t * y / strain)


def _ramp_force(P: float, angle_deg: float) -> float:
    a = math.radians(angle_deg)
    den = 1.0 - FRICTION * math.tan(a)
    if den <= 0.05:
        return float('inf')
    return P * (FRICTION + math.tan(a)) / den


def compute(p: Params) -> Result:
    warns: List[str] = []
    eps = max(p.strain_pct, 0.01) / 100.0
    auto_len = beam_length(p.arm_t, p.engage, eps)
    if p.length is None:
        L = max(MIN_LENGTH, math.ceil(auto_len * 2.0) / 2.0)
    else:
        L = p.length
        if L < auto_len - 1e-6:
            warns.append('Длина балки меньше расчётной (%.1f мм): деформация выше допустимой.' % auto_len)
    strain = 1.5 * p.arm_t * p.engage / (L * L) * 100.0

    lead_len = p.engage / math.tan(math.radians(p.lead_deg))
    ret_len = 0.0 if p.ret_deg >= 89.5 else p.engage / math.tan(math.radians(p.ret_deg))

    P = p.E * p.arm_w * p.arm_t ** 3 * p.engage / (4.0 * L ** 3)
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
    return Result(L, strain, lead_len, ret_len, P, ins, rem, warns)


Poly = List[Tuple[float, float]]


def arm_polygon(p: Params, r: Result) -> Poly:
    """Профиль балки с крючком в координатах (d, n), мм."""
    n_in = -p.wall
    n_a = -p.wall + p.arm_t
    y = p.engage
    L = r.length
    d0 = -L
    return [
        (ROOT_OVERLAP, n_in),
        (d0, n_in),
        (d0, n_a),
        (d0 + r.lead_len, n_a + y),
        (d0 + r.lead_len + LIP_FLAT, n_a + y),
        (d0 + r.lead_len + LIP_FLAT + r.ret_len, n_a),
        (ROOT_OVERLAP, n_a),
    ]


def pocket_polygon(p: Params, r: Result) -> Poly:
    """Профиль выреза в противоположной половине: канал под балку + окно под крючок."""
    n_in = -p.wall
    n_a = -p.wall + p.arm_t
    cl = p.clearance
    L = r.length
    d_ledge = -L + r.lead_len + LIP_FLAT + r.ret_len + cl     # упор крючка
    top = 1.0 if p.through else n_a + p.engage + cl
    return [
        (0.5, n_in - 0.5),
        (-L - cl, n_in - 0.5),
        (-L - cl, top),
        (d_ledge, top),
        (d_ledge, n_a + cl),
        (0.5, n_a + cl),
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
        'Усилие защёлкивания ~ %s, разъединения: %s' % (ins, rem),
        'Минимальная стенка: %.1f мм' % (p.arm_t + MIN_SKIN),
    ]
    for w in r.warnings:
        lines.append('<font color="#c0392b">⚠ %s</font>' % w)
    return '<br>'.join(lines)
