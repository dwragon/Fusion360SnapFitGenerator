# -*- coding: utf-8 -*-
"""
Snap-Fit Generator для Fusion 360.

Выбираешь тело, плоскость/кривую реза и точки защёлок, материал печати.
Аддин делит тело на две половины и в каждой точке строит консольную защёлку
(балка с крючком на одной половине + канал и окно на другой).
"""
import importlib.util
import math
import os
import sys
import traceback

import adsk.core
import adsk.fusion

def _load_core():
    """
    Грузим snapfit_core.py напрямую из папки аддина под уникальным именем.
    Все аддины Fusion живут в одном процессе Python и делят sys.modules: обычный
    'import snapfit_core' может вернуть кэш старой версии или модуль из другой копии аддина.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snapfit_core.py')
    name = 'snapfit_generator_core'
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # нужно для dataclass
    spec.loader.exec_module(mod)
    return mod


core = _load_core()

CMD_ID = 'SnapFitGeneratorCmd'
PANEL_ID = 'SolidCreatePanel'
CM = 0.1  # мм -> см (внутренние единицы Fusion)

_app = None
_ui = None
_handlers = []


# ----------------------------------------------------------------- vectors ---
def _v(x, y, z):
    return adsk.core.Vector3D.create(x, y, z)


def _pt_add(p, v, s=1.0):
    """Точка p + v * s."""
    q = p.copy()
    w = v.copy()
    w.scaleBy(s)
    q.translateBy(w)
    return q


def _unit(v):
    w = v.copy()
    w.normalize()
    return w


# ------------------------------------------------------------ input helpers ---
def _find(inputs, cid):
    item = inputs.itemById(cid)
    if item:
        return item
    for i in range(inputs.count):
        child = inputs.item(i)
        grp = adsk.core.GroupCommandInput.cast(child)
        if grp:
            r = _find(grp.children, cid)
            if r:
                return r
    return None


def _mm(inputs, cid):
    return _find(inputs, cid).value / CM


def _set_mm(inputs, cid, mm):
    _find(inputs, cid).value = mm * CM


def read_params(inputs):
    auto = _find(inputs, 'autoLen').value
    return core.Params(
        arm_t=_mm(inputs, 'arm_t'),
        engage=_mm(inputs, 'engage'),
        arm_w=_mm(inputs, 'arm_w'),
        wall=_mm(inputs, 'wall'),
        clearance=_mm(inputs, 'clearance'),
        strain_pct=_find(inputs, 'strain').value,
        E=_find(inputs, 'E').value,
        lead_deg=math.degrees(_find(inputs, 'lead').value),
        ret_deg=math.degrees(_find(inputs, 'ret').value),
        length=None if auto else _mm(inputs, 'length'),
        through=_find(inputs, 'through').value,
        taper_pct=_find(inputs, 'taper').value,
        fillet=_find(inputs, 'fillet').value,
        pins=_find(inputs, 'pins').value,
    )


def apply_preset(inputs, name):
    m = core.MATERIALS.get(name)
    if not m:
        return
    _set_mm(inputs, 'arm_t', m['arm_t'])
    _set_mm(inputs, 'engage', m['engage'])
    _set_mm(inputs, 'clearance', m['clearance'])
    _find(inputs, 'strain').value = m['strain']
    _find(inputs, 'E').value = m['E']
    _find(inputs, 'lead').value = math.radians(m['lead'])


def apply_type(inputs, name):
    t = core.TYPES.get(name)
    if t:
        _find(inputs, 'ret').value = math.radians(t['ret'])


def update_info(inputs):
    try:
        p = read_params(inputs)
        auto_wall = _find(inputs, 'autoWall').value
        _find(inputs, 'wall').isEnabled = not auto_wall
        if auto_wall:
            p.wall = p.arm_t + 10.0  # реальная стенка станет известна при построении: ложных предупреждений не даём
        _find(inputs, 'length').isEnabled = not _find(inputs, 'autoLen').value
        if _find(inputs, 'autoLen').value:
            _set_mm(inputs, 'length', core.compute(p).length)
        r = core.compute(p)
        tname = _find(inputs, 'ctype').selectedItem.name
        desc = core.TYPES.get(tname, {}).get('text', '')
        _find(inputs, 'info').formattedText = '<i>%s</i><br><br>%s' % (desc, core.format_report(p, r))
    except Exception:
        pass


# ------------------------------------------------------------ command setup ---
class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isExecutedWhenPreEmpted = False
            inputs = cmd.commandInputs
            sc = adsk.core.SelectionCommandInput
            vi = adsk.core.ValueInput

            s = inputs.addSelectionInput('body', 'Тело', 'Тело, которое нужно разрезать')
            s.addSelectionFilter(sc.SolidBodies)
            s.setSelectionLimits(1, 1)

            s = inputs.addSelectionInput(
                'cut', 'Плоскость / кривая реза',
                'Конструкторская плоскость, грань, поверхность или эскизная кривая')
            s.addSelectionFilter(sc.ConstructionPlanes)
            s.addSelectionFilter(sc.Faces)
            s.addSelectionFilter(sc.SketchCurves)
            s.setSelectionLimits(1, 0)   # можно выбрать несколько линий эскиза, как в Split Body

            s = inputs.addSelectionInput(
                'pts', 'Точки защёлок',
                'Точки на внешней поверхности стенки, лежащие на линии реза')
            s.addSelectionFilter(sc.SketchPoints)
            s.addSelectionFilter(sc.ConstructionPoints)
            s.addSelectionFilter(sc.Vertices)
            s.setSelectionLimits(1, 0)

            b = inputs.addBoolValueInput('projPts', 'Режим кривой: точки на кривой, стенки найти самому',
                                         True, '', True)
            b.tooltip = 'Для эскизной кривой реза'
            b.tooltipDescription = ('Ставьте точки прямо на кривую в эскизе. Аддин пойдёт от точки '
                                    'перпендикулярно плоскости эскиза и найдёт наружную стенку тела. '
                                    'Точки, уже лежащие на стенке, остаются как есть.')
            inputs.addBoolValueInput('bothSides', 'Защёлки на обеих противоположных стенках', True, '', False)

            dd = inputs.addDropDownCommandInput(
                'material', 'Материал печати', adsk.core.DropDownStyles.TextListDropDownStyle)
            for name in core.MATERIALS:
                dd.listItems.add(name, name == core.DEFAULT_MATERIAL)

            tt = inputs.addDropDownCommandInput(
                'ctype', 'Тип защёлки', adsk.core.DropDownStyles.TextListDropDownStyle)
            for name in core.TYPES:
                tt.listItems.add(name, name == core.DEFAULT_TYPE)
            tt.tooltip = 'Тип защёлки'
            tt.tooltipDescription = '\n\n'.join('%s: %s' % (k, v['text']) for k, v in core.TYPES.items())

            g = inputs.addGroupCommandInput('params', 'Параметры защёлки').children
            m = core.MATERIALS[core.DEFAULT_MATERIAL]
            ret0 = core.TYPES[core.DEFAULT_TYPE]['ret']
            g.addBoolValueInput('autoWall', 'Толщину стенки брать с модели', True, '', True)
            g.addValueInput('wall', 'Толщина стенки (вручную)', 'mm', vi.createByReal(2.4 * CM))
            g.addValueInput('arm_t', 'Толщина балки', 'mm', vi.createByReal(m['arm_t'] * CM))
            g.addValueInput('arm_w', 'Ширина балки', 'mm', vi.createByReal(5.0 * CM))
            g.addValueInput('engage', 'Величина зацепа', 'mm', vi.createByReal(m['engage'] * CM))
            g.addValueInput('clearance', 'Зазор', 'mm', vi.createByReal(m['clearance'] * CM))
            g.addFloatSpinnerCommandInput('strain', 'Допустимая деформация, %', '',
                                          0.1, 10.0, 0.1, m['strain'])
            g.addFloatSpinnerCommandInput('E', 'Модуль E, МПа', '', 100.0, 5000.0, 100.0, m['E'])
            g.addValueInput('lead', 'Угол заведения', 'deg', vi.createByReal(math.radians(m['lead'])))
            g.addValueInput('ret', 'Угол возврата (90 = неразъёмно)', 'deg',
                            vi.createByReal(math.radians(ret0)))
            g.addFloatSpinnerCommandInput('taper', 'Конус: толщина на конце, % от корня', '',
                                          30.0, 100.0, 5.0, 50.0)
            g.addBoolValueInput('fillet', 'Скругление корня балки', True, '', True)
            g.addBoolValueInput('pins', 'Направляющие штифты по бокам', True, '', True)
            g.addBoolValueInput('autoLen', 'Длина балки по расчёту', True, '', True)
            g.addValueInput('length', 'Длина балки', 'mm', vi.createByReal(10.0 * CM))
            g.addBoolValueInput('through', 'Сквозное окно в стенке', True, '', True)
            g.addBoolValueInput('flip', 'Балка на другой половине', True, '', False)

            inputs.addTextBoxCommandInput('info', 'Расчёт', '', 12, True)
            update_info(inputs)

            for cls, ev in ((ExecuteHandler, cmd.execute),
                            (InputChangedHandler, cmd.inputChanged),
                            (ValidateHandler, cmd.validateInputs)):
                h = cls()
                ev.add(h)
                _handlers.append(h)
        except Exception:
            _ui.messageBox('Ошибка создания диалога:\n' + traceback.format_exc())


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            inputs = args.inputs
            if args.input.id == 'material':
                apply_preset(inputs, _find(inputs, 'material').selectedItem.name)
            elif args.input.id == 'ctype':
                apply_type(inputs, _find(inputs, 'ctype').selectedItem.name)
            update_info(inputs)
        except Exception:
            pass


class ValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            i = args.inputs
            ok = (_find(i, 'body').selectionCount == 1 and
                  _find(i, 'cut').selectionCount >= 1 and
                  _find(i, 'pts').selectionCount >= 1)
            for cid in ('wall', 'arm_t', 'arm_w', 'engage', 'clearance', 'length'):
                if _find(i, cid).value <= 0:
                    ok = False
            args.areInputsValid = ok
        except Exception:
            args.areInputsValid = False


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        design = adsk.fusion.Design.cast(_app.activeProduct)
        try:
            inputs = args.command.commandInputs
            body = adsk.fusion.BRepBody.cast(_find(inputs, 'body').selection(0).entity)
            cut_in = _find(inputs, 'cut')
            cuts = [cut_in.selection(k).entity for k in range(cut_in.selectionCount)]
            cut = cuts[0]
            if len(cuts) > 1 and not all(hasattr(c, 'parentSketch') for c in cuts):
                raise UserError('Несколько объектов реза можно выбирать только для линий эскиза. '
                                'Плоскость или грань выбирайте по одной.')
            pts_in = _find(inputs, 'pts')
            pts = [_point_of(pts_in.selection(k).entity) for k in range(pts_in.selectionCount)]
            params = read_params(inputs)
            flip = _find(inputs, 'flip').value
            auto_wall = _find(inputs, 'autoWall').value
            build(design, body, cut, pts, params, flip, auto_wall,
                  _find(inputs, 'projPts').value, _find(inputs, 'bothSides').value, cuts)
        except Exception as e:
            msg = str(e) if isinstance(e, UserError) else traceback.format_exc()
            _ui.messageBox('Не удалось построить защёлки:\n\n' + msg +
                           '\n\nИзменения откатаны (если нет - Ctrl+Z).')


# --------------------------------------------------------------- geometry ---
class UserError(Exception):
    pass


def _point_of(e):
    for cls, attr in ((adsk.fusion.SketchPoint, 'worldGeometry'),
                      (adsk.fusion.ConstructionPoint, 'geometry'),
                      (adsk.fusion.BRepVertex, 'geometry')):
        o = cls.cast(e)
        if o:
            return getattr(o, attr)
    raise UserError('Неподдерживаемый тип точки.')


def _fresh(design, ent):
    """Перечитать объект по токену (ссылки могут устареть после операций в таймлайне)."""
    try:
        r = design.findEntityByToken(ent.entityToken)
        if r and len(r) > 0:
            return r[0]
    except Exception:
        pass
    return ent


def _face_normal_at(face, q):
    ev = face.evaluator
    ok, prm = ev.getParameterAtPoint(q)
    if not ok:
        raise UserError('Не удалось получить нормаль поверхности.')
    ok, nrm = ev.getNormalAtParameter(prm)
    if not ok:
        raise UserError('Не удалось получить нормаль поверхности.')
    return nrm


def _closest(faces, p):
    """[(dist, face, closest_point)] для списка граней."""
    mm = _app.measureManager
    out = []
    for f in faces:
        r = mm.measureMinimumDistance(p, f)
        out.append((r.value, f, r.positionTwo))
    return out


def _cut_frame(cut_ent, faces, p):
    """Ближайшая точка на поверхности реза и её нормаль."""
    pl = adsk.fusion.ConstructionPlane.cast(cut_ent)
    if pl:
        g = pl.geometry
        n = _unit(g.normal)
        dist = _v(p.x - g.origin.x, p.y - g.origin.y, p.z - g.origin.z).dotProduct(n)
        return _pt_add(p, n, -dist), n
    best = min(_closest(faces, p), key=lambda t: t[0])
    return best[2], _unit(_face_normal_at(best[1], best[2]))


def _outer_normal(body, d, p):
    """Ближайшая к p точка поверхности тела и наружная нормаль; грани, параллельные резу, не в приоритете."""
    cands = _closest(body.faces, p)
    mind = min(c[0] for c in cands)
    if mind > 0.3:  # 3 мм
        raise UserError('Точка лежит дальше 3 мм от поверхности тела. Поставьте её на внешнюю '
                        'поверхность стенки в месте реза.')
    near = [c for c in cands if c[0] <= mind + 0.001]
    scored = []
    for dist, f, q in near:
        n = _unit(_face_normal_at(f, q))
        scored.append((abs(n.dotProduct(d)), n, q))
    _, n, q = min(scored, key=lambda t: t[0])
    test = _pt_add(q, n, 0.01)
    if body.pointContainment(test) == adsk.fusion.PointContainment.PointInsidePointContainment:
        n.scaleBy(-1.0)
    return q, n


def _resolve_cut_tool(design, comp, body, cut_ent, cuts=None):
    """Возвращает (инструмент для Split Body, список граней для нормалей, созданная поверхность|None)."""
    if adsk.fusion.ConstructionPlane.cast(cut_ent):
        return cut_ent, [], None
    face = adsk.fusion.BRepFace.cast(cut_ent)
    if face:
        return face, [face], None
    if hasattr(cut_ent, 'parentSketch'):  # эскизная кривая -> поверхность, выдавленная перпендикулярно эскизу
        bb = body.boundingBox
        size = bb.minPoint.distanceTo(bb.maxPoint) * 2.0
        if cuts and len(cuts) > 1:      # несколько выбранных линий -> один путь
            coll = adsk.core.ObjectCollection.create()
            for c in cuts:
                coll.add(c)
            path = comp.features.createPath(coll, False)
        else:                           # одна линия: Fusion сам подтянет связанную цепочку
            path = comp.features.createPath(cut_ent, True)
        exts = comp.features.extrudeFeatures
        ei = exts.createInput(path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ei.isSolid = False
        ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(size), True)
        feat = exts.add(ei)
        surf = feat.bodies.item(0)
        return surf, [surf.faces.item(i) for i in range(surf.faces.count)], surf
    raise UserError('Неподдерживаемый тип инструмента реза.')


def _measure_wall(comp, q_out, N):
    """Толщина стенки, мм: от наружной точки вглубь (-N) до первой внутренней грани. None, если не вышло."""
    try:
        eps = 0.005  # 0.05 мм внутрь, чтобы луч не стартовал ровно на грани
        origin = _pt_add(q_out, N, -eps)
        direction = _v(-N.x, -N.y, -N.z)
        hits = adsk.core.ObjectCollection.create()
        comp.findBRepUsingRay(origin, direction, adsk.fusion.BRepEntityTypes.BRepFaceEntityType,
                              -1.0, False, hits)
        best = None
        for i in range(hits.count):
            dist = origin.distanceTo(hits.item(i))
            if dist > 0.01 and (best is None or dist < best):  # игнорируем попадания ближе 0.1 мм
                best = dist
        if best is None:
            return None
        return (best + eps) / CM
    except Exception:
        return None


def _make_tool(comp, frame, poly_mm, width_mm):
    """
    Строит призму-заготовку: полигон (d, n) в эскизе на базовой плоскости XY,
    выдавливание симметрично на width_mm (новое тело), затем перенос в позицию защёлки.
    Так не нужны произвольные конструкторские плоскости (они недоступны в параметрическом режиме).
    Возвращает тело-заготовку.
    """
    anchor, D, N = frame
    T = _unit(D.crossProduct(N))
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.isLightBulbOn = False

    def to_sk(dd, nn):
        sp = sk.modelToSketchSpace(adsk.core.Point3D.create(dd * CM, nn * CM, 0))
        return adsk.core.Point3D.create(sp.x, sp.y, 0)

    pts = [to_sk(dd, nn) for dd, nn in poly_mm]
    lines = sk.sketchCurves.sketchLines
    first = lines.addByTwoPoints(pts[0], pts[1])
    prev = first
    for k in range(2, len(pts)):
        prev = lines.addByTwoPoints(prev.endSketchPoint, pts[k])
    lines.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)
    if sk.profiles.count < 1:
        raise UserError('Профиль защёлки не замкнулся (проверьте параметры).')

    exts = comp.features.extrudeFeatures
    ei = exts.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(width_mm * CM), True)
    tool_body = exts.add(ei).bodies.item(0)

    # локальные оси (x=D, y=N, z=T) -> мировые, начало координат -> точка защёлки
    m = adsk.core.Matrix3D.create()
    o = adsk.core.Point3D.create(0, 0, 0)
    m.setToAlignCoordinateSystems(
        o, _v(1, 0, 0), _v(0, 1, 0), _v(0, 0, 1),
        anchor, D, N, T)
    coll = adsk.core.ObjectCollection.create()
    coll.add(tool_body)
    moves = comp.features.moveFeatures
    mi = moves.createInput2(coll)
    mi.defineAsFreeMove(m)
    moves.add(mi)
    return tool_body


def _combine(comp, target, tool_body, operation):
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool_body)
    ci = comp.features.combineFeatures.createInput(target, tools)
    ci.operation = operation
    ci.isKeepToolBodies = False
    comp.features.combineFeatures.add(ci)


def _far_hit(comp, body, p, v):
    """Самая дальняя точка пересечения луча p+v с гранями тела (для полого корпуса это наружная стенка)."""
    hits = adsk.core.ObjectCollection.create()
    ents = comp.findBRepUsingRay(p, v, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, -1.0, False, hits)
    best, bd = None, -1.0
    if ents:
        for i in range(min(ents.count, hits.count)):
            f = adsk.fusion.BRepFace.cast(ents.item(i))
            if f and f.body.entityToken == body.entityToken:
                d = p.distanceTo(hits.item(i))
                if d > bd:
                    best, bd = hits.item(i), d
    return best


def _project_to_walls(comp, body, cut_ent, p, both):
    """Точка на кривой -> наружные стенки тела по нормали к плоскости эскиза (в обе стороны)."""
    ok, o, xa, ya, za = cut_ent.parentSketch.transform.getAsCoordinateSystem()
    cands = []
    for s in (1.0, -1.0):
        hit = _far_hit(comp, body, p, _v(za.x * s, za.y * s, za.z * s))
        if hit:
            cands.append(hit)
    if not cands:
        return []
    if both:
        return cands
    return [min(cands, key=lambda h: p.distanceTo(h))]


def build(design, body, cut_ent, pts, P, flip, auto_wall=False, proj=False, both=False, cuts=None):
    if design is None or design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise UserError('Включите историю (параметрический режим): Capture Design History.')
    if body.assemblyContext is not None:
        raise UserError('Выберите тело корневого компонента (или активируйте нужный компонент).')

    notes = []
    comp = body.parentComponent
    tl = design.timeline
    start = tl.count
    surf = None
    try:
        # 1. Кадры защёлок (до разреза, по исходному телу)
        tool, faces, surf = _resolve_cut_tool(design, comp, body, cut_ent, cuts)

        # Режим «точки на кривой»: от точки на кривой идём по оси выдавливания к стенкам тела
        if proj and hasattr(cut_ent, 'parentSketch'):
            new_pts = []
            for p in pts:
                if min(c[0] for c in _closest(body.faces, p)) < 0.05:   # точка уже на стенке
                    new_pts.append(p)
                    continue
                found = _project_to_walls(comp, body, cut_ent, p, both)
                if not found:
                    raise UserError('От точки на кривой не найдена стенка тела вдоль оси '
                                    'выдавливания. Проверьте положение точки.')
                new_pts += found
            if len(new_pts) != len(pts):
                notes.append('Точки на кривой: найдено мест для защёлок - %d.' % len(new_pts))
            pts = new_pts

        frames = []
        walls = []
        for p in pts:
            q_out, n_raw = _outer_normal(body, _v(0, 0, 0), p)  # предварительная нормаль
            q_cut, d = _cut_frame(cut_ent, faces, q_out)
            q_out, n_raw = _outer_normal(body, d, p)
            N = _v(n_raw.x, n_raw.y, n_raw.z)
            dn = N.dotProduct(d)
            N = _v(N.x - d.x * dn, N.y - d.y * dn, N.z - d.z * dn)
            if N.length < 0.3:
                raise UserError('В одной из точек стенка параллельна плоскости реза: '
                                'защёлку там построить нельзя.')
            N = _unit(N)
            D = d.copy()
            if flip:
                D.scaleBy(-1.0)
            frames.append((q_cut, D, N))
            if auto_wall:
                walls.append(_measure_wall(comp, q_out, N))

        if auto_wall:
            good = [w for w in walls if w]
            if len(good) == len(walls) and good:
                P.wall = min(good)
                if max(good) - min(good) > 0.3:
                    notes.append('Толщина стенки в точках разная (%.1f-%.1f мм), взята минимальная.'
                                 % (min(good), max(good)))
                notes.append('Толщина стенки по модели: %.2f мм.' % P.wall)
            else:
                notes.append('Не удалось измерить стенку по модели, использовано значение из поля '
                             '(%.1f мм). Проверьте его.' % P.wall)

        res = core.compute(P)
        arm_poly = core.arm_polygon(P, res)
        pocket_poly = core.pocket_polygon(P, res)

        # 2. Разрез
        sbs = comp.features.splitBodyFeatures
        sf = sbs.add(sbs.createInput(body, tool, True))
        halves = [sf.bodies.item(i) for i in range(sf.bodies.count)]
        if len(halves) < 2:
            raise UserError('Разрез не разделил тело на части. Проверьте, что плоскость/кривая '
                            'пересекает тело целиком.')
        if surf is not None:
            surf.isLightBulbOn = False

        def side_body(pt):
            for h in halves:
                h = _fresh(design, h)
                if h.pointContainment(pt) == adsk.fusion.PointContainment.PointInsidePointContainment:
                    return h
            return None

        # 3. Защёлки
        for idx, (anchor, D, N) in enumerate(frames):
            mid = _pt_add(anchor, N, -P.wall * 0.5 * CM)
            body_a = side_body(_pt_add(mid, D, 0.3 * CM))     # половина с балкой
            body_b = side_body(_pt_add(mid, D, -0.3 * CM))    # половина с окном
            if body_a is None or body_b is None or body_a.entityToken == body_b.entityToken:
                raise UserError('Точка %d: не удалось определить половины корпуса около защёлки. '
                                'Проверьте толщину стенки и положение точки.' % (idx + 1))
            frame = (anchor, D, N)

            # балка с крючком -> половина A
            arm = _make_tool(comp, frame, arm_poly, P.arm_w)
            _combine(comp, _fresh(design, body_a), arm,
                     adsk.fusion.FeatureOperations.JoinFeatureOperation)

            # канал и окно -> половина B
            pocket = _make_tool(comp, frame, pocket_poly, P.arm_w + 2 * P.clearance)
            _combine(comp, _fresh(design, body_b), pocket,
                     adsk.fusion.FeatureOperations.CutFeatureOperation)

            # направляющие штифты по бокам балки: штифт на половине A, гнездо на половине B
            if P.pins:
                T = _unit(D.crossProduct(N))
                off = core.pin_offset(P)
                for sgn in (1.0, -1.0):
                    fr = (_pt_add(anchor, T, sgn * off * CM), D, N)
                    pin = _make_tool(comp, fr, core.pin_polygon(P), core.PIN_W)
                    _combine(comp, _fresh(design, body_a), pin,
                             adsk.fusion.FeatureOperations.JoinFeatureOperation)
                    hole = _make_tool(comp, fr, core.pin_pocket_polygon(P),
                                      core.PIN_W + 2 * P.clearance)
                    _combine(comp, _fresh(design, body_b), hole,
                             adsk.fusion.FeatureOperations.CutFeatureOperation)

        msg = 'Готово: %d защёлк(и), длина балки %.1f мм.' % (len(frames), res.length)
        if notes:
            msg += '\n' + '\n'.join(notes)
        if res.warnings:
            msg += '\n\nПредупреждения:\n- ' + '\n- '.join(res.warnings)
        _ui.messageBox(msg)
    except Exception:
        for i in range(tl.count - 1, start - 1, -1):
            try:
                tl.item(i).entity.deleteMe()
            except Exception:
                pass
        raise


# ------------------------------------------------------------ add-in entry ---
def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        old = _ui.commandDefinitions.itemById(CMD_ID)
        if old:
            old.deleteMe()
        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, 'Snap-Fit Generator',
            'Разрезает тело на две половины и строит защёлки под FDM-печать')
        h = CreatedHandler()
        cmd_def.commandCreated.add(h)
        _handlers.append(h)
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        old_ctrl = panel.controls.itemById(CMD_ID)
        if old_ctrl:
            old_ctrl.deleteMe()
        panel.controls.addCommand(cmd_def)
    except Exception:
        if _ui:
            _ui.messageBox('Ошибка запуска аддина:\n' + traceback.format_exc())


def stop(context):
    try:
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        ctrl = panel.controls.itemById(CMD_ID)
        if ctrl:
            ctrl.deleteMe()
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
    except Exception:
        if _ui:
            _ui.messageBox('Ошибка остановки аддина:\n' + traceback.format_exc())
