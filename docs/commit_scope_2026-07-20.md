# Commit Scope - 2026-07-20

## Recommended Commit Theme

```text
fix(mmapi): validate EGLImage VPI warp path
```

This commit should capture the Regular gate device-side path closure:

```text
1. freeze the accepted BGR8 VPI Python correctness path;
2. replace the rejected C++ CUDA pitch-pointer wrapper with the C++ EGLImage-wrapper candidate;
3. record five-clip Regular EGLImage validation and Regular05 timing;
4. record the direct NvBuffer-input negative evidence.
```

## Include

Source/config/docs that describe reproducible work:

```text
README.md
configs/harness/contracts/orin_next_engineering_loop_v1.json
configs/harness/contracts/regular_gate_inclusion_validation_v1.json
docs/presentation/one_page_summary.md
docs/regular_gate_inclusion_validation_2026-07-20.md
docs/regular_gate_vpi_distortion_fix_2026-07-20.md
docs/regular_gate_eglimage_fix_2026-07-20.md
docs/regular_gate_eglimage_timing_2026-07-20.md
docs/regular_gate_nvbuffer_input_probe_2026-07-20.md
scripts/patch_mmapi_vpi_transcode_eglimage_warp.py
scripts/patch_mmapi_vpi_transcode_nvbuffer_input_warp.py
scripts/summarize_egl_stage_timing.py
scripts/summarize_vpi_warp_log.py
```

## Do Not Include

Local evidence, generated videos, raw data, internal materials, and temporary
prompt entrypoints:

```text
results/
data/raw/
data/sources/
C:\Users\Admin\Videos\orin nx\
*.mp4
*.h264
*.avi
*.mov
*.mkv
.local_knowledge/
orin nx 项目口播模板.txt
docs/regular_gate_internal_ai_prompt_2026-07-20.md
```

`orin nx 项目口播模板.txt` is the current task entrypoint and may contain
temporary user instructions. Do not commit it unless the user explicitly asks to
version that prompt.

`docs/regular_gate_internal_ai_prompt_2026-07-20.md` is untracked and was not
needed for the accepted EGLImage path closure. Keep it out of the commit unless
the user explicitly wants to preserve that prompt.

## Evidence To Mention In Commit/PR Text

```text
BGR8 correctness path:
  User accepted five Regular BGR8 review grids.

C++ EGLImage-wrapper path:
  User accepted five Regular EGLImage-wrapper review grids.
  Five Regular inclusion matrices ran with rc=0, fallback=0, frame-index mismatch=0.

Timing:
  Regular05 wall time ~= 2002 ms for 180 frames.
  VPI warp-only running avg ~= 1.55 ms.
  EGLImage scratch-buffer stage running avg ~= 10.5 ms.

Negative evidence:
  Direct NvBuffer input wrapper failed with:
  "Input and output images must have the same format", rc=139.
```

## Pre-Commit Checks

```powershell
py -3.12 -m json.tool configs\harness\contracts\orin_next_engineering_loop_v1.json
py -3.12 -m json.tool configs\harness\contracts\regular_gate_inclusion_validation_v1.json
py -3.12 -m py_compile scripts\patch_mmapi_vpi_transcode_eglimage_warp.py scripts\patch_mmapi_vpi_transcode_nvbuffer_input_warp.py scripts\summarize_egl_stage_timing.py scripts\summarize_vpi_warp_log.py
py -3.12 scripts\harness_runner.py doctor
git status --short
git diff --stat
```
