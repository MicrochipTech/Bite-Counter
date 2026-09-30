---
name: setup
description: "Walk through first-time setup of the Bite-Counter meal monitoring demo on Windows."
argument-hint: ""
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion
---

# Skill: Set Up Bite-Counter on Windows

> Interactive setup guide for the meal monitoring dashboard on a Windows machine with Hailo-8 via Thunderbolt.

## When This Skill Is Loaded

Walk the user through each step below. Check prerequisites, run commands, and verify each step succeeds before moving to the next. If a step fails, diagnose and help fix it before proceeding.

## Step 1: Check Prerequisites

Verify these are available. Run the check commands and report results:

```cmd
python --version
git --version
hailortcli fw-control identify
```

- **Python 3.10+** required — if missing, direct to https://python.org
- **Git** required — if missing, direct to https://git-scm.com
- **HailoRT + Hailo-8 device** required — if `hailortcli` fails:
  - Check Thunderbolt enclosure is powered on
  - Check Thunderbolt device is authorized in Windows Settings > Thunderbolt
  - If HailoRT not installed, direct to https://hailo.ai/developer-zone/ (Software Downloads > HailoRT > Windows)
  - If `Code 10` error in Device Manager, BIOS Thunderbolt security must be set to No Security / SL0 (requires reboot)

**Note the HailoRT version** from `hailortcli fw-control identify` — the Python wheel must match this version exactly.

## Step 2: Run setup.bat

```cmd
.\setup.bat
```

This clones hailo-apps (pinned to v26.03.1) into `deps/`, creates an isolated Python venv, patches BYTETracker to remove the C++ compiler dependency, and installs all packages (including pillow and pygrabber). Verify it completed without errors.

## Step 3: Install HailoRT Python Wheel

Ask the user where they downloaded the HailoRT Python wheel (.whl file).

**IMPORTANT:** The wheel must match **both**:
- The installed HailoRT runtime version (e.g. 4.24.0)
- The Python version (e.g. cp312 for Python 3.12)

Example: HailoRT 4.24.0 + Python 3.12 → `hailort-4.24.0-cp312-cp312-win_amd64.whl`

```cmd
.\venv\Scripts\activate
pip install <path-to-wheel>
```

Verify the install:

```cmd
python -c "from hailo_platform import VDevice; print('HailoRT Python bindings OK')"
```

**If you get `DLL load failed ... _pyhailort`:** The wheel version doesn't match the runtime. Check:
- `hailortcli fw-control identify` for the runtime version
- `python --version` for the Python version
- Reinstall the correct wheel

If the user hasn't downloaded the wheel yet, direct them to Hailo Developer Zone > Software Downloads > HailoRT > Python wheel for Windows.

## Step 4: Test Launch

```cmd
.\run.bat
```

Check the terminal output for:
- `Found HEF in resources: ...yolov8m.hef` (OD model loaded)
- `Loading pose model: ...yolov8s_pose.hef` (pose model loaded)
- Camera window opens with two panels (camera feed + dashboard)

Models download automatically on first run (~40 MB). If download fails, check internet connectivity.

**If you get `HAILO_OUT_OF_PHYSICAL_DEVICES`:** Another process is using the Hailo chip. Close any other Hailo app or Python process and retry.

## Step 5: Verify Gesture Detection

Guide the user through this quick test:

1. Place a bottle or cup in front of the camera — should appear under "Utensils" on the dashboard
2. Raise hand to mouth with bent elbow — gesture should change from "Resting" to "Eating" or "Drinking"
3. Lower hands and stay still — gesture should return to "Resting" after a few seconds
4. Check FPS in terminal — should be ~10-15 with dual models

## Troubleshooting

If any step fails, diagnose using these common fixes:

| Problem | Fix |
|---------|-----|
| `No Hailo device found` | Power cycle enclosure, authorize Thunderbolt in Windows Settings, re-run HailoRT installer |
| `DLL load failed ... _pyhailort` | Wheel version mismatch. Reinstall the `.whl` matching both HailoRT runtime version and Python version |
| `HAILO_OUT_OF_PHYSICAL_DEVICES` | Another process is using the Hailo chip. Close other Hailo apps/Python processes |
| `Code 10` in Device Manager | Reboot into BIOS, set Thunderbolt Security to No Security / SL0, enable PCIe Tunneling |
| Camera black/won't open | Close Teams/Zoom/browser using webcam. Try `.\run.bat -i 1` for alternate camera |
| `ModuleNotFoundError: hailo_platform` | Re-activate venv, re-install .whl |
| `ModuleNotFoundError: hailo_apps` | Check that `deps\hailo-apps` exists (re-run `setup.bat`), check PYTHONPATH |
| Models won't download | Check internet. Manual download: place .hef files in `C:\usr\local\hailo\resources\models\hailo8\` |
| Gesture stuck on Resting | Check pose model loaded in logs. Move hand clearly to face with bent elbow |
| FPS < 5 | Close other apps. Verify Thunderbolt (not USB fallback). Try `.\run.bat --no-gesture` |

## Success

When the user confirms the dashboard is running with food detection and gesture classification working, the setup is complete. Remind them:

- `.\run.bat` to launch anytime
- `.\run.bat --no-gesture` for higher FPS without gesture detection
- Press Q or Esc to quit
- See `docs/architecture.md` for how the system works
