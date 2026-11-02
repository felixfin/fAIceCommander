# fAIceCommander 3D

A 3D space shooter you steer with your face: tilt your head to slide left and right, turn it to
switch weapons, open your mouth to fire, close your eyes to survive hypno pulses.

Status: **milestone 1** - face controls with calibration, level 1 (Asteroid Belt) playable, HUD,
webcam panel with the AR helmet (sunglasses and cigar included), fullscreen. Sound, music and
levels 2-7 follow in the next milestones.

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
```

## Controls

| Face | Keyboard | Effect |
|---|---|---|
| tilt head left / right | A / D or arrow keys | slide left / right (analog) |
| turn head left / right | Q / E | previous / next weapon |
| open mouth | Space | laser: one pulse per opening · shield: toggle |
| close eyes | C | hypno protection (from level 3) |

F2 hides the webcam panel, F11 toggles fullscreen, P pauses, Esc quits. During calibration,
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
  game/        world (2D logic on the play plane), entities, weapons, levels (one file per level)
  render/      procedural models, backdrop, effects, HUD, webcam view with AR helmet
  data/        config.toml, levels.toml
  assets/      face model, font
concept/       concept renders and the music teaser (see concept/web/index.html)
```
