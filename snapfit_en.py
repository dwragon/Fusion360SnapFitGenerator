# -*- coding: utf-8 -*-
"""English translation of the add-in strings: Russian source string -> English.

To add another language copy this file (for example snapfit_de.py), translate the values and
extend the language selection in snapfit_core.py. Keep the %-placeholders unchanged.
"""
EN = {
    'PA (нейлон)':
        'PA (nylon)',
    'Консольный разъёмный (60°)':
        'Cantilever, detachable (60°)',
    'Балка с крючком внутри стенки, возврат под 60°: защёлку можно открыть без поломки (корпуса, батарейные отсеки, сервисные крышки). Нужна стенка от ~2.5 мм.':
        'Beam with a hook inside the wall, 60° return angle: the snap can be opened without breaking (enclosures, battery compartments, service covers). Needs a wall of about 2.5 mm or more.',
    'Консольный неразъёмный (90°)':
        'Cantilever, permanent (90°)',
    'Балка с крючком внутри стенки, возврат под 90°: не открывается без отжатия или разрушения балки. Для крышек, которые открывать не нужно.':
        'Beam with a hook inside the wall, 90° return angle: it cannot be opened without pressing the beam aside or breaking it. For covers that never need to be opened.',
    'Накладной для тонких стенок, разъёмный (60°)':
        'Overlay for thin walls, detachable (60°)',
    'Балка стоит внутри корпуса вдоль стенки (не в толще стенки), крючок заходит в окно стенки другой половины. Для стенок 1.2-2 мм. Окно лучше сквозное.':
        'The beam sits inside the enclosure along the wall (not in the wall thickness); the hook enters a window in the wall of the other half. For walls of 1.2-2 mm. A through window is preferable.',
    'Накладной для тонких стенок, неразъёмный (90°)':
        'Overlay for thin walls, permanent (90°)',
    'То же, но возврат 90°: открыть без отжатия балки нельзя.':
        'Same, but with a 90° return angle: it cannot be opened without pressing the beam aside.',
    'U-образный накладной, разъёмный (60°)':
        'U-shaped overlay, detachable (60°)',
    'Балка сложена буквой U: большой прогиб на короткой длине, крючок на свободной ветви у линии разъёма. Занимает ~4.5 мм вглубь корпуса. Длина и усилия приближённые.':
        'The beam is folded into a U: large deflection over a short length, the hook is on the free leg next to the split line. Takes about 4.5 mm into the enclosure. Length and forces are approximate.',
    'Торсионный накладной, разъёмный (60°)':
        'Torsion overlay, detachable (60°)',
    'Рычаг с крючком сидит на торсионе: квадратном стержне вдоль стенки, концы которого закреплены в стойках своей половины. Крючок отжимается скручиванием стержня. Компактен вглубь корпуса (как накладная балка), но длиннее вдоль стенки (~15-20 мм).':
        'A lever with a hook sits on a torsion bar: a square rod along the wall whose ends are fixed in posts on its own half. Twisting the rod releases the hook. Compact into the enclosure (like an overlay beam) but longer along the wall (~15-20 mm).',
    'Торсионный с кнопкой, неразъёмный (90°)':
        'Torsion with button, permanent (90°)',
    'То же, но возврат 90°: держит жёстко, открывается нажатием на крючок через окно в стенке (штифтом или отвёрткой). Окно лучше сквозное.':
        'Same, but with a 90° return angle: it holds firmly and is opened by pressing the hook through a window in the wall (with a pin or a screwdriver). A through window is preferable.',
    'Кольцевой в стенке, разъёмный (60°)':
        'Annular in the wall, detachable (60°)',
    'Для круглых деталей: воротник с кольцевым валиком входит в канавку другой половины. Воротник разрезан прорезями на пальцы (иначе кольцо слишком жёсткое для печати). Канавка всегда глухая: нужна стенка от ~4.5 мм. Выбирай круговое ребро на шве.':
        'For round parts: a collar with an annular bead snaps into a groove of the other half. The collar is cut into fingers by slots (a solid ring is too stiff to print and assemble). The groove is always blind: needs a wall of about 4.5 mm or more. Select the circular edge on the seam.',
    'Кольцевой в стенке, неразъёмный (90°)':
        'Annular in the wall, permanent (90°)',
    'То же, но возврат 90°: после защёлкивания не разбирается без разрушения. Без прорезей и с хорошей геометрией может быть герметичным.':
        'Same, but with a 90° return angle: after snapping it cannot be taken apart without damage. Without slots and with good geometry it can be airtight.',
    'Кольцевой накладной, разъёмный (60°)':
        'Annular overlay, detachable (60°)',
    'Для круглых деталей с тонкой стенкой (от ~2 мм): воротник стоит внутри корпуса вдоль стенки, валик заходит в кольцевую канавку на внутренней стороне стенки другой половины.':
        'For round parts with a thin wall (from about 2 mm): the collar sits inside the enclosure along the wall and the bead enters an annular groove on the inner side of the wall of the other half.',
    'Длина балки меньше расчётной (%.1f мм): деформация выше допустимой.':
        'Beam length is below the calculated (%.1f mm): strain exceeds the allowed value.',
    'Для U-образной балки длина не меньше %.1f мм (иначе крючок упирается в изгиб).':
        'For a U-shaped beam the length must be at least %.1f mm (otherwise the hook hits the bend).',
    'Для глухого окна нужна стенка не меньше %.1f мм (сейчас %.1f мм). Включите «Сквозное окно».':
        'A blind window needs a wall of at least %.1f mm (now %.1f mm). Enable “Through window in the wall”.',
    'Стенка тоньше 0.8 мм: окно ослабит её слишком сильно.':
        'Wall thinner than 0.8 mm: a window would weaken it too much.',
    'Штифты отключены: для них нужна стенка не меньше 1.2 мм.':
        'Pins are disabled: they need a wall of at least 1.2 mm.',
    'Стенка %.1f мм при балке %.1f мм: упор в окне тоньше %.1f мм. Для тонкой стенки выберите «Накладной» тип.':
        'Wall %.1f mm with a %.1f mm beam: the stop in the window is thinner than %.1f mm. For a thin wall choose an overlay type.',
    'Для глухого окна нужна стенка не меньше %.1f мм (сейчас %.1f мм). Включите «Сквозное окно» или увеличьте стенку.':
        'A blind window needs a wall of at least %.1f mm (now %.1f mm). Enable “Through window in the wall” or increase the wall.',
    'Штифты: стенка слишком тонкая, остаток над штифтом меньше %.1f мм.':
        'Pins: the wall is too thin, the remainder above the pin is less than %.1f mm.',
    'Крючок слишком длинный для балки: увеличьте длину или уменьшите зацеп.':
        'The hook is too long for the beam: increase the length or reduce the engagement.',
    'Ширина балки меньше 3 линий сопла.':
        'Beam width is less than 3 nozzle lines.',
    'Толщина балки на конце меньше 0.8 мм (2 линии сопла): увеличьте толщину или конус.':
        'Beam thickness at the tip is below 0.8 mm (2 nozzle lines): increase the thickness or the taper.',
    'Скругление корня отключено: не хватает места (стенка или длина балки).':
        'Root fillet disabled: not enough room (wall or beam length).',
    'Радиус кольца %.1f мм слишком мал для такой стенки и воротника.':
        'Ring radius %.1f mm is too small for this wall and collar.',
    'Кольцо R%.1f мм: %d пальцев шириной %.1f мм, прорези %.1f мм':
        'Ring R%.1f mm: %d fingers %.1f mm wide, slots %.1f mm',
    'Пальцы уже %.0f мм: уменьшите число прорезей.':
        'Fingers narrower than %.0f mm: reduce the number of slots.',
    'Пальцы шире %.0f мм: добавьте прорези, иначе валик заходит неравномерно.':
        'Fingers wider than %.0f mm: add slots, otherwise the bead engages unevenly.',
    'Длина балки меньше расчётной':
        'Beam length is below the calculated',
    'Цельное кольцо R%.1f мм, деформация обода %.2f %%':
        'Solid ring R%.1f mm, rim strain %.2f %%',
    'Цельное кольцо: деформация %.1f %% выше допустимой %.1f %%. Добавьте прорези (пальцы) или увеличьте радиус.':
        'Solid ring: strain %.1f %% exceeds the allowed %.1f %%. Add slots (fingers) or increase the radius.',
    'Цельное кольцо слишком жёсткое для ручной сборки (усилие ~%s Н).':
        'A solid ring is too stiff for hand assembly (force ~%s N).',
    ' Включите «Сквозное окно» или увеличьте стенку.':
        ' Enable “Through window in the wall” or increase the wall.',
    ' Увеличьте стенку или выберите накладной кольцевой тип.':
        ' Increase the wall or choose an annular overlay type.',
    ' Включите «Сквозное окно».':
        ' Enable “Through window in the wall”.',
    ' Увеличьте стенку.':
        ' Increase the wall.',
    'Рычаг короче %.1f мм: крючок не помещается.':
        'The lever is shorter than %.1f mm: the hook does not fit.',
    'Рычаг изгибается (%.2f мм при зацепе %.2f мм): увеличьте толщину балки/рычага или ширину.':
        'The lever bends (%.2f mm at %.2f mm engagement): increase the beam/lever thickness or width.',
    'Рычаг уже 3 мм: слишком узкий.':
        'Lever narrower than 3 mm: too narrow.',
    'Сторона торсиона меньше 1.2 мм: при печати стержень будет слишком хрупким.':
        'Torsion bar side is below 1.2 mm: the rod will be too brittle when printed.',
    'Торсион %.1fx%.1f мм, свободная длина каждой половины %.1f мм, угол поворота %.1f°':
        'Torsion bar %.1fx%.1f mm, free length of each half %.1f mm, rotation angle %.1f°',
    'Полная длина механизма вдоль стенки: %.1f мм':
        'Total mechanism length along the wall: %.1f mm',
    'неразъёмная':
        'permanent',
    '%.0f Н':
        '%.0f N',
    '%.1f Н':
        '%.1f N',
    'Рычаг: <b>%.1f мм</b> (деформация торсиона %.2f %%)':
        'Lever: <b>%.1f mm</b> (torsion strain %.2f %%)',
    'Воротник: <b>%.1f мм</b> (деформация %.2f %%)':
        'Collar: <b>%.1f mm</b> (strain %.2f %%)',
    'Длина балки: <b>%.1f мм</b> (деформация %.2f %%)':
        'Beam length: <b>%.1f mm</b> (strain %.2f %%)',
    'Крючок: заведение %.1f мм, возврат %.1f мм':
        'Hook: lead-in %.1f mm, return %.1f mm',
    'Конец балки: %.1f мм, галтель корня: %s':
        'Beam tip: %.1f mm, root fillet: %s',
    '%.1f мм':
        '%.1f mm',
    'нет':
        'none',
    'Галтель корня: %.1f мм':
        'Root fillet: %.1f mm',
    'Усилие защёлкивания ~ %s, разъединения: %s':
        'Snap-in force ~ %s, release: %s',
    'Минимальная стенка: %.1f мм':
        'Minimum wall: %.1f mm',
    'Длина ветви меньше расчётной (%.1f мм): деформация выше допустимой.':
        'Arm length is below the calculated (%.1f mm): strain exceeds the allowed value.',
    'Пакет тоньше %.1f мм: упор крючка будет слишком хрупким.':
        'Package thinner than %.1f mm: the hook stop will be too brittle.',
    'Головка выступает на %.1f мм над поверхностью: ветви должны быть длинными. Если мешает, возьмите материал с большей допустимой деформацией, меньший зацеп или более толстый пакет.':
        'The head protrudes %.1f mm above the surface: the arms must be long. If this is a problem, use a material with a higher allowable strain, a smaller engagement or a thicker package.',
    'Ширина защёлки меньше 3 линий сопла.':
        'Fork width is less than 3 nozzle lines.',
    'Толщина ветви меньше 0.8 мм (2 линии сопла).':
        'Arm thickness is below 0.8 mm (2 nozzle lines).',
    'Прорезь в телах: %.1f x %.1f мм':
        'Slot in the bodies: %.1f x %.1f mm',
    'За пакетом нужно свободное место не меньше %.1f мм (крючки и концы ветвей)':
        'Free space of at least %.1f mm is needed behind the package (hooks and arm tips)',
    'не снимается':
        'not removable',
    'Ветвь: <b>%.1f мм</b> (деформация %.2f %%), высота крючка %.2f мм':
        'Arm: <b>%.1f mm</b> (strain %.2f %%), hook height %.2f mm',
    'Вилка %.1f x %.1f мм, головка %.1f мм':
        'Fork %.1f x %.1f mm, head %.1f mm',
    'Усилие вставки ~ %s, снятия: %s':
        'Insertion force ~ %s, removal: %s',
    'Свой диаметр':
        'Custom diameter',
    'Прорезь %.2f мм уже минимальной %.2f мм: половинки не сойдутся при заведении, взята минимальная.':
        'Slot %.2f mm is narrower than the minimum %.2f mm: the halves would not close during insertion, the minimum was used.',
    'Половинки штыря тоньше %.1f мм (%.2f мм): для такого отверстия печатная стойка хрупкая. Уменьшите зацеп или возьмите более гибкий материал.':
        'Pin halves are thinner than %.1f mm (%.2f mm): a printed post is fragile for such a hole. Reduce the engagement or use a more flexible material.',
    'Диаметр буртика увеличен до %.1f мм: он должен быть заметно больше штыря.':
        'Collar diameter increased to %.1f mm: it must be noticeably larger than the pin.',
    'оставьте шейку: высота буртика должна быть заметно меньше высоты опоры':
        'keep the neck: the collar height must be noticeably smaller than the standoff height',
    'увеличьте высоту опоры или уменьшите зацеп':
        'increase the standoff height or reduce the engagement',
    'Деформация %.1f %% выше допустимой %.1f %%: гибкая длина %.1f мм, нужно не меньше %.1f мм. %s.':
        'Strain %.1f %% exceeds the allowed %.1f %%: flexible length %.1f mm, at least %.1f mm needed. %s.',
    'Высота опоры меньше 1 мм.':
        'Standoff height is below 1 mm.',
    'Штырь под клей слишком толстый для основания стойки (диаметр основания %.1f мм).':
        'The glue-in peg is too thick for the post base (base diameter %.1f mm).',
    'Штырь под клей тоньше 1.5 мм: он оторвётся при нагрузке.':
        'The glue-in peg is thinner than 1.5 mm: it will break off under load.',
    'Стенка %.1f мм слишком тонкая для глухого отверстия под штырь.':
        'Wall %.1f mm is too thin for a blind hole for the peg.',
    'Длина штыря ограничена стенкой: %.1f мм вместо %.1f мм.':
        'Peg length limited by the wall: %.1f mm instead of %.1f mm.',
    'Штырь %.2f мм, крючок %.2f мм, прорезь %.2f мм':
        'Pin %.2f mm, hook %.2f mm, slot %.2f mm',
    'Плата садится на буртик, над платой выступает ~%.1f мм':
        'The board sits on the collar and protrudes ~%.1f mm above the board',
    'Гибкая длина: <b>%.1f мм</b> (нужно от %.1f мм), деформация %.1f %%':
        'Flexible length: <b>%.1f mm</b> (at least %.1f mm needed), strain %.1f %%',
    'Усилие установки платы ~ %s, снятия: %s':
        'Board insertion force ~ %s, removal: %s',
    'Разрезать тело (плоскость / кривая)':
        'Cut the body (plane / curve)',
    'Тела уже разделены (выбрать два тела)':
        'Bodies are already split (select two bodies)',
    'Вставная защёлка-вилка (отдельная деталь + прорези в телах)':
        'Insert fork snap (separate part + slots in the bodies)',
    'Стойки для печатной платы (штыри под метрические отверстия)':
        'PCB standoffs (pins for metric holes)',
    'Стойка в теле (печатается вместе с корпусом)':
        'Post in the body (printed with the enclosure)',
    'Отверстие в теле + отдельная стойка (вклеивается)':
        'Hole in the body + separate post (glued in)',
    '%s (отв. %.1f мм)':
        '%s (hole %.1f mm)',
    'Вилка с двумя ветвями печатается отдельно и вставляется в прорези одного или двух тел (стенка или пакет из двух стенок). Головка остаётся снаружи, крючки защёлкиваются за пакетом. Точки ставь на наружной поверхности первого тела.':
        'A fork with two arms is printed separately and inserted into slots in one or two bodies (a wall or a stack of two walls). The head stays outside and the hooks snap behind the stack. Place points on the outer surface of the first body.',
    'Разрезной штырь с конической головкой входит в метрическое отверстие платы, плата садится на буртик. Точки ставь на поверхности тела там, где должны стоять отверстия платы.':
        'A split pin with a conical head goes into a metric hole of the board and the board sits on the collar. Place points on the body surface where the board holes should be.',
    'Толщина балки':
        'Beam thickness',
    'Ширина балки':
        'Beam width',
    'Длина балки':
        'Beam length',
    'Толщина рычага = сторона торсиона':
        'Lever thickness = torsion bar side',
    'Ширина рычага':
        'Lever width',
    'Длина рычага':
        'Lever length',
    'Толщина воротника':
        'Collar thickness',
    'Ширина пальца (считается)':
        'Finger width (calculated)',
    'Длина воротника':
        'Collar length',
    'Длина по расчёту':
        'Length by calculation',
    'Тело (первое в пакете)':
        'Body (first in the stack)',
    'Тело корпуса':
        'Enclosure body',
    'Тело':
        'Body',
    'Второе тело в пакете (если есть)':
        'Second body in the stack (if any)',
    'Второе тело':
        'Second body',
    'Точки вилок':
        'Fork points',
    'Центры стоек':
        'Standoff centers',
    'Точки защёлок':
        'Snap points',
    'Режим':
        'Mode',
    'Тело, которое нужно разрезать (в режиме готовых тел - первое из двух тел)':
        'The body to cut (in the split-bodies mode, the first of the two bodies)',
    'Вторая половина корпуса':
        'The other half of the enclosure',
    'Плоскость / кривая реза':
        'Cutting plane / curve',
    'Конструкторская плоскость, грань, поверхность или эскизная кривая':
        'A construction plane, face, surface or sketch curve',
    'Точки на поверхности стенки у линии реза. Балка вырастет на той половине, на которой лежит точка (кнопка «Реверс» меняет половины)':
        'Points on the wall surface near the cut line. The beam grows on the half where the point lies (the “Reverse” button swaps the halves)',
    'Кольцевое ребро на шве':
        'Annular edge on the seam',
    'Круговое ребро на наружной цилиндрической поверхности корпуса. Ось и радиус кольца берутся из ребра; воротник вырастет на первом теле (в режиме разреза - на половине, где лежит ребро), кнопка «Реверс» меняет половины':
        'A circular edge on the outer cylindrical surface of the enclosure. The ring axis and radius are taken from the edge; the collar grows on the first body (in cut mode, on the half where the edge lies), the “Reverse” button swaps the halves',
    'Режим кривой: точки на кривой, стенки найти самому':
        'Curve mode: points on the curve, find the walls automatically',
    'Для эскизной кривой реза':
        'For a sketch cutting curve',
    'Ставьте точки прямо на кривую в эскизе. Аддин пойдёт от точки перпендикулярно плоскости эскиза и найдёт наружную стенку тела. Точки, уже лежащие на стенке, остаются как есть.':
        'Place points directly on the curve in the sketch. The add-in goes from the point perpendicular to the sketch plane and finds the outer wall of the body. Points already lying on the wall stay as they are.',
    'Защёлки на обеих противоположных стенках':
        'Snaps on both opposite walls',
    'Материал печати':
        'Print material',
    'Тип защёлки':
        'Snap type',
    'Параметры защёлки':
        'Snap parameters',
    'Толщину стенки брать с модели':
        'Take wall thickness from the model',
    'Толщина стенки (вручную)':
        'Wall thickness (manual)',
    'Величина зацепа':
        'Engagement',
    'Зазор':
        'Clearance',
    'Допустимая деформация, %':
        'Allowable strain, %',
    'Модуль E, МПа':
        'Modulus E, MPa',
    'Угол заведения':
        'Lead-in angle',
    'Угол возврата (90 = неразъёмно)':
        'Return angle (90 = permanent)',
    'Конус: толщина на конце, % от корня':
        'Taper: tip thickness, % of root',
    'Скругление корня балки':
        'Beam root fillet',
    'Направляющие штифты по бокам':
        'Guide pins on the sides',
    'Прорезей в воротнике (0 = цельное кольцо)':
        'Slots in the collar (0 = solid ring)',
    'Ширина прорези':
        'Slot width',
    'Длина балки по расчёту':
        'Beam length by calculation',
    'Сквозное окно в стенке':
        'Through window in the wall',
    'Реверс: балка на другой половине':
        'Reverse: beam on the other half',
    'Параметры вилки':
        'Fork parameters',
    'Толщину пакета брать с модели':
        'Take stack thickness from the model',
    'Толщина пакета (вручную)':
        'Stack thickness (manual)',
    'Толщина ветви':
        'Arm thickness',
    'Ширина вилки':
        'Fork width',
    'Перекрытие крючка':
        'Hook overlap',
    'Зазор в прорези':
        'Slot clearance',
    'Длина ветви по расчёту':
        'Arm length by calculation',
    'Длина ветви':
        'Arm length',
    'Толщина головки':
        'Head thickness',
    'Вылет головки за прорезь':
        'Head overhang past the slot',
    'Повернуть вилку на 90°':
        'Rotate the fork by 90°',
    'Параметры стойки для платы':
        'PCB standoff parameters',
    'Отверстие в плате':
        'Hole in the board',
    'Диаметр отверстия платы':
        'Board hole diameter',
    'Толщина платы':
        'Board thickness',
    'Высоту опоры подобрать по расчёту':
        'Choose the standoff height by calculation',
    'Высота опоры платы над телом':
        'Board standoff height above the body',
    'Диаметр буртика (0 = авто)':
        'Collar diameter (0 = auto)',
    'Высота буртика под платой':
        'Collar height under the board',
    'Ширина прорези (0 = авто)':
        'Slot width (0 = auto)',
    'Зазор штыря в отверстии (по диаметру)':
        'Pin clearance in the hole (diametral)',
    'Исполнение':
        'Variant',
    'Толщину стенки под стойкой брать с модели':
        'Take the wall thickness under the standoff from the model',
    'Толщина стенки под стойкой (вручную)':
        'Wall thickness under the standoff (manual)',
    'Диаметр клеевого штыря':
        'Glue-in peg diameter',
    'Длина клеевого штыря':
        'Glue-in peg length',
    'Повернуть прорезь на 90°':
        'Rotate the slot by 90°',
    'Language / Язык (применится после перезапуска аддина)':
        'Language (applies after the add-in restarts)',
    'Сбросить настройки к заводским (отметь галку)':
        'Reset settings to factory defaults (check the box)',
    'Расчёт':
        'Calculation',
    'Ошибка создания диалога:\n':
        'Dialog creation error:\n',
    'Для кольцевой защёлки выберите одну плоскость или плоскую грань реза.':
        'For an annular snap select one plane or a flat cutting face.',
    'Несколько объектов реза можно выбирать только для линий эскиза. Плоскость или грань выбирайте по одной.':
        'Several cutting objects can be selected only for sketch lines. Select a plane or face one at a time.',
    'Не удалось построить защёлки:\n\n':
        'Could not build the snaps:\n\n',
    '\n\nИзменения откатаны (если нет - Ctrl+Z).':
        '\n\nChanges were rolled back (if not, press Ctrl+Z).',
    'Неподдерживаемый тип точки.':
        'Unsupported point type.',
    'Не удалось получить нормаль поверхности.':
        'Could not get the surface normal.',
    'Точка лежит дальше 3 мм от поверхности тела. Поставьте её на внешнюю поверхность стенки в месте реза.':
        'The point is farther than 3 mm from the body surface. Place it on the outer surface of the wall at the cut.',
    'Неподдерживаемый тип инструмента реза.':
        'Unsupported cutting tool type.',
    'Профиль защёлки не замкнулся (проверьте параметры).':
        'The snap profile did not close (check the parameters).',
    'Профиль не найден.':
        'Profile not found.',
    'Fusion не смог выполнить вращение профиля (Revolve): %s. Проверьте, что ребро кольца лежит на цилиндре, а размеры воротника помещаются в стенку.':
        'Fusion could not perform the Revolve of the profile: %s. Check that the ring edge lies on the cylinder and that the collar dimensions fit into the wall.',
    'Профиль кольцевой защёлки не замкнулся (проверьте параметры).':
        'The annular snap profile did not close (check the parameters).',
    'В одной из точек стенка параллельна плоскости реза: защёлку там построить нельзя.':
        'At one of the points the wall is parallel to the cutting plane: a snap cannot be built there.',
    'Точка лежит дальше 3 мм от обоих тел. Поставьте её на поверхность одного из тел.':
        'The point is farther than 3 mm from both bodies. Place it on the surface of one of the bodies.',
    'Не удалось найти стык двух тел у точки. Тела должны касаться друг друга или находиться рядом, а точка лежать на краю стыка.':
        'Could not find the joint of the two bodies at the point. The bodies must touch or be close together, and the point must lie at the edge of the joint.',
    'В одной из точек стенка параллельна стыку тел: защёлку там построить нельзя.':
        'At one of the points the wall is parallel to the body joint: a snap cannot be built there.',
    'Толщина стенки в точках разная (%.1f-%.1f мм), взята минимальная.':
        'Wall thickness differs between points (%.1f-%.1f mm), the minimum was used.',
    'Толщина стенки по модели: %.2f мм.':
        'Wall thickness from the model: %.2f mm.',
    'Не удалось измерить стенку по модели, использовано значение из поля (%.1f мм). Проверьте его.':
        'Could not measure the wall from the model, the value from the field was used (%.1f mm). Please check it.',
    'защёлк(и)':
        'snap(s)',
    'длина балки':
        'beam length',
    'торсионных защёлк(и)':
        'torsion snap(s)',
    'длина рычага':
        'lever length',
    'кольцевых защёлк(и)':
        'annular snap(s)',
    'длина воротника':
        'collar length',
    'Готово: %d %s, %s %.1f мм.':
        'Done: %d %s, %s %.1f mm.',
    '\n\nПредупреждения:\n- ':
        '\n\nWarnings:\n- ',
    'Включите историю (параметрический режим): Capture Design History.':
        'Enable design history (parametric mode): Capture Design History.',
    'Выберите тело корневого компонента (или активируйте нужный компонент).':
        'Select a body of the root component (or activate the needed component).',
    'От точки на кривой не найдена стенка тела вдоль оси выдавливания. Проверьте положение точки.':
        'No body wall was found from the point on the curve along the extrusion axis. Check the point position.',
    'Точки на кривой: найдено мест для защёлок - %d.':
        'Points on the curve: snap locations found - %d.',
    'Точек на самой линии реза: %d. Для них сторона балки не определяется по положению точки; если балка выросла не там, включите «Реверс».':
        'Points exactly on the cut line: %d. For them the beam side cannot be determined from the point position; if the beam grew on the wrong half, enable “Reverse”.',
    'Разрез не разделил тело на части. Проверьте, что плоскость/кривая пересекает тело целиком.':
        'The cut did not split the body. Check that the plane/curve crosses the whole body.',
    'Точка %d: не удалось определить половины корпуса около защёлки. Проверьте толщину стенки и положение точки.':
        'Point %d: could not determine the enclosure halves near the snap. Check the wall thickness and the point position.',
    'Все операции собраны в группу «%s» на таймлайне.':
        'All operations are collected into the “%s” group on the timeline.',
    'Выберите два разных тела.':
        'Select two different bodies.',
    'Оба тела должны лежать в одном компоненте.':
        'Both bodies must be in the same component.',
    'Выберите круговое ребро (полная окружность) на шве корпуса.':
        'Select a circular edge (a full circle) on the enclosure seam.',
    'Ось кольца не перпендикулярна плоскости реза: кольцо и плоскость должны быть соосны.':
        'The ring axis is not perpendicular to the cutting plane: the ring and the plane must be coaxial.',
    'Кольцевое ребро не лежит на шве первого тела: рядом с ним нет материала тела.':
        'The annular edge does not lie on the seam of the first body: there is no body material next to it.',
    'Второе тело не найдено по другую сторону шва у кольцевого ребра. Тела должны касаться друг друга по шву.':
        'The second body was not found on the other side of the seam at the annular edge. The bodies must touch along the seam.',
    'Первое тело не найдено на нужной стороне шва у кольцевого ребра.':
        'The first body was not found on the required side of the seam at the annular edge.',
    'Кольцевую защёлку можно построить при разрезе плоскостью или плоской гранью. Для кривой реза выберите режим консольной или торсионной защёлки.':
        'An annular snap can be built with a plane or flat face cut. For a curve cut choose a cantilever or torsion snap.',
    'Кольцо не лежит на наружной цилиндрической поверхности корпуса у шва (радиус или положение ребра не совпадают с телом).':
        'The ring does not lie on the outer cylindrical surface of the enclosure at the seam (the edge radius or position does not match the body).',
    'Разрез не разделил тело на части. Проверьте, что плоскость пересекает тело целиком.':
        'The cut did not split the body. Check that the plane crosses the whole body.',
    'Кольцо %d: не удалось определить половины корпуса у шва. Проверьте толщину стенки и положение ребра.':
        'Ring %d: could not determine the enclosure halves at the seam. Check the wall thickness and the edge position.',
    'Для нескольких колец показан расчёт первого.':
        'For several rings the calculation of the first one is shown.',
    'Профиль стойки не замкнулся (проверьте параметры).':
        'The standoff profile did not close (check the parameters).',
    'Толщина пакета по модели: %.2f мм.':
        'Stack thickness from the model: %.2f mm.',
    'Толщина пакета в точках разная (%.1f-%.1f мм), взята минимальная.':
        'Stack thickness differs between points (%.1f-%.1f mm), the minimum was used.',
    'Не удалось измерить пакет по модели, использовано значение из поля (%.1f мм). Проверьте его.':
        'Could not measure the stack from the model, the value from the field was used (%.1f mm). Please check it.',
    'Точка %d: под ней нет материала первого тела на глубину пакета. Поставьте точку на наружную поверхность стенки.':
        'Point %d: there is no material of the first body under it to the stack depth. Place the point on the outer surface of the wall.',
    'Точка %d: второе тело не попадает в пакет, прорезь в нём не сделана.':
        'Point %d: the second body is not in the stack, no slot was cut in it.',
    'Не удалось вырезать прорезь.':
        'Could not cut the slot.',
    'Готово: %d вилок(и), ветвь %.1f мм, пакет %.1f мм.\nВилки созданы отдельными телами «Snap pin» в рабочем положении; в телах вырезаны прорези.':
        'Done: %d fork(s), arm %.1f mm, stack %.1f mm.\nThe forks were created as separate “Snap pin” bodies in their working position; slots were cut in the bodies.',
    'Готово: %d стоек(и) под отверстие %.1f мм.':
        'Done: %d standoff(s) for a %.1f mm hole.',
    '\nСтойки созданы отдельными телами «PCB post» (в рабочем положении), в теле сделаны глухие отверстия под клей.':
        '\nThe posts were created as separate “PCB post” bodies (in their working position); blind glue holes were made in the body.',
    'Разрезает тело на две половины и строит защёлки под FDM-печать':
        'Splits a body in two halves and builds snap-fits for FDM printing',
    'Ошибка запуска аддина:\n':
        'Add-in start error:\n',
    'Ошибка остановки аддина:\n':
        'Add-in stop error:\n',
}
