# fAIceCommander 3D

A 3D space shooter you steer with your face: tilt your head to slide left and right, turn it to
switch weapons, open your mouth to fire, close your eyes to survive hypno pulses.

Status: **milestone 2** - face controls with calibration, levels 1 (Asteroid Belt) and 2 (Debris Field),
all four weapons (laser, beam, nukes, shield), explosions that are heard when their shockwave reaches you,
procedural sound effects and an adaptive drum & bass soundtrack, HUD, webcam panel with the AR helmet,
fullscreen. Levels 3-7, intro, outro, highscores and Easy/Hard selection follow in the next milestones.

On first launch the soundtrack is synthesized once (a few seconds) into
`%LOCALAPPDATA%\fAIceCommander3D\audio`; the panel shows the progress.

## Setup

Requires Python 3.12 on Windows (other platforms should work but are untested) and a webcam.

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```
.venv\Scripts\python -m faicecommander              # fullscreen, webcam
.venv\Scripts\python -m faicecommander --windowed   # in a window
.venv\Scripts\python -m faicecommander --no-camera  # keyboard only
.venv\Scripts\python -m faicecommander --level 2    # practice a level directly
```

## Controls

| Face | Keyboard | Effect |
|---|---|---|
| tilt head left / right | A / D or arrow keys | slide left / right (analog) |
| turn head left / right | Q / E | previous / next weapon |
| open mouth | Space | laser: one pulse per opening · beam: fires while open · nuke: one per opening · shield: toggle |
| close eyes | C | hypno protection (from level 3) |

F2 hides the webcam panel, F11 toggles fullscreen, M mutes, P pauses, Esc quits. During calibration,
Enter skips to the game with default thresholds. The game pauses by itself when it loses your face.

Tuning lives in `faicecommander/data/config.toml` (controls, physics) and `levels.toml` (level numbers).

## Tests

```
.venv\Scripts\python -m pytest tests
.venv\Scripts\python -m faicecommander --offscreen --no-camera --autopilot 10 --screenshot shot.png
```

## Layout

```
faicecommander/
  core/        app shell (window, display regions, state machine), game states
  input/       face tracker thread (MediaPipe), gesture mapping, keyboard fallback
  audio/       synthesizer, sound effects, soundtrack stems, cache, music director
  game/        world (2D logic on the play plane), entities, weapons, levels (one file per level)
  render/      procedural models, backdrop, effects, HUD, webcam view with AR helmet
  data/        config.toml, levels.toml
  assets/      face model, font
concept/       concept renders and the music teaser (see concept/web/index.html)
```
