# -*- coding: utf-8 -*-
"""
Snap-Fit Generator для Fusion 360.

Выбираешь тело, плоскость/кривую реза и точки защёлок, материал печати.
Аддин делит тело на две половины и в каждой точке строит консольную защёлку
(балка с крючком на одной половине + канал и окно на другой).
"""
import importlib.util
import json
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
    kind = ti.get('kind', 'beam')
    ring_r = 30.0
    if kind == 'annular':                       # для предпросмотра берём радиус первого выбранного ребра
        try:
            ri = _find(inputs, 'ring')
            if ri.selectionCount > 0:
                ring_r = _ring_of(ri.selection(0).entity)[2] / CM
        except Exception:
            pass
    return core.Params(
        overlay=(ti.get('style') == 'overlay'),
        shape=ti.get('shape', 'straight'),
        kind=kind,
        slots=_find(inputs, 'slots').value,
        slot_w=_mm(inputs, 'slot_w'),
        ring_r=ring_r,
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
        through=False if kind == 'annular' else _find(inputs, 'through').value,
        taper_pct=_find(inputs, 'taper').value,
        fillet=_find(inputs, 'fillet').value,
        pins=False if kind == 'annular' else _find(inputs, 'pins').value,
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


LABELS = {
    'beam': ('Толщина балки', 'Ширина балки', 'Длина балки'),
    'torsion': ('Толщина рычага = сторона торсиона', 'Ширина рычага', 'Длина рычага'),
    'annular': ('Толщина воротника', 'Ширина пальца (считается)', 'Длина воротника'),
}


def _set_label(inputs, cid, text):
    """Подпись поля меняем, если API позволяет; ошибка не должна ломать диалог."""
    try:
        _find(inputs, cid).name = text
    except Exception:
        pass


def apply_type(inputs, name):
    t = core.TYPES.get(name)
    if not t:
        return
    _find(inputs, 'ret').value = math.radians(t['ret'])
    kind = t.get('kind', 'beam')
    is_u = t.get('shape') == 'u'
    _find(inputs, 'taper').isEnabled = (not is_u) and kind != 'torsion'   # у U-ветви и рычага сечение постоянное
    _find(inputs, 'fillet').isEnabled = kind != 'torsion'
    _find(inputs, 'pins').isEnabled = kind != 'annular'
    th = _find(inputs, 'through')
    if kind == 'annular':                      # канавка кольца не может быть сквозной: она разрезала бы деталь
        th.value = False
        th.isEnabled = False
    else:
        if not th.isEnabled:
            th.value = True
        th.isEnabled = True
    _find(inputs, 'arm_w').isEnabled = kind != 'annular'
    lt, lw, ll = LABELS[kind]
    _set_label(inputs, 'arm_t', lt)
    _set_label(inputs, 'arm_w', lw)
    _set_label(inputs, 'length', ll)
    _set_label(inputs, 'autoLen', 'Длина по расчёту')
    _find(inputs, 'slots').isVisible = kind == 'annular'
    _find(inputs, 'slot_w').isVisible = kind == 'annular'


def apply_mode(inputs):
    """Показать поля выбранного режима и типа: разрез или готовые тела, точки или кольцевые рёбра."""
    split_mode = _find(inputs, 'mode').selectedItem.name == MODE_SPLIT_DONE
    ann = _type_info(inputs).get('kind', 'beam') == 'annular'
    _find(inputs, 'cut').isVisible = not split_mode
    _find(inputs, 'body2').isVisible = split_mode
    _find(inputs, 'projPts').isVisible = (not split_mode) and not ann
    _find(inputs, 'bothSides').isVisible = (not split_mode) and not ann
    _find(inputs, 'pts').isVisible = not ann
    _find(inputs, 'ring').isVisible = ann


def update_info(inputs):
    try:
        p = read_params(inputs)
        auto_wall = _find(inputs, 'autoWall').value
        _find(inputs, 'wall').isEnabled = not auto_wall
        if auto_wall:
            # реальная стенка станет известна при построении: ложных предупреждений не даём
            p.wall = p.arm_t + 10.0
            if p.kind == 'annular':
                p.wall = max(p.arm_t + 1.0, min(p.arm_t + 10.0, p.ring_r * 0.15))
        _find(inputs, 'length').isEnabled = not _find(inputs, 'autoLen').value
        if _find(inputs, 'autoLen').value:
            _set_mm(inputs, 'length', core.compute(p).length)
        r = core.compute(p)
        tname = _find(inputs, 'ctype').selectedItem.name
        desc = core.TYPES.get(tname, {}).get('text', '')
        _find(inputs, 'info').formattedText = '<i>%s</i><br><br>%s' % (desc, core.format_report(p, r))
    except Exception:
        pass


# ------------------------------------------------------- память настроек ---
SETTINGS_VERSION = 1
DROP_IDS = ('mode', 'material', 'ctype')
BOOL_IDS = ('projPts', 'bothSides', 'autoWall', 'autoLen', 'fillet', 'pins', 'through', 'flip')
MM_IDS = ('wall', 'arm_t', 'arm_w', 'engage', 'clearance', 'length', 'slot_w')
DEG_IDS = ('lead', 'ret')
NUM_IDS = ('strain', 'E', 'taper', 'slots')
SECTIONS = ('drop', 'bool', 'mm', 'deg', 'num')


def _settings_path():
    return os.path.join(os.path.expanduser('~'), '.snapfit_generator', 'settings.json')


def factory_state():
    """Заводские значения диалога (в мм, градусах и обычных числах)."""
    m = core.MATERIALS[core.DEFAULT_MATERIAL]
    return {
        'drop': {'mode': MODE_CUT, 'material': core.DEFAULT_MATERIAL, 'ctype': core.DEFAULT_TYPE},
        'bool': {'projPts': True, 'bothSides': False, 'autoWall': True, 'autoLen': True,
                 'fillet': True, 'pins': True, 'through': True, 'flip': False},
        'mm': {'wall': 2.4, 'arm_t': m['arm_t'], 'arm_w': 5.0, 'engage': m['engage'],
               'clearance': m['clearance'], 'length': 10.0, 'slot_w': 1.5},
        'deg': {'lead': m['lead'], 'ret': core.TYPES[core.DEFAULT_TYPE]['ret']},
        'num': {'strain': m['strain'], 'E': m['E'], 'taper': 50.0, 'slots': 8},
    }


def merge_state(base, extra):
    """Заводское состояние, поверх которого лежат сохранённые значения (только известные ключи)."""
    out = {sec: dict(base.get(sec, {})) for sec in SECTIONS}
    if isinstance(extra, dict):
        for sec in SECTIONS:
            part = extra.get(sec)
            if isinstance(part, dict):
                for k, v in part.items():
                    if k in out[sec]:
                        out[sec][k] = v
    return out


def collect_state(inputs):
    st = {sec: {} for sec in SECTIONS}
    for cid in DROP_IDS:
        st['drop'][cid] = _find(inputs, cid).selectedItem.name
    for cid in BOOL_IDS:
        inp = _find(inputs, cid)
        if cid == 'through' and not inp.isEnabled:      # у кольцевых типов принудительно выключено - не запоминаем
            continue
        st['bool'][cid] = bool(inp.value)
    for cid in MM_IDS:
        st['mm'][cid] = round(_mm(inputs, cid), 4)
    for cid in DEG_IDS:
        st['deg'][cid] = round(math.degrees(_find(inputs, cid).value), 3)
    for cid in NUM_IDS:
        st['num'][cid] = _find(inputs, cid).value
    return st


def _select_item(dd, name):
    for i in range(dd.listItems.count):
        it = dd.listItems.item(i)
        if it.name == name:
            it.isSelected = True
            return True
    return False


def apply_state(inputs, st):
    """Выставляет диалог по состоянию st. Материал выбирается без пересчёта пресета: значения берутся из st."""
    for cid in DROP_IDS:
        try:
            _select_item(_find(inputs, cid), st['drop'][cid])
        except Exception:
            pass
    apply_type(inputs, _find(inputs, 'ctype').selectedItem.name)
    for cid in BOOL_IDS:
        try:
            inp = _find(inputs, cid)
            if cid != 'through' or inp.isEnabled:
                inp.value = bool(st['bool'][cid])
        except Exception:
            pass
    for cid in MM_IDS:
        try:
            _set_mm(inputs, cid, float(st['mm'][cid]))
        except Exception:
            pass
    for cid in DEG_IDS:
        try:
            _find(inputs, cid).value = math.radians(float(st['deg'][cid]))
        except Exception:
            pass
    for cid in NUM_IDS:
        try:
            v = st['num'][cid]
            _find(inputs, cid).value = int(v) if cid == 'slots' else float(v)
        except Exception:
            pass
    apply_mode(inputs)


def load_settings():
    try:
        with open(_settings_path(), encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get('version') == SETTINGS_VERSION:
            return data
    except Exception:
        pass
    return {}


def save_settings(inputs):
    """Запоминает текущие режим, материал, тип, галки и параметры. Ошибки записи не мешают работе."""
    try:
        st = collect_state(inputs)
        prev = load_settings()
        merged = {'version': SETTINGS_VERSION}
        for sec in SECTIONS:
            d = dict(prev.get(sec, {})) if isinstance(prev.get(sec), dict) else {}
            d.update(st[sec])
            merged[sec] = d
        path = _settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_settings():
    try:
        os.remove(_settings_path())
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
            s.setSelectionLimits(0, 0)   # обязательность проверяет ValidateHandler: у кольцевых типов точки не нужны

            s = inputs.addSelectionInput(
                'ring', 'Кольцевое ребро на шве',
                'Круговое ребро на наружной цилиндрической поверхности корпуса. Ось и радиус кольца берутся '
                'из ребра; воротник вырастет на первом теле (в режиме разреза - на половине, где лежит ребро), '
                'кнопка «Реверс» меняет половины')
            s.addSelectionFilter(sc.CircularEdges)
            s.setSelectionLimits(0, 0)
            s.isVisible = False

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
            g.addIntegerSpinnerCommandInput('slots', 'Прорезей в воротнике (0 = цельное кольцо)', 0, 36, 1, 8)
            g.addValueInput('slot_w', 'Ширина прорези', 'mm', vi.createByReal(1.5 * CM))
            g.addBoolValueInput('autoLen', 'Длина балки по расчёту', True, '', True)
            g.addValueInput('length', 'Длина балки', 'mm', vi.createByReal(10.0 * CM))
            g.addBoolValueInput('through', 'Сквозное окно в стенке', True, '', True)
            g.addBoolValueInput('flip', 'Реверс: балка на другой половине', True, '', False)

            inputs.addBoolValueInput('resetDefaults', 'Сбросить настройки к заводским (отметь галку)',
                                     True, '', False)
            inputs.addTextBoxCommandInput('info', 'Расчёт', '', 12, True)
            apply_state(inputs, merge_state(factory_state(), load_settings()))
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
            if args.input.id == 'resetDefaults':
                if _find(inputs, 'resetDefaults').value:
                    apply_state(inputs, factory_state())
                    clear_settings()
                    _find(inputs, 'resetDefaults').value = False
            elif args.input.id == 'material':
                apply_preset(inputs, _find(inputs, 'material').selectedItem.name)
            elif args.input.id == 'ctype':
                apply_type(inputs, _find(inputs, 'ctype').selectedItem.name)
                apply_mode(inputs)
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
            ann = _type_info(i).get('kind', 'beam') == 'annular'
            ok = (_find(i, 'body').selectionCount == 1 and
                  (_find(i, 'ring').selectionCount if ann else _find(i, 'pts').selectionCount) >= 1)
            if split_mode:
                ok = ok and _find(i, 'body2').selectionCount == 1
            else:
                ok = ok and _find(i, 'cut').selectionCount >= 1
            for cid in ('wall', 'arm_t', 'arm_w', 'engage', 'clearance', 'length') + (('slot_w',) if ann else ()):
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
            save_settings(inputs)
            body = adsk.fusion.BRepBody.cast(_find(inputs, 'body').selection(0).entity)
            params = read_params(inputs)
            flip = _find(inputs, 'flip').value
            auto_wall = _find(inputs, 'autoWall').value
            split_mode = _find(inputs, 'mode').selectedItem.name == MODE_SPLIT_DONE
            body2 = adsk.fusion.BRepBody.cast(_find(inputs, 'body2').selection(0).entity) if split_mode else None

            if params.kind == 'annular':
                ring_in = _find(inputs, 'ring')
                rings = [ring_in.selection(k).entity for k in range(ring_in.selectionCount)]
                cut = None
                if not split_mode:
                    cut_in = _find(inputs, 'cut')
                    if cut_in.selectionCount != 1:
                        raise UserError('Для кольцевой защёлки выберите одну плоскость или плоскую грань реза.')
                    cut = cut_in.selection(0).entity
                build_annular(design, body, body2, cut, rings, params, flip, auto_wall)
                return

            pts_in = _find(inputs, 'pts')
            pts = [_point_of(pts_in.selection(k).entity) for k in range(pts_in.selectionCount)]
            if split_mode:
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


def _draw_polygon(sk, pts):
    """Замкнутый полигон из линий эскиза по списку точек Point3D."""
    lines = sk.sketchCurves.sketchLines
    first = lines.addByTwoPoints(pts[0], pts[1])
    prev = first
    for k in range(2, len(pts)):
        prev = lines.addByTwoPoints(prev.endSketchPoint, pts[k])
    lines.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)


def _move_body(comp, body, anchor, D, N):
    """Переносит тело, построенное в локальных осях (x=D, y=N, z=D x N) у начала координат, к точке anchor."""
    T = _unit(D.crossProduct(N))
    m = adsk.core.Matrix3D.create()
    o = adsk.core.Point3D.create(0, 0, 0)
    m.setToAlignCoordinateSystems(
        o, _v(1, 0, 0), _v(0, 1, 0), _v(0, 0, 1),
        anchor, D, N, T)
    coll = adsk.core.ObjectCollection.create()
    coll.add(body)
    moves = comp.features.moveFeatures
    mi = moves.createInput2(coll)
    mi.defineAsFreeMove(m)
    moves.add(mi)


def _make_tool(comp, frame, poly_mm, width_mm, off_t=0.0):
    """
    Строит призму-заготовку: полигон (d, n) в эскизе на базовой плоскости XY,
    выдавливание симметрично на width_mm (новое тело), затем перенос в позицию защёлки
    (со смещением off_t мм вдоль стенки). Так не нужны произвольные конструкторские плоскости
    (они недоступны в параметрическом режиме). Возвращает тело-заготовку.
    """
    anchor, D, N = frame
    if off_t:
        anchor = _pt_add(anchor, _unit(D.crossProduct(N)), off_t * CM)
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.isLightBulbOn = False

    def to_sk(dd, nn):
        sp = sk.modelToSketchSpace(adsk.core.Point3D.create(dd * CM, nn * CM, 0))
        return adsk.core.Point3D.create(sp.x, sp.y, 0)

    _draw_polygon(sk, [to_sk(dd, nn) for dd, nn in poly_mm])
    if sk.profiles.count < 1:
        raise UserError('Профиль защёлки не замкнулся (проверьте параметры).')

    exts = comp.features.extrudeFeatures
    ei = exts.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setSymmetricExtent(adsk.core.ValueInput.createByReal(width_mm * CM), True)
    tool_body = exts.add(ei).bodies.item(0)
    _move_body(comp, tool_body, anchor, D, N)
    return tool_body


def _make_ring(comp, anchor, D, U, R_mm, poly_mm):
    """
    Тело вращения: полигон (d, n) превращается в профиль (d, R + n) и вращается на 360 градусов вокруг
    оси кольца (локальная ось x = D), затем переносится в центр кольца anchor.
    """
    sk = comp.sketches.add(comp.xYConstructionPlane)
    sk.isLightBulbOn = False

    def to_sk(dd, rr):
        sp = sk.modelToSketchSpace(adsk.core.Point3D.create(dd * CM, rr * CM, 0))
        return adsk.core.Point3D.create(sp.x, sp.y, 0)

    if min(n for _, n in poly_mm) + R_mm < 0.5:
        raise UserError('Радиус кольца %.1f мм слишком мал для такой стенки и воротника.' % R_mm)
    _draw_polygon(sk, [to_sk(dd, R_mm + nn) for dd, nn in poly_mm])
    if sk.profiles.count < 1:
        raise UserError('Профиль кольцевой защёлки не замкнулся (проверьте параметры).')
    prof = sk.profiles.item(0)
    d_lo = min(d for d, _ in poly_mm) - 2.0
    d_hi = max(d for d, _ in poly_mm) + 2.0
    axis = sk.sketchCurves.sketchLines.addByTwoPoints(to_sk(d_lo, 0.0), to_sk(d_hi, 0.0))
    axis.isConstruction = True

    revs = comp.features.revolveFeatures
    ri = revs.createInput(prof, axis, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ri.setAngleExtent(False, adsk.core.ValueInput.createByReal(2.0 * math.pi))
    body = revs.add(ri).bodies.item(0)
    _move_body(comp, body, anchor, D, U)
    return body


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
    frames: [(anchor, D, N, body_a, body_b)]; body_a - тело с защёлкой, body_b - тело с окном.
    На каждую защёлку: одно объединение (балка/рычаг/торсион + штифты) и одно вычитание (окно + гнёзда).
    """
    use_pins = P.pins and res.pins_ok
    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    for anchor, D, N, body_a, body_b in frames:
        frame = (anchor, D, N)
        arms = [_make_tool(comp, frame, poly, w, off) for poly, w, off in core.arm_parts(P, res)]
        pockets = [_make_tool(comp, frame, poly, w, off) for poly, w, off in core.pocket_parts(P, res)]
        if use_pins:
            T = _unit(D.crossProduct(N))
            off = core.pin_offset(P, res)
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


KIND_TEXT = {
    'beam': ('защёлк(и)', 'длина балки'),
    'torsion': ('торсионных защёлк(и)', 'длина рычага'),
    'annular': ('кольцевых защёлк(и)', 'длина воротника'),
}


def _report(count, res, notes, kind='beam'):
    what, ln = KIND_TEXT.get(kind, KIND_TEXT['beam'])
    msg = 'Готово: %d %s, %s %.1f мм.' % (count, what, ln, res.length)
    extra = list(res.notes) + list(notes)
    if extra:
        msg += '\n' + '\n'.join(extra)
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
        _report(len(frames), res, notes, P.kind)
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
        _report(len(frames), res, notes, P.kind)
    except Exception:
        _rollback(design, start)
        raise


# ------------------------------------------------------------ кольцевой тип ---
def _plane_of(ent):
    """(origin, единичная нормаль) для конструкторской плоскости или плоской грани, иначе None."""
    cp = adsk.fusion.ConstructionPlane.cast(ent)
    g = cp.geometry if cp else None
    if g is None:
        f = adsk.fusion.BRepFace.cast(ent)
        g = adsk.core.Plane.cast(f.geometry) if f else None
    if g is None:
        return None
    return g.origin, _unit(g.normal)


def _ring_of(edge):
    """Круговое ребро -> (центр, единичная ось, радиус в см)."""
    e = adsk.fusion.BRepEdge.cast(edge)
    c = adsk.core.Circle3D.cast(e.geometry) if e else None
    if c is None:
        raise UserError('Выберите круговое ребро (полная окружность) на шве корпуса.')
    return c.center, _unit(c.normal), c.radius


def _perp(a):
    """Единичный вектор, перпендикулярный a."""
    ref = _v(1, 0, 0) if abs(a.x) < 0.9 else _v(0, 1, 0)
    return _unit(a.crossProduct(ref))


def _rot(u, a, ang):
    """Вектор u, повёрнутый вокруг оси a (перпендикулярной u) на ang радиан."""
    w = a.crossProduct(u)
    c, s_ = math.cos(ang), math.sin(ang)
    return _v(u.x * c + w.x * s_, u.y * c + w.y * s_, u.z * c + w.z * s_)


def _ring_seat_cut(C0, a, plane, flip):
    """Режим разреза: центр кольца на плоскости реза и направление D в сторону половины, где лежит ребро."""
    o, n = plane
    den = a.dotProduct(n)
    if abs(den) < 0.5:
        raise UserError('Ось кольца не перпендикулярна плоскости реза: кольцо и плоскость должны быть соосны.')
    t = _v(o.x - C0.x, o.y - C0.y, o.z - C0.z).dotProduct(n) / den
    C = _pt_add(C0, a, t)
    D = a.copy()
    if -t < -0.005:                 # ребро лежит на стороне -a от плоскости реза
        D.scaleBy(-1.0)
    if flip:
        D.scaleBy(-1.0)
    return C, D


def _ring_side_split(body_1, body_2, C, a, u, R, flip):
    """Режим готовых тел: (D, тело с воротником, тело с канавкой). Воротник по умолчанию на первом теле."""
    p0 = _pt_add(C, u, max(R - 0.05, R * 0.5))
    if _inside(body_1, _pt_add(p0, a, 0.03)):
        D = a.copy()
    elif _inside(body_1, _pt_add(p0, a, -0.03)):
        D = a.copy()
        D.scaleBy(-1.0)
    else:
        raise UserError('Кольцевое ребро не лежит на шве первого тела: рядом с ним нет материала тела.')
    owner, other = body_1, body_2
    if flip:
        D.scaleBy(-1.0)
        owner, other = body_2, body_1
    if not _inside(other, _pt_add(p0, D, -0.03), include_boundary=True):
        raise UserError('Второе тело не найдено по другую сторону шва у кольцевого ребра. Тела должны '
                        'касаться друг друга по шву.')
    if not _inside(owner, _pt_add(p0, D, 0.03), include_boundary=True):
        raise UserError('Первое тело не найдено на нужной стороне шва у кольцевого ребра.')
    return D, owner, other


def build_annular(design, body, body2, cut_ent, rings, P, flip, auto_wall=False):
    """
    Кольцевой тип. body2 is None: разрез плоскостью cut_ent и кольца на шве; иначе два готовых тела.
    Воротник (тело вращения, с прорезями-пальцами) объединяется с телом-владельцем, канавка вычитается
    из второго тела. Радиус и ось берутся из выбранных круговых рёбер.
    """
    split_mode = body2 is not None
    _check_design(design, body, *([body2] if split_mode else []))
    comp = body.parentComponent
    plane = None
    if split_mode:
        if body.entityToken == body2.entityToken:
            raise UserError('Выберите два разных тела.')
        if body2.parentComponent.entityToken != comp.entityToken:
            raise UserError('Оба тела должны лежать в одном компоненте.')
    else:
        plane = _plane_of(cut_ent)
        if plane is None:
            raise UserError('Кольцевую защёлку можно построить при разрезе плоскостью или плоской гранью. '
                            'Для кривой реза выберите режим консольной или торсионной защёлки.')
    notes = []
    start = design.timeline.markerPosition
    try:
        seats, walls = [], []
        for e in rings:
            C0, a, R = _ring_of(e)
            u = _perp(a)
            if split_mode:
                C = C0
                D, owner, other = _ring_side_split(body, body2, C, a, u, R, flip)
            else:
                C, D = _ring_seat_cut(C0, a, plane, flip)
                owner = other = None
            q_meas = _pt_add(_pt_add(C, u, R), D, 0.03)
            chk = [body] + ([body2] if split_mode else [])
            if min(min(c[0] for c in _closest(b.faces, q_meas)) for b in chk) > 0.03:
                raise UserError('Кольцо не лежит на наружной цилиндрической поверхности корпуса у шва '
                                '(радиус или положение ребра не совпадают с телом).')
            seats.append((C, D, u, R, owner, other))
            if auto_wall:
                walls.append(_measure_wall(comp, q_meas, u))
        if auto_wall:
            _apply_auto_wall(P, walls, notes)
        results = [core.compute(core.replace(P, ring_r=R / CM)) for (_, _, _, R, _, _) in seats]

        if not split_mode:
            tool, faces, surf = _resolve_cut_tool(design, comp, body, cut_ent, None)
            sbs = comp.features.splitBodyFeatures
            sf = sbs.add(sbs.createInput(body, tool, True))
            halves = [sf.bodies.item(i) for i in range(sf.bodies.count)]
            if len(halves) < 2:
                raise UserError('Разрез не разделил тело на части. Проверьте, что плоскость пересекает тело '
                                'целиком.')

            def side_body(pt):
                for h in halves:
                    h = _fresh(design, h)
                    if _inside(h, pt):
                        return h
                return None

            for k, (C, D, u, R, _, _) in enumerate(seats):
                mid = _pt_add(C, u, R - P.wall * 0.5 * CM)
                own = side_body(_pt_add(mid, D, 0.03))
                oth = side_body(_pt_add(mid, D, -0.03))
                if own is None or oth is None or own.entityToken == oth.entityToken:
                    raise UserError('Кольцо %d: не удалось определить половины корпуса у шва. Проверьте '
                                    'толщину стенки и положение ребра.' % (k + 1))
                seats[k] = (C, D, u, R, own, oth)

        JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
        CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
        for (C, D, u, R, own, oth), res in zip(seats, results):
            Pk = core.replace(P, ring_r=R / CM)
            R_mm = R / CM
            collar = _make_ring(comp, C, D, u, R_mm, core.arm_polygon(Pk, res))
            slots = max(int(Pk.slots), 0)
            if slots >= 2:
                a_ax = _unit(D)
                cuts_ = []
                for j in range(slots):
                    uk = _rot(u, a_ax, 2.0 * math.pi * j / slots)
                    anchor_k = _pt_add(C, uk, R)
                    cuts_.append(_make_tool(comp, (anchor_k, D, uk), core.slot_polygon(Pk, res), Pk.slot_w))
                _combine(comp, _fresh(design, collar), [_fresh(design, t) for t in cuts_], CUT)
            groove = _make_ring(comp, C, D, u, R_mm, core.pocket_polygon(Pk, res))
            _combine(comp, _fresh(design, own), [_fresh(design, collar)], JOIN)
            _combine(comp, _fresh(design, oth), [_fresh(design, groove)], CUT)

        if _group_timeline(design, start):
            notes.append('Все операции собраны в группу «%s» на таймлайне.' % GROUP_NAME)
        res0 = results[0]
        if len(results) > 1:
            notes.append('Для нескольких колец показан расчёт первого.')
        _report(len(seats), res0, notes, 'annular')
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
