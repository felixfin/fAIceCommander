# fAIceCommander 3D

A 3D space shooter you steer with your face: tilt your head to slide left and right, turn it to
switch weapons, open your mouth to fire, close your eyes to survive hypno pulses.

Status: **milestone 4** - the complete game. An in-engine intro that ends with you becoming FaceCommander
(live webcam + helmet), a main menu controlled with your face, seven levels up to the boss fight against the
Mother (damage zones, aimed shots, black hole bombs, travelling hypno pulses, regeneration), an outro, an
endless mode unlocked by winning, Easy / Hard / practice modes and local top-10 highscores per mode.

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
.venv\Scripts\python -m faicecommander --level 7    # jump straight into a level (1-7)
```

## Controls

| Face | Keyboard | Effect |
|---|---|---|
| tilt head left / right | A / D or arrow keys | slide left / right (analog) |
| turn head left / right | Q / E | previous / next weapon |
| open mouth | Space | laser: one pulse per opening · beam: fires while open · nuke: one per opening · shield: toggle |
| close eyes | C | hypno protection (from level 3) |

F2 hides the webcam panel, F11 toggles fullscreen, M mutes, P pauses, Esc goes back (menu / skip).
In menus, turn your head (Q/E, arrows) to move and open your mouth (Space, Enter) to choose.
Space, Esc or holding your mouth open skips the intro. Highscore names are typed on the keyboard. During calibration,
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
  cutscenes/   intro and outro, built from the game's own models
  game/        world (2D logic on the play plane), entities, weapons, levels (one file per level)
  render/      procedural models, backdrop, effects, HUD, webcam view with AR helmet
  data/        config.toml, levels.toml
  assets/      face model, font
concept/       concept renders and the music teaser (see concept/web/index.html)
```

## Modes

- **Easy** - after a game over you retry the level you failed, with the score you started it with.
- **Hard** - one run from level 1; a game over ends it.
- **Endless** - unlocked by defeating the Mother: mixed waves at rising difficulty.
- **Practice** - play any single level; no highscore.

Highscores and the endless unlock are stored in `%LOCALAPPDATA%\fAIceCommander3D\save.json`.

## Voice-over

Intro and outro are narrated; the lines are also shown as captions. The voices were generated
offline with Piper TTS and post-processed (EQ, compression, radio/robot effects, reverb) - see
`tools/voice/`. Piper is a development tool only and is not part of the game. To replace a line,
put your own `<id>.wav` into `faicecommander/assets/voice/` (ids and texts in `LINES.txt`).
Missing files are skipped; the volume is `audio.voice` in `config.toml`.
