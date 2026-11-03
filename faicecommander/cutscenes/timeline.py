"""Shot lengths of the intro and outro, shared by the cutscenes and their scored music
(audio/tracks.py) so that hits and swells land on the cuts. No Panda3D imports here."""

INTRO = [("signal", 7.0), ("planet", 11.0), ("slaves", 12.5), ("mother", 9.0), ("queen", 4.5),
         ("battle", 12.5), ("pod", 5.0), ("medbay", 8.0), ("hangar", 12.0), ("waking", 9.0), ("becoming", 9.0)]

OUTRO = [("eye", 7.5), ("wave", 7.0), ("chaos", 9.0), ("collars", 9.0), ("fireworks", 10.0), ("name", 8.0),
         ("credits", 14.0)]


def starts(timeline):
    """{shot name: start time in seconds}."""
    t, out = 0.0, {}
    for name, dur in timeline:
        out[name] = t
        t += dur
    return out


def length(timeline):
    return sum(d for _, d in timeline)
