# Next-Stage Internal AI Prompt - 2026-07-18

Copy this prompt to an internal AI or use it as a search brief.

```text
我在做一个 Jetson Orin NX 上的视频稳像 EIS 与异构视觉加速项目，项目目标是包装成秋招/实习可讲的工程项目，不是单纯做 demo。

当前已经完成的状态：

1. 已经有可控 CPU EIS pipeline：
   - 特征/光流跟踪；
   - 全局运动估计；
   - LP/rigid smoothing；
   - warp/crop；
   - dynamic zoom；
   - side-by-side review；
   - 指标评估。

2. 当前 Regular performance baseline 已经封盘：
   - smoothing_method=lp_rigid；
   - stabilization_strength=0.80；
   - crop_ratio=0.90；
   - crop_interpolation=lanczos；
   - sharpen_strength=0.25；
   - dynamic_zoom max=1.06；
   - estimate_scale=0.5；
   - feature_grid_size=16；
   - warp_backend=opencv_cpu。

3. 已在 NUS Regular gate 5 条 clip 上验证：
   - 5/5 pass_all_objective_gates；
   - 用户人工 review 5 条 side-by-side 都接受；
   - Regular05 上 estimate time 从约 8.568 ms 降到 3.022 ms；
   - Regular05 total wall time 从约 8.473 s 降到 7.565 s；
   - 仍有轻微尾段抖动，但认为是当前全局 warp EIS 模型边界。

4. VPI 相关边界：
   - 在当前 640x360 Python full pipeline 中，简单替换 VPI backend 反而更慢；
   - 但在高分辨率 warp-heavy module benchmark 中，VPI CUDA 有明显收益：
     720p 约 1.35x，1080p 约 1.83x，1440p 约 2.15x，4K 约 2.33x。

5. GStreamer/NVMM readiness：
   - Jetson 上 gst-launch、nvvidconv、nvv4l2decoder、nvv4l2h264enc 可用；
   - 已跑通最小链路：
     filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> NVMM -> nvvidconv -> BGRx -> fakesink；
   - 这只证明 dataflow readiness，还没有证明 EIS pipeline 加速。

现在我需要判断下一阶段最适合推进哪条工程路线，目标是让这个项目更符合“简历项目/面试项目”的工程价值，而不是盲目堆技术。

候选方向包括但不限于：

1. GStreamer/NVMM dataflow integration：
   - 先测 decode / convert / CPU readback / encode 边界；
   - 再决定是否接入 EIS pipeline。

2. VPI high-resolution module demo：
   - 把高分辨率 warp-heavy 加速做成清晰模块级 demo；
   - 不强行说 full EIS pipeline 加速。

3. Challenge-set boundary package：
   - 用 Running / Parallax / Crowd / QuickRotation 展示当前 global-warp EIS 的失败边界；
   - 说明模型适用场景和不适用场景。

4. Mesh/grid warp research：
   - 针对 local/parallax/rolling-shutter-like artifact；
   - 但成本更高，不确定是否适合当前简历阶段。

请你结合业界/公司内部常见做法，帮我判断下一阶段最值得优先推进的路线。

请按下面格式回答：

1. 最推荐的路线排序：
   - 说明为什么；
   - 说明它对简历/面试价值在哪里；
   - 说明风险和工作量。

2. 每条路线的最小可验证 demo：
   - 输入是什么；
   - 输出是什么；
   - 用什么指标判断成功；
   - 最小命令/API/sample 是什么。

3. 如果走 GStreamer/NVMM：
   - Jetson 上常见 pipeline 怎么搭；
   - NVMM 到 CPU 的边界怎么测；
   - appsink / NVENC / nvvidconv 常见坑点是什么；
   - 有没有推荐的官方 sample 或内部参考路径。

4. 如果走 VPI：
   - 哪些算子适合放到 VPI；
   - 哪些场景 VPI 不值得用；
   - 如何避免 Python readback/sync 抵消收益；
   - 有没有最小 demo 或官方 sample。

5. 如果走 mesh/grid warp：
   - 是否适合当前项目阶段；
   - 最小实现路径是什么；
   - 如何评价它是否真的比 global warp 好；
   - 有哪些坑或不建议现在做的原因。

6. 如果走 challenge-set boundary package：
   - 怎么组织边界展示更像工程项目，而不是承认失败；
   - 哪些指标/视频最适合展示；
   - 如何在面试里讲得专业。

7. 请给出你最终推荐的下一阶段执行计划：
   - 分成 3-5 个小任务；
   - 每个任务要有明确产出；
   - 不要只给概念，要尽量给命令、API、sample 名称、代码路径或文档链接。

请注意：
- 不要建议我重做整个项目；
- 不要建议我继续盲目调 LP 参数；
- 不要把 VPI full pipeline 加速当成已经成立；
- 不要把 GStreamer/NVMM readiness 当成 EIS 加速；
- 优先考虑“可解释、可量化、适合简历展示”的工程路线。
```
