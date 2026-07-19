# AGENTS.md - project entrypoint

This file is a lightweight dispatcher for future AI agents working on this project. Keep it concise: do not turn it into a progress log, a long design document, or a second notebook. Put detailed experiment records, screenshots, videos, benchmark tables, and conclusions in separate project documents when they exist.

## First Read

1. Project requirement prompt and current intent:

```text
C:\Users\Admin\Desktop\orin nx project\orin nx 项目口播模板.txt
```

This `.txt` file is the current authoritative oral-template entrypoint. Do not
look for or create an `.md` oral-template replacement unless the user explicitly
changes this rule.

2. Progressive onboarding manifest:

```text
C:\Users\Admin\Desktop\orin nx project\configs\harness\onboarding_manifest.json
```

Use the manifest to keep startup lightweight. The default startup path is:

```powershell
py -3.12 scripts\harness_runner.py onboard
```

Do not full-read the long-term context document, full internal reference folders,
or all evidence directories during default startup. First read the manifest,
active contracts, and exact task-specific docs. Load long documents only when a
trigger in the manifest or active Done Contract requires them.

3. Active overall engineering loop:

```text
C:\Users\Admin\Desktop\orin nx project\configs\harness\contracts\orin_next_engineering_loop_v1.json
```

This contract owns the current P0-P3 task sequence. Unless the user changes the
objective, future agents should continue that loop until all tasks are complete
or a declared stop reason is hit.

4. Current task-specific Done Contract:

```text
C:\Users\Admin\Desktop\orin nx project\configs\harness\contracts\regular_gate_inclusion_validation_v1.json
```

This is the current Regular gate inclusion / viewport correctness entry. It
starts from source-to-destination matrices and the color-fixed VPI Python
allocated-image path with explicit `BGR8` input. The old MMAPI EGL pitch-wrapper
path is diagnostic only because non-identity matrices caused visible block
tearing.

5. High-level project target reference, especially "项目二：Jetson Orin NX 视频稳像（EIS）与异构加速":

```text
C:\Users\Admin\Nutstore\1\Typora_save\自己的项目\6.14项目整理版.md
```

6. Long-term project context and milestone log:

```text
C:\Users\Admin\Nutstore\1\Typora_save\自己的项目\jetson orin nx project_AI上下文.md
```

Do not full-read this file by default. It is a long historical record. First read
its heading list, then only the sections required by the current task. For the
current Regular gate inclusion/color-fix work, the usual relevant sections are
M40, 操作与复现指南, and 下一步计划. Before editing the long-term context document,
read its "文档维护原则" section first and follow its permission rules.

7. Harness gate and Done Contract control plane:

```text
C:\Users\Admin\Desktop\orin nx project\docs\harness_engineering_v1.md
C:\Users\Admin\Desktop\orin nx project\docs\loop_engineering_v2.md
C:\Users\Admin\Desktop\orin nx project\docs\evaluation_system_v1.md
C:\Users\Admin\Desktop\orin nx project\configs\harness\gates.json
C:\Users\Admin\Desktop\orin nx project\configs\harness\loop_profiles.json
C:\Users\Admin\Desktop\orin nx project\configs\harness\evaluation_datasets.json
C:\Users\Admin\Desktop\orin nx project\configs\harness\metric_schema.json
C:\Users\Admin\Desktop\orin nx project\configs\harness\contracts\jetson_regular05_perf.json
```

Harness V1 is the runtime and evidence control plane. Loop Engineering V2 is the decision layer above it: choose a loop profile, freeze variables, name external observations, and stop/recover instead of blind retry. Evaluation System V1 is the lifecycle dataset and metric contract; use it before adding or changing quality metrics.

8. External knowledge-base routing, used only when a real blocker appears:

```text
C:\Users\Admin\Desktop\orin nx project\docs\knowledge_base\README.md
C:\Users\Admin\Desktop\orin nx project\docs\knowledge_base\routing.md
C:\Users\Admin\Desktop\orin nx project\docs\knowledge_base\harness_integration.md
```

Internal/company Typora references are routed through this local-only, Git-ignored index:

```text
C:\Users\Admin\Desktop\orin nx project\.local_knowledge\internal_reference_index.md
```

Do not copy internal original text, images, private links, or screenshots into public GitHub outputs.

Before running a new EIS experiment, check the Harness boundary first with:

```powershell
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py check-claim --gate-id nus_running_gate_v1 --claim main_gate_success_rate
```

Use the reference as strategic guidance, not as a rigid contract. It is already July, so prioritize demonstrable results over trying to finish every advanced idea.

## Project Purpose

The project is a Jetson Orin NX resume-oriented engineering project for autumn recruitment. The goal is not only to build a demo, but to produce a project that can be explained in interviews with clear engineering depth:

- measurable baseline;
- bottleneck analysis;
- targeted optimization;
- before/after numbers;
- clear trade-offs;
- reproducible artifacts such as code, videos, plots, tables, logs, and commit history.

The intended direction is **real-time EIS video stabilization and heterogeneous vision acceleration on NVIDIA Jetson Orin NX**. Start from an OpenCV CPU baseline and a controllable custom EIS pipeline, then use NVIDIA VPI/CUDA/GStreamer/Nsight/tegrastats to optimize key modules.

## Main Paths

- Local project root:

```text
C:\Users\Admin\Desktop\orin nx project
```

- GitHub remote target:

```text
https://github.com/StrongObserver/orin-nx-project
```

- Strategic reference document:

```text
C:\Users\Admin\Nutstore\1\Typora_save\自己的项目\6.14项目整理版.md
```

- USB SSH access from the Windows laptop to Jetson Orin NX:

```text
ssh nvidia@192.168.55.1
```

Current SSH login note:

```text
Host: 192.168.55.1
User: nvidia
Password: ask the user or check the local private project notes; do not commit plaintext passwords to a public repository.
```

Security note: do not commit plaintext passwords, tokens, SSH keys, or machine-local secrets to the public GitHub repository.

Stable USB network setup, if SSH is unstable:

```text
Windows: keep UsbNcm Host Device as 192.168.55.100/24, no gateway/DNS
Windows: disable Remote NDIS Compatible Device
Jetson: use usb0 as 192.168.55.1/24
Jetson: keep rndis0 and l4tbr0 down
```

Detailed setup notes:

```text
Private local USB-SSH setup note listed in the long-term context
C:\Users\Admin\Nutstore\1\Typora_save\自己的项目\jetson orin nx project_AI上下文.md
```

- Current first shaky input video for CPU EIS baseline:

```text
C:\Users\Admin\Desktop\orin nx project\data\raw\ostrich_shaky.mp4
```

Source URL:

```text
https://s3.amazonaws.com/python-vidstab/ostrich.mp4
```

Do not commit raw videos by default. Record the source URL and keep raw data under `data/raw/` unless the user explicitly decides otherwise.

- Current preferred visual evidence and immediate quality-gate clips:

```text
C:\Users\Admin\Desktop\orin nx project\results\vidstab_baseline\ostrich_vidstab_compare.mp4
C:\Users\Admin\Desktop\orin nx project\results\estimate_scale_sweep_1080p\stabilized_opencv_cpu_est0p33.mp4
C:\Users\Admin\Desktop\orin nx project\results\estimate_scale_sweep_1080p\compare_est0p33_side_by_side.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\20260718_nus_regular_gate_v1_regular_gate05_regular_6_jetson_lp_rigid_strength080_dynzoom106_compare.mp4
```

`ostrich_vidstab_compare.mp4` is the current mature external stabilization evidence. The current accepted custom CPU baseline review clip is the `lp_rigid_strength080_dynzoom106` Regular05 video above; it is a practical stage baseline, not a claim that global-warp EIS solves all local/parallax cases. `compare_est0p33_side_by_side.mp4` was generated as a 1080p check clip, but the source is mostly smooth ocean footage and is **not a valid stabilization-quality dataset**; use it only for performance / no-regression sanity, not for proving EIS quality. Do not package the naive VPI CUDA full-pipeline integration as an acceleration result unless a same-input end-to-end speedup is actually measured.

Current Harness boundary: `nus_regular_gate_v1` is the main quality gate, `nus_running_gate_v1` is a challenge/failure-boundary gate, and `regular05_perf_gate` is only for same-input Jetson performance evidence. Windows `209901xx` harness self-test evidence is not project progress and must not be cited as Jetson performance.

## Environment Setup Policy

- Be careful when configuring Python/CUDA/OpenCV/VPI environments, especially on Jetson.
- Follow the **minimum-intrusion principle** for environment defects and conflicts: inspect first, change the smallest reversible thing that can unblock the task, and avoid broad environment rebuilds or system-wide changes unless explicitly required.
- Do not uninstall or overwrite existing system packages unless the user explicitly asks.
- First inspect what already exists, for example `python3 --version`, `python3 -m pip --version`, `python3 -c "import cv2; print(cv2.__version__)"`, `dpkg -l | grep -E 'opencv|vpi|cuda'`.
- Prefer a lightweight project virtual environment when Python packages are needed. Do not force Docker just for isolation unless there is a real conflict or the user asks.
- If using `sudo apt install`, keep it minimal and explain what is being installed.

## Project Direction

Target resume block, after data is measured:

> Jetson Orin NX real-time EIS video stabilization and heterogeneous vision acceleration. Build a controllable pipeline: feature/optical-flow tracking -> motion estimation -> trajectory smoothing -> warp/remap. Use OpenCV `videostab` only as CPU baseline and visual reference. Use VPI/CUDA/GStreamer hardware blocks to replace hot modules and report latency, FPS, power, and stabilization quality improvements.

Core technical line:

1. Establish a CPU baseline and output a before/after stabilization video.
2. Build a custom EIS pipeline with measurable module timings.
3. Create a VPI backend support table for key operators on this Jetson/JetPack version.
4. Replace at least one hot module, such as optical flow, remap, or perspective warp, with a faster hardware backend.
5. Add profiling-driven optimizations only after bottlenecks are measured.

## Priority Rules

When time or implementation choices conflict, follow this order:

1. **Demo closure first**: a video stabilization result with timing data is more important than a complex unfinished architecture.
2. **Resume value first**: prefer work that yields before/after numbers, visual comparison, or profiling evidence.
3. **Baseline before optimization**: do not claim acceleration without a reproducible CPU or simple baseline.
4. **One solid optimization beats many slogans**: at least one VPI/CUDA/GStreamer replacement with measured improvement is better than many half-finished features.
5. **Validation boundary before more coding**: before adding a new optimization, define what counts as good/bad on stabilization quality, crop/black-border behavior, and same-input latency/FPS.
6. **Defer non-core ideas**: rolling-shutter correction, gyro fusion, full zero-copy, multi-stream concurrency, and complex smoothing algorithms are advanced items unless the core path is already stable.

## Open-Source-First Problem Solving

When the project hits an algorithm, platform, performance, or engineering blocker, do **not** default to writing a fresh implementation from scratch. The default workflow is:

1. Define the current blocker precisely, such as poor stabilization quality, black borders, unstable motion estimation, VPI operator usage, GStreamer/NVMM data flow, or Jetson encoder setup.
2. Search for similar open-source projects, official samples, and mature implementations that solve the same or a highly similar problem.
3. Read the README or usage docs first to judge similarity: whether the input/output, algorithm stage, platform, or failure mode matches the current blocker.
4. If the project has a reasonable chance of solving the blocker, clone it locally and inspect source code at the main-loop and module level before deciding.
5. If source-level inspection confirms that it solves the problem, reuse, adapt, or rewrite from that implementation directly instead of forcing originality.

For this resume project, code originality is less important than visible effect, Jetson measurement, and interview explainability. It is acceptable to heavily reference or adapt mature implementations when doing so saves time and improves results. Avoid only the uncontrolled version of a "stitched" project: do not combine large black boxes that cannot be debugged or explained. Prefer a controllable integration where each borrowed component or idea has a clear purpose and can be explained in terms of the EIS pipeline.

Current reference roles:

- `vid.stab`: mature external stabilization baseline and two-stage detect/transform reference. Use it first when a stable traditional EIS result is needed.
- OpenCV `videostab`: reference for classic visual stabilization flow, motion estimation, and smoothing abstractions.
- CUVISTA: reference for stronger stabilization quality ideas such as trajectory smoothing, dynamic zoom, outlier rejection, background fill, CLI output, and profiling-style artifacts.
- NVIDIA VPI / Jetson multimedia / GStreamer samples: preferred references for hardware acceleration, VIC/CUDA/PVA/OFA backend usage, NVMM, NVDEC, and NVENC.
- Internal references, if accessible through the user/company network: use them
  only as private guidance for EIS metrics, pass/fail gates, scene matrices, and
  traditional stabilization design. Treat these as internal L2/L4 references: do
  not copy their content, private paths, screenshots, or links into public GitHub
  outputs, and verify access/permission before cloning or quoting details.

## Internal-AI Escalation Workflow

The user may have access to compliant company-internal AI and open technical assets. When public search and local attempts do not quickly unblock a real issue, ask the user to relay a focused prompt to the internal AI instead of spending too long guessing.

Use this only for material blockers, for example: stabilization quality remains poor after several attempts, VPI/GStreamer/NVMM usage is unclear, Jetson multimedia samples are hard to adapt, or a comparable internal project/document may exist.

Workflow:

1. State the blocker in one sentence.
2. Provide a copy-paste prompt for the user to send to the internal AI.
3. Ask for specific return artifacts: document links, repo paths, sample names, key commands, API usage, known pitfalls, and minimal reproducible snippets.
4. After the user pastes the answer back, inspect only the relevant material and adapt the useful parts into this project.

Known access caveat: this local agent environment may not be able to clone
company-internal repositories directly. If code-level inspection is needed, ask
the user/internal AI for either access guidance or a focused export of the key
files: entry point, motion estimation, trajectory smoothing, warp/crop, metrics
scripts, README/build commands.

Prompt template:

```text
我在做 Jetson Orin NX 上的实时 EIS 视频稳像与异构加速项目，当前卡点是：【用一句话描述卡点】。

请优先搜索公司内部开放且合规可参考的技术文档、代码仓库、sample、历史项目或最佳实践，重点找：
1. 与 Jetson / NVIDIA VPI / CUDA / GStreamer / NVMM / NVDEC / NVENC / 视频稳像 / 光流 / warp / remap 相关的资料；
2. 能直接说明工程架构、关键 API、命令、性能数据、踩坑和适用边界的内容；
3. 可复用或可借鉴的最小代码路径，而不是只给概念介绍。

请按以下格式返回：
- 最相关的 3-5 个资料或仓库：名称 + 链接/路径 + 为什么相关；
- 每个资料中最值得看的文件/章节/函数；
- 可直接借鉴的命令、API 或代码片段；
- 已知坑点和不适合照搬的地方；
- 如果没有强相关资料，请明确说没有，并给出最接近的替代方向。
```

## Milestones

- M1 - Project skeleton and Git hygiene: repository initialized, remote documented, `.gitignore` correct, minimal runnable structure present.
- M2 - CPU baseline: OpenCV `videostab` or simple custom CPU pipeline produces stabilized output and module timing table.
- M3 - Custom controllable EIS pipeline: feature/flow, motion estimation, smoothing, and warp/remap are explicit and easy to modify.
- M4 - VPI backend validation: table of which operators run on CPU/CUDA/PVA/VIC/OFA on the actual device.
- M5 - First acceleration result: one hot module replaced by a measured faster backend with before/after latency and FPS.
- M6 - Presentation package: original/stabilized videos, benchmark table, profiling screenshot or logs, and concise explanation for interview use.

## Git Workflow

- Use Git from the beginning. If the repository is not initialized, initialize it in the project root and bind the remote above.
- Commit when a coherent stage is reached, not after every tiny edit.
- Good commit points:
  - initial project skeleton;
  - CPU baseline runs successfully;
  - custom EIS pipeline first works end-to-end;
  - timing/profiling instrumentation is added;
  - VPI backend validation table is produced;
  - a hardware-accelerated module shows measured improvement;
  - documentation or presentation artifacts are updated after a real result.
- Suggested commit message style:

```text
type(scope): concise imperative summary
```

Examples:

```text
chore(repo): initialize Jetson EIS project structure
feat(eis): add CPU stabilization baseline
perf(vpi): accelerate remap with CUDA backend
test(profile): record optical flow backend timings
docs(results): summarize first before-after stabilization demo
```

- Prefer `feat`, `fix`, `perf`, `test`, `docs`, `chore`, `refactor`.
- Push only when the user asks or when a stage is intentionally ready to sync to GitHub. Do not force-push, rewrite history, or change remote settings without explicit user instruction.
- Before pushing, inspect `git status`, confirm the commit contains only intended source/config/docs changes, and confirm large videos, raw data, virtual environments, build outputs, and secrets are excluded.
- Push with normal `git push origin <branch>`. Do not use `--force` or `--force-with-lease` unless the user explicitly requests it and the target branch is not `main`/`master`.
- After pushing, report the branch, remote, commit hash, and whether the working tree is clean. If push fails, report the exact failure and do not hide it behind a generic success message.
- Before committing, review `git status` and avoid accidentally committing local junk.

## Do Not Commit

Do not commit large or machine-local artifacts unless the user explicitly decides otherwise:

- build outputs;
- raw datasets and long videos;
- generated stabilized videos if too large for Git;
- profiler cache files;
- model weights or large binaries;
- local virtual environments;
- IDE/user settings;
- credentials, tokens, SSH keys, `.env` files;
- Jetson-specific temporary logs unless trimmed and intentionally used as evidence.

Use small representative samples, links, or documented paths for large artifacts.

## Evidence and Results

This project should continuously collect evidence useful for resume and interview discussion:

- before/after stabilization video or GIF;
- timing table by module;
- FPS and latency under fixed input resolution;
- power/perf data from `tegrastats` and `nvpmodel` when available;
- backend support table for VPI operators;
- Nsight Systems screenshots or exported summaries;
- notes explaining why an optimization helped, what it cost, and when it would not help.

Follow a **minimal-but-critical evidence policy**: do not preserve large numbers of screenshots or videos for every experiment. By default, keep concise text records, commands, parameters, metrics, selected output paths, and conclusions in the long-term context document. Keep only the smallest set of visual artifacts that are necessary to prove a milestone.

When a milestone truly needs visual evidence, the agent must explicitly remind the user and give concrete capture/storage instructions. Typical cases:

- Stabilization quality: keep one selected side-by-side comparison video, not every parameter trial. Generate it with `src/make_comparison.py` and store it under `results/evidence/<YYYYMMDD>_<milestone>/` or copy the final chosen clip to a Nutstore project assets folder if it must survive local cleanup.
- Runtime/profiling proof: keep one screenshot or exported summary from `tegrastats`, Nsight Systems, or terminal benchmark output. Store it under `results/evidence/<YYYYMMDD>_<milestone>/` and record the exact command and file path in the long-term context.
- Demo/presentation proof: if a video is needed for the final portfolio, remind the user to record a short 10-20 second clip showing original vs stabilized or CPU vs accelerated output, then record its path in the long-term context.

For user review, always copy generated visual evidence such as side-by-side videos, contact sheets, and short demo clips to `C:\Users\Admin\Videos\orin nx` in addition to keeping the reproducible copy under `results/`. New review copies must use the categorized tree `C:\Users\Admin\Videos\orin nx\review\<category>\<YYYYMMDD>_<loop_or_gate>\` and filenames shaped as `<YYYYMMDD>_<gate_id>_<clip_stem>_<platform>_<config_slug>_<asset_kind>.mp4`; do not put new bare duplicate-looking names directly under the review root. Do not leave reviewable evidence only in JSON/CSV or only on Jetson.

Do not commit these visual artifacts by default. `results/` is local evidence storage and is ignored by Git unless the user explicitly chooses a small representative artifact for version control.

## Safety Gate

- Low-risk read-only checks and routine local edits may proceed without asking.
- Be careful with commands that affect hardware state, system packages, JetPack/CUDA/VPI installations, power modes, cameras, long-running jobs, or remote repositories.
- Do not run destructive cleanup, force push, history rewrite, broad deletion, or system/global environment changes unless the user explicitly asks and the target is clear.
- Prefer scoped, reversible commands. When an action may affect the user's current environment or hardware, explain the risk first.

## Agent Behavior

- Keep the main direction stable: Jetson Orin NX + EIS/video stabilization + heterogeneous acceleration + measurable engineering optimization.
- Do not expand the project just to use more technologies.
- Do not optimize before measuring.
- Do not treat OpenCV `videostab` as code to deeply modify unless there is a strong reason; prefer building a controllable pipeline around mature OpenCV/VPI primitives.
- Ask the user for internal-AI help when a real blocker is likely to have company-internal references; provide a precise prompt instead of asking vague questions.
- When planning the next step, avoid presenting many routes by default. In normal cases, choose and communicate the single best, most feasible, and most useful next action for the current project state. Only present multiple options when the project is at a real functional fork that affects the overall direction and requires the user's decision.
- For long-term notes, use the Jetson Orin NX context document listed in this file. If a requested context path appears to belong to another independent project, stop and point out the mismatch before writing.
- Always distinguish measured data from placeholders. Never invent FPS, latency, power, or quality numbers.
- When reporting progress, state what was done, how it was verified, what evidence was produced, and the next most valuable step.
