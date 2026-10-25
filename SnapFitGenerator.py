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
MODE_CUT = 'Разрезать тело (плоскость / кривая)'
MODE_SPLIT_DONE = 'Тела уже разделены (выбрать два тела)'

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


def _type_info(inputs):
    return core.TYPES.get(_find(inputs, 'ctype').selectedItem.name, {})


def read_params(inputs):
    auto = _find(inputs, 'autoLen').value
    ti = _type_info(inputs)
    return core.Params(
        overlay=(ti.get('style') == 'overlay'),
        shape=ti.get('shape', 'straight'),
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
        is_u = t.get('shape') == 'u'
        _find(inputs, 'taper').isEnabled = not is_u      # у U-образной ветви сечение постоянное


def apply_mode(inputs):
    """Показать поля выбранного режима: разрезать тело или использовать готовые тела."""
    split_mode = _find(inputs, 'mode').selectedItem.name == MODE_SPLIT_DONE
    _find(inputs, 'cut').isVisible = not split_mode
    _find(inputs, 'projPts').isVisible = not split_mode
    _find(inputs, 'bothSides').isVisible = not split_mode
    _find(inputs, 'body2').isVisible = split_mode


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

            md = inputs.addDropDownCommandInput(
                'mode', 'Режим', adsk.core.DropDownStyles.TextListDropDownStyle)
            md.listItems.add(MODE_CUT, True)
            md.listItems.add(MODE_SPLIT_DONE, False)

            s = inputs.addSelectionInput('body', 'Тело', 'Тело, которое нужно разрезать '
                                         '(в режиме готовых тел - первое из двух тел)')
            s.addSelectionFilter(sc.SolidBodies)
            s.setSelectionLimits(1, 1)

            s = inputs.addSelectionInput('body2', 'Второе тело', 'Вторая половина корпуса')
            s.addSelectionFilter(sc.SolidBodies)
            s.setSelectionLimits(0, 1)       # обязательность проверяет ValidateHandler
            s.isVisible = False

            s = inputs.addSelectionInput(
                'cut', 'Плоскость / кривая реза',
                'Конструкторская плоскость, грань, поверхность или эскизная кривая')
            s.addSelectionFilter(sc.ConstructionPlanes)
            s.addSelectionFilter(sc.Faces)
            s.addSelectionFilter(sc.SketchCurves)
            s.setSelectionLimits(0, 0)   # можно выбрать несколько линий эскиза; обязательность - в ValidateHandler

            s = inputs.addSelectionInput(
                'pts', 'Точки защёлок',
                'Точки на поверхности стенки у линии реза. Балка вырастет на той половине, '
                'на которой лежит точка (кнопка «Реверс» меняет половины)')
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
            g.addBoolValueInput('flip', 'Реверс: балка на другой половине', True, '', False)

            inputs.addTextBoxCommandInput('info', 'Расчёт', '', 12, True)
            apply_type(inputs, core.DEFAULT_TYPE)
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
            elif args.input.id == 'mode':
                apply_mode(inputs)
            update_info(inputs)
        except Exception:
            pass


class ValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            i = args.inputs
            split_mode = _find(i, 'mode').selectedItem.name == MODE_SPLIT_DONE
            ok = (_find(i, 'body').selectionCount == 1 and
                  _find(i, 'pts').selectionCount >= 1)
            if split_mode:
                ok = ok and _find(i, 'body2').selectionCount == 1
            else:
                ok = ok and _find(i, 'cut').selectionCount >= 1
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
            pts_in = _find(inputs, 'pts')
            pts = [_point_of(pts_in.selection(k).entity) for k in range(pts_in.selectionCount)]
            params = read_params(inputs)
            flip = _find(inputs, 'flip').value
            auto_wall = _find(inputs, 'autoWall').value
            if _find(inputs, 'mode').selectedItem.name == MODE_SPLIT_DONE:
                body2 = adsk.fusion.BRepBody.cast(_find(inputs, 'body2').selection(0).entity)
                build_split(design, body, body2, pts, params, flip, auto_wall)
                return
            cut_in = _find(inputs, 'cut')
            cuts = [cut_in.selection(k).entity for k in range(cut_in.selectionCount)]
            cut = cuts[0]
            if len(cuts) > 1 and not all(hasattr(c, 'parentSketch') for c in cuts):
                raise UserError('Несколько объектов реза можно выбирать только для линий эскиза. '
                                'Плоскость или грань выбирайте по одной.')
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


def _combine(comp, target, tool_bodies, operation):
    """Объединение/вычитание сразу нескольких тел-инструментов одной операцией таймлайна."""
    tools = adsk.core.ObjectCollection.create()
    for t in tool_bodies:
        tools.add(t)
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


SIDE_EPS = 0.005    # 0.05 мм: ближе этого точка считается лежащей прямо на линии реза
GROUP_NAME = 'Snap-Fit'


def _inside(body, pt, include_boundary=False):
    pc = body.pointContainment(pt)
    if pc == adsk.fusion.PointContainment.PointInsidePointContainment:
        return True
    return include_boundary and pc == adsk.fusion.PointContainment.PointOnPointContainment


def _near_faces(body, p, tol=0.002):
    """Ближайшие к точке грани тела: (мин. расстояние, [(грань, точка на ней, наружная нормаль)])."""
    cands = _closest(body.faces, p)
    mind = min(c[0] for c in cands)
    out = []
    for dist, f, q in cands:
        if dist <= mind + tol:
            n = _unit(_face_normal_at(f, q))
            if _inside(body, _pt_add(q, n, 0.01)):
                n.scaleBy(-1.0)
            out.append((f, q, n))
    return mind, out


def _perp_unit(N, D, err):
    """Составляющая N, перпендикулярная D, единичная."""
    dn = N.dotProduct(D)
    w = _v(N.x - D.x * dn, N.y - D.y * dn, N.z - D.z * dn)
    if w.length < 0.3:
        raise UserError(err)
    return _unit(w)


def _frame_cut(body, p, cut_ent, faces, flip):
    """
    Кадр защёлки для режима разреза: (anchor, D, N, q_out, на_линии_реза).
    D направлен в сторону половины, на которой лежит точка (там вырастет балка).
    """
    q_out, _ = _outer_normal(body, _v(0, 0, 0), p)           # предварительно: ближайшая точка поверхности
    q_cut, d = _cut_frame(cut_ent, faces, q_out)
    q_out, n_raw = _outer_normal(body, d, p)
    N = _perp_unit(_v(n_raw.x, n_raw.y, n_raw.z), d,
                   'В одной из точек стенка параллельна плоскости реза: защёлку там построить нельзя.')
    sd = _v(q_out.x - q_cut.x, q_out.y - q_cut.y, q_out.z - q_cut.z).dotProduct(d)
    D = d.copy()
    if sd < -SIDE_EPS:
        D.scaleBy(-1.0)
    if flip:
        D.scaleBy(-1.0)
    return q_cut, D, N, q_out, abs(sd) <= SIDE_EPS


def _frame_split(body_1, body_2, p):
    """
    Кадр защёлки для двух готовых тел: (тело_с_балкой, тело_с_окном, anchor, D, N, q_out).
    Балка - на теле, на поверхности которого лежит точка; D направлен от стыка в сторону этого тела.
    """
    m1, f1 = _near_faces(body_1, p)
    m2, f2 = _near_faces(body_2, p)
    if min(m1, m2) > 0.3:
        raise UserError('Точка лежит дальше 3 мм от обоих тел. Поставьте её на поверхность одного из тел.')
    if m2 + 0.002 < m1:
        beam, other, faces = body_2, body_1, f2
    else:
        beam, other, faces = body_1, body_2, f1

    # грань стыка: её наружная нормаль ведёт внутрь второго тела
    contact = None
    for f, q, n in faces:
        w = None
        rest = [t for t in faces if t[0] != f]
        if rest:
            w = min(rest, key=lambda t: abs(t[2].dotProduct(n)))[2]
        test = _pt_add(q, n, 0.02)
        if w is not None:
            test = _pt_add(test, w, -0.02)       # чуть вглубь стенки, чтобы не попасть на её наружную грань
        if _inside(other, test, include_boundary=True):
            contact = (q, n)
            break
    if contact is None:                          # тела разнесены: идём к ближайшей точке второго тела
        r = _app.measureManager.measureMinimumDistance(p, other)
        v = _v(r.positionTwo.x - p.x, r.positionTwo.y - p.y, r.positionTwo.z - p.z)
        if v.length > 1e-6:
            v = _unit(v)
            f, q, n = max(faces, key=lambda t: t[2].dotProduct(v))
            if n.dotProduct(v) > 0.3:
                contact = (q, n)
    if contact is None:
        raise UserError('Не удалось найти стык двух тел у точки. Тела должны касаться друг друга '
                        'или находиться рядом, а точка лежать на краю стыка.')
    q_c, n_c = contact
    D = _v(-n_c.x, -n_c.y, -n_c.z)
    f, q_out, n_w = min(faces, key=lambda t: abs(t[2].dotProduct(D)))
    N = _perp_unit(n_w, D, 'В одной из точек стенка параллельна стыку тел: защёлку там построить нельзя.')
    return beam, other, q_c, D, N, q_out


def _apply_auto_wall(P, walls, notes):
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


def _place_snaps(design, comp, frames, P, res):
    """
    frames: [(anchor, D, N, body_a, body_b)]; body_a - тело с балкой, body_b - тело с окном.
    На каждую защёлку: одно объединение (балка + штифты) и одно вычитание (окно + гнёзда).
    """
    arm_poly = core.arm_polygon(P, res)
    pocket_poly = core.pocket_polygon(P, res)
    use_pins = P.pins and res.pins_ok
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    for anchor, D, N, body_a, body_b in frames:
        frame = (anchor, D, N)
        arms = [_make_tool(comp, frame, arm_poly, P.arm_w)]
        pockets = [_make_tool(comp, frame, pocket_poly, P.arm_w + 2 * P.clearance)]
        if use_pins:
            T = _unit(D.crossProduct(N))
            off = core.pin_offset(P)
            for sgn in (1.0, -1.0):
                fr = (_pt_add(anchor, T, sgn * off * CM), D, N)
                arms.append(_make_tool(comp, fr, core.pin_polygon(P), core.PIN_W))
                pockets.append(_make_tool(comp, fr, core.pin_pocket_polygon(P),
                                          core.PIN_W + 2 * P.clearance))
        _combine(comp, _fresh(design, body_a), [_fresh(design, t) for t in arms], JOIN)
        _combine(comp, _fresh(design, body_b), [_fresh(design, t) for t in pockets], CUT)


def _group_timeline(design, start):
    """Сворачивает все операции аддина в одну группу таймлайна. Ошибки группировки не критичны."""
    try:
        tl = design.timeline
        end = tl.markerPosition - 1
        if end > start:
            g = tl.timelineGroups.add(start, end)
            g.name = GROUP_NAME
            g.isCollapsed = True
            return True
    except Exception:
        pass
    return False


def _rollback(design, start):
    tl = design.timeline
    for i in range(tl.markerPosition - 1, start - 1, -1):
        try:
            tl.item(i).entity.deleteMe()
        except Exception:
            pass


def _report(count, res, notes):
    msg = 'Готово: %d защёлк(и), длина балки %.1f мм.' % (count, res.length)
    if notes:
        msg += '\n' + '\n'.join(notes)
    if res.warnings:
        msg += '\n\nПредупреждения:\n- ' + '\n- '.join(res.warnings)
    _ui.messageBox(msg)


def _check_design(design, *bodies):
    if design is None or design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise UserError('Включите историю (параметрический режим): Capture Design History.')
    for b in bodies:
        if b.assemblyContext is not None:
            raise UserError('Выберите тело корневого компонента (или активируйте нужный компонент).')


def build(design, body, cut_ent, pts, P, flip, auto_wall=False, proj=False, both=False, cuts=None):
    """Режим «разрезать тело»: разрез по плоскости/кривой и защёлки в точках."""
    _check_design(design, body)
    notes = []
    comp = body.parentComponent
    start = design.timeline.markerPosition
    try:
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

        # 1. Кадры защёлок (до разреза, по исходному телу)
        frames0, walls, on_cut = [], [], 0
        for p in pts:
            anchor, D, N, q_out, onp = _frame_cut(body, p, cut_ent, faces, flip)
            on_cut += 1 if onp else 0
            frames0.append((anchor, D, N))
            if auto_wall:
                walls.append(_measure_wall(comp, q_out, N))
        if auto_wall:
            _apply_auto_wall(P, walls, notes)
        if on_cut:
            notes.append('Точек на самой линии реза: %d. Для них сторона балки не определяется по '
                         'положению точки; если балка выросла не там, включите «Реверс».' % on_cut)
        res = core.compute(P)

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
                if _inside(h, pt):
                    return h
            return None

        # 3. Защёлки: тело с балкой - с той стороны, куда смотрит D
        frames = []
        for idx, (anchor, D, N) in enumerate(frames0):
            mid = _pt_add(anchor, N, -P.wall * 0.5 * CM)
            body_a = side_body(_pt_add(mid, D, 0.3 * CM))
            body_b = side_body(_pt_add(mid, D, -0.3 * CM))
            if body_a is None or body_b is None or body_a.entityToken == body_b.entityToken:
                raise UserError('Точка %d: не удалось определить половины корпуса около защёлки. '
                                'Проверьте толщину стенки и положение точки.' % (idx + 1))
            frames.append((anchor, D, N, body_a, body_b))
        _place_snaps(design, comp, frames, P, res)

        if _group_timeline(design, start):
            notes.append('Все операции собраны в группу «%s» на таймлайне.' % GROUP_NAME)
        _report(len(frames), res, notes)
    except Exception:
        _rollback(design, start)
        raise


def build_split(design, body_1, body_2, pts, P, flip, auto_wall=False):
    """Режим «тела уже разделены»: два тела, точки на одном из них, разрез не делается."""
    _check_design(design, body_1, body_2)
    if body_1.entityToken == body_2.entityToken:
        raise UserError('Выберите два разных тела.')
    comp = body_1.parentComponent
    if body_2.parentComponent.entityToken != comp.entityToken:
        raise UserError('Оба тела должны лежать в одном компоненте.')
    notes = []
    start = design.timeline.markerPosition
    try:
        frames, walls = [], []
        for p in pts:
            beam, other, anchor, D, N, q_out = _frame_split(body_1, body_2, p)
            if flip:
                D.scaleBy(-1.0)
                beam, other = other, beam
            frames.append((anchor, D, N, beam, other))
            if auto_wall:
                walls.append(_measure_wall(comp, q_out, N))
        if auto_wall:
            _apply_auto_wall(P, walls, notes)
        res = core.compute(P)
        _place_snaps(design, comp, frames, P, res)

        if _group_timeline(design, start):
            notes.append('Все операции собраны в группу «%s» на таймлайне.' % GROUP_NAME)
        _report(len(frames), res, notes)
    except Exception:
        _rollback(design, start)
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
