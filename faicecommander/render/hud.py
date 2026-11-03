"""2D overlay: hull/energy bars, weapon slots, star progress, score, messages and the control panel."""
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import CardMaker, Filename, TextNode, TransparencyAttrib

from ..config import ASSETS_DIR

GREEN, RED, CYAN, PINK, GOLD, GREY = (0.45, 1, 0.6, 1), (1, 0.32, 0.3, 1), (0.35, 0.85, 1, 1), \
    (1, 0.45, 0.85, 1), (1, 0.93, 0.68, 1), (0.6, 0.65, 0.75, 1)
WEAPON_COLORS = {"laser": (0.5, 1, 0.35, 1), "beam": (0.35, 1, 0.85, 1), "nuke": (1, 0.38, 0.28, 1),
                 "shield": (0.35, 0.65, 1, 1)}


def rect(parent, l, r, b, t, color):
    cm = CardMaker("rect")
    cm.setFrame(l, r, b, t)
    np_ = parent.attachNewNode(cm.generate())
    np_.setColor(*color)
    np_.setTransparency(TransparencyAttrib.MAlpha)
    return np_


def outline(parent, l, r, b, t, color, w=0.004):
    node = parent.attachNewNode("outline")
    for args in ((l, r, b, b + w), (l, r, t - w, t), (l, l + w, b, t), (r - w, r, b, t)):
        rect(node, *args, color)
    return node


class Bar:
    def __init__(self, parent, x, y, width, height, color, segments=20):
        self.node = parent.attachNewNode("bar")
        self.node.setPos(x, 0, y)
        self.frame = outline(self.node, 0, width, 0, height, color)
        pad = height * 0.18
        sw = (width - 2 * pad) / segments
        self.segs = [rect(self.node, pad + i * sw, pad + (i + 1) * sw - sw * 0.2, pad, height - pad, color)
                     for i in range(segments)]

    def set(self, frac, color=None):
        n = round(max(0.0, min(1.0, frac)) * len(self.segs))
        for i, s in enumerate(self.segs):
            s.show() if i < n else s.hide()
            if color:
                s.setColor(*color)
        if color:
            self.frame.setColor(*color)


class Gauge:
    def __init__(self, parent, font, label, x, y, width, color):
        self.node = parent.attachNewNode("gauge")
        self.node.setPos(x, 0, y)
        OnscreenText(label, parent=self.node, pos=(0, -0.012), scale=0.04, fg=GREY, align=TextNode.ALeft, font=font)
        self.x0, self.w = 0.2, width
        rect(self.node, self.x0, self.x0 + width, -0.003, 0.003, (0.3, 0.33, 0.42, 1))
        rect(self.node, self.x0 + width / 2 - 0.002, self.x0 + width / 2 + 0.002, -0.02, 0.02, (0.3, 0.33, 0.42, 1))
        self.dot = rect(self.node, -0.014, 0.014, -0.014, 0.014, color)

    def set(self, value, bipolar=True):
        v = (value + 1) / 2 if bipolar else value
        self.dot.setX(self.x0 + max(0.0, min(1.0, v)) * self.w)


class Hud:
    def __init__(self, base):
        self.base = base
        self.font = base.loader.loadFont(Filename.fromOsSpecific(str(ASSETS_DIR / "fonts" / "ChakraPetch-SemiBold.ttf")).getFullpath())
        self.font.setPixelsPerUnit(80)
        tl, tr = base.a2dTopLeft, base.a2dTopRight
        t = dict(font=self.font, mayChange=True)
        self.labels = [OnscreenText("HULL", parent=tl, pos=(0.05, -0.085), scale=0.042, fg=GREEN, align=TextNode.ALeft, **t),
                       OnscreenText("ENERGY", parent=tl, pos=(0.05, -0.155), scale=0.042, fg=CYAN, align=TextNode.ALeft, **t)]
        self.hull = Bar(tl, 0.25, -0.1, 0.62, 0.05, GREEN)
        self.energy = Bar(tl, 0.25, -0.17, 0.62, 0.05, CYAN)
        self.score = OnscreenText("0000000", parent=tr, pos=(-0.05, -0.12), scale=0.085, fg=GOLD, align=TextNode.ARight, **t)
        self.level = OnscreenText("", parent=tr, pos=(-0.05, -0.19), scale=0.042, fg=PINK, align=TextNode.ARight, **t)
        # weapon slots, top centre
        self.slots = {}
        top = base.aspect2d.attachNewNode("top-centre")
        self.top = top
        for i, name in enumerate(("laser", "beam", "nuke", "shield")):
            x = -0.57 + i * 0.29
            node = top.attachNewNode(name)
            node.setX(x)
            c = WEAPON_COLORS[name]
            box_ = outline(node, 0, 0.27, -0.065, 0.0, c, 0.005)
            fill = rect(node, 0, 0.27, -0.065, 0.0, (c[0], c[1], c[2], 0.22))
            label = OnscreenText(name.upper(), parent=node, pos=(0.135, -0.045), scale=0.04, fg=c, **t)
            self.slots[name] = (node, box_, fill, label)
        self.progress_label = OnscreenText("NEXT STAR", parent=top, pos=(-0.57, -0.12), scale=0.032, fg=GREY,
                                           align=TextNode.ALeft, **t)
        self.progress = Bar(top, -0.36, -0.13, 0.93, 0.025, (0.9, 0.85, 1, 1), segments=40)
        self.note = OnscreenText("", parent=top, pos=(0.105, -0.19), scale=0.04, fg=GOLD, **t)
        # centre messages (game area)
        self.center = base.aspect2d.attachNewNode("centre")
        self.title = OnscreenText("", parent=self.center, pos=(0, 0.08), scale=0.12, fg=PINK, **t)
        self.subtitle = OnscreenText("", parent=self.center, pos=(0, -0.02), scale=0.05, fg=(0.9, 0.92, 1, 1), **t)
        self.hint = OnscreenText("", parent=self.center, pos=(0, -0.1), scale=0.04, fg=GREY, **t)
        self.warning = OnscreenText("", parent=self.center, pos=(0, -0.3), scale=0.055, fg=RED, **t)
        self.menu = OnscreenText("", parent=self.center, pos=(0, -0.08), scale=0.055, fg=(0.9, 0.92, 1, 1), **t)
        self.columns = [OnscreenText("", parent=self.center, pos=(x, 0.0), scale=0.036, fg=(0.85, 0.9, 1, 1), **t)
                        for x in (-0.85, 0.0, 0.85)]
        # control panel
        self.panel = base.aspect2d.attachNewNode("panel")
        self.panel_left = base.a2dBottomLeft.attachNewNode("panel-left")
        self.panel_right = base.a2dBottomRight.attachNewNode("panel-right")
        self.panel_line = rect(self.panel, -10, 10, -0.002, 0.002, (1, 0.25, 0.8, 1))
        OnscreenText("CONTROLS", parent=self.panel_left, pos=(0.06, 0.0), scale=0.042, fg=PINK, align=TextNode.ALeft, **t)
        self.gauges = {
            "tilt": Gauge(self.panel_left, self.font, "Tilt", 0.06, -0.08, 0.5, (0.45, 1, 0.6, 1)),
            "turn": Gauge(self.panel_left, self.font, "Turn", 0.06, -0.15, 0.5, (1, 0.8, 0.3, 1)),
            "mouth": Gauge(self.panel_left, self.font, "Mouth", 0.06, -0.22, 0.5, (1, 0.4, 0.4, 1)),
            "eyes": Gauge(self.panel_left, self.font, "Eyes", 0.06, -0.29, 0.5, (0.75, 0.5, 1, 1)),
        }
        OnscreenText("SYSTEM", parent=self.panel_right, pos=(-0.06, 0.0), scale=0.042, fg=PINK, align=TextNode.ARight, **t)
        self.status = OnscreenText("", parent=self.panel_right, pos=(-0.06, -0.08), scale=0.036,
                                   fg=(0.85, 0.9, 1, 1), align=TextNode.ARight, **t)
        self.track = OnscreenText("", parent=self.panel_right, pos=(-0.06, -0.2), scale=0.036,
                                  fg=(0.55, 0.85, 1, 1), align=TextNode.ARight, **t)
        self.keys = OnscreenText("F2 panel  ·  F11 fullscreen  ·  M mute  ·  P pause  ·  Esc menu", parent=self.panel_right,
                                 pos=(-0.06, -0.3), scale=0.03, fg=GREY, align=TextNode.ARight, **t)
        self.cam_note = OnscreenText("", parent=self.panel, pos=(0, 0), scale=0.04, fg=GREY, **t)
        self.set_weapons(["laser", "shield"], "laser", nukes=0)

    def layout(self, panel_frac, panel_visible):
        """panel_frac: share of the window height used by the panel (0 if hidden)."""
        game_bottom = -1 + 2 * panel_frac  # in aspect2d / render2d y
        self.top.setZ(0.97)
        self.center.setZ((1 + game_bottom) / 2)
        self.panel.setZ(game_bottom)
        self.cam_note.setPos(0, -panel_frac)
        top_of_panel = 2 * panel_frac
        scale = min(1.0, top_of_panel / 0.44) if panel_frac > 0 else 1.0
        for node in (self.panel_left, self.panel_right):
            node.setZ(top_of_panel - 0.07 * scale)
            node.setScale(scale)
        for node in (self.panel, self.panel_left, self.panel_right):
            node.show() if panel_visible else node.hide()

    def set_weapons(self, unlocked, selected, nukes=0):
        for name, (node, box_, fill, label) in self.slots.items():
            avail = name in unlocked
            sel = name == selected
            node.setAlphaScale(1.0 if avail else 0.3)
            fill.show() if sel else fill.hide()
            label.setText(f"NUKE ×{nukes}" if name == "nuke" and avail else name.upper())

    def set_level_info(self, label, note):
        self.progress_label.setText(label)
        self.note.setText(note)

    def set_menu(self, items, selected):
        """items: list of (label, enabled). Turn your head / Q/E / arrows to move, mouth / SPACE to choose."""
        lines = []
        for i, (label, enabled) in enumerate(items):
            text = label if enabled else f"{label} (locked)"
            lines.append(f">  {text}  <" if i == selected else text)
        self.menu.setText("\n".join(lines))

    def set_columns(self, texts):
        for col, text in zip(self.columns, list(texts) + [""] * 3):
            col.setText(text)

    def set_stats(self, hull, energy, score, level_name, progress):
        self.hull.set(hull / 100, GREEN if hull > 35 else RED)
        self.energy.set(energy / 100)
        self.score.setText(f"{int(score):07d}")
        self.level.setText(level_name)
        self.progress.set(progress)

    def set_gauges(self, ctl):
        self.gauges["tilt"].set(ctl.tilt_gauge)
        self.gauges["turn"].set(ctl.turn_gauge)
        self.gauges["mouth"].set(ctl.mouth_gauge, bipolar=False)
        self.gauges["eyes"].set(ctl.eyes_gauge, bipolar=False)

    def message(self, title="", subtitle="", hint=""):
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.hint.setText(hint)

    def set_warning(self, text):
        self.warning.setText(text)

    def set_status(self, text):
        self.status.setText(text)

    def set_track(self, title, build_progress, muted):
        if muted:
            text = "SOUND MUTED (M)"
        elif build_progress < 1.0 and not title:
            text = f"synthesizing soundtrack · {build_progress * 100:.0f} %"
        else:
            text = f"SOUNDTRACK · {title}" if title else ""
        self.track.setText(text)

    def show_game_hud(self, visible):
        for node in (self.top, self.hull.node, self.energy.node, self.score, self.level, *self.labels):
            node.show() if visible else node.hide()
