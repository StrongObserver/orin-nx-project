# CUDA Affine MMAPI Diagnostic - 2026-07-24

## Decision

The custom CUDA affine MMAPI diagnostic is blocked at the non-identity stage and
is closed as negative evidence for the current EGL-mapped NV12_ER scratch route.

What passed:

```text
identity CUDA kernel path:
  rc=0
  readable 640x360 output
  black-border p95 = 0
  source-vs-identity mean_abs_center_avg = 2.772184
```

What failed:

```text
translate / affine / random-sampling CUDA kernels over the current EGL-mapped
pitch-linear NV12_ER scratch repeatedly produced severe tearing or unrelated
visual corruption, despite rc=0.
```

Boundary:

```text
This is negative device-stage CUDA affine integration evidence. It is not an
accepted CUDA warp path, not an acceleration result, not zero-copy, and not EIS
quality improvement.
```

## Scope

Tracked patch script:

```text
scripts/patch_mmapi_cuda_affine_diagnostic.py
```

Active contract:

```text
configs/harness/contracts/cuda_affine_mmapi_diagnostic_v1.json
```

Input:

```text
/home/nvidia/orin-nx-project/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
```

## Attempts

| Attempt | Result | Decision |
|---|---|---|
| identity CUDA kernel | rc=0, readable output | pass |
| translate affine kernel, direct EGL output write | rc=0, visible tearing/corruption | reject |
| temporary `cudaMallocPitch` input/output buffers plus copy-back | rc=0, still visible tearing/corruption | reject |
| matrix passed as kernel arguments instead of constant memory | no visual fix | reject |
| `translate_y_copy_uv` | Y-only warp still tears | reject |
| integer `translate_direct` kernel | still tears | reject |
| `cuCtxSynchronize` after map and before unregister | still tears | reject |
| `NvBufSurfaceSyncForDevice` on CUDA output scratch | segmentation fault | reject |

The first valid safety result remains the previous interop verifier:

```text
identity + marker + dynamic_marker writes are safe.
Large plane shift/random sampling is not safe in this current route.
```

## Interpretation

The current evidence says:

```text
CUDA can touch this scratch surface safely for full-frame copy and small ROI
marker writes.
```

It does not say:

```text
CUDA can safely run arbitrary affine/random-sampling warp over the EGL-mapped
pitch-linear NV12_ER scratch and then feed the result back through
NvBufSurfTransform/NVENC.
```

The most likely boundary is memory-layout/cache/surface ownership around
EGL-mapped NvBufSurface scratch buffers under random access. Official Jetson
samples show simple CUDA ROI writes on EGLImage buffers, but this loop did not
find a public in-repo sample proving full-frame random-sampling warp on the same
MMAPI transcode scratch boundary.

## Interview Value

This is still useful evidence:

```text
I did not stop at standalone CUDA timing. I tried to integrate CUDA into the
MMAPI/NVENC device path, found that identity and small marker writes were safe,
then proved that naive affine/random-sampling writes over the current EGL-mapped
NV12_ER scratch path tear. That changed the engineering decision from "CUDA is
faster standalone" to "CUDA needs a different surface ownership or official
interop route before it is a valid device-stage warp path."
```

This is a stronger claim than pretending the route worked.

## Next Route

Do not keep patching the same route blindly. A future route needs one of:

```text
1. Official Jetson Multimedia API CUDA processing pattern for full-frame
   random-sampling warp before encode.
2. A CUDA-owned intermediate surface with a documented transform back into
   encoder-compatible NvBufSurface.
3. Internal/company guidance for NvBufSurface/EGLImage/CUDA cache and sync rules
   under random write workloads.
```

## Internal-AI Prompt

```text
我在做 Jetson Orin NX 异构视频计算与设备侧数据流优化项目，EIS 是代表性实时视觉负载。当前卡点是：我已经验证 CUDA 可以通过 EGLImage interop 对 MMAPI 的 pitch-linear NV12_ER scratch 做 identity copy 和小 ROI marker 写入，但一旦做 full-frame translate / affine / random-sampling CUDA kernel，输出送回 NvBufSurfTransform/NVENC 后会出现严重 tearing / block corruption；即使使用临时 cudaMallocPitch buffer、kernel argument matrix、Y-only warp、integer translate、cuCtxSynchronize、NvBufSurfaceSyncForDevice 等尝试也没有解决，其中 NvBufSurfaceSyncForDevice(output_scratch) 还会 segfault。

项目当前边界：
- 输入是 Regular05 640x360 H264；
- 主链是 MMAPI/NVDEC block-linear NV12 -> NvBufSurfTransform -> pitch-linear NV12_ER scratch -> CUDA/EGLImage interop -> NvBufSurfTransform 回 block-linear NV12 -> NVENC；
- identity copy 和 small marker 写入可读；
- full-frame random-sampling warp 会撕裂；
- 不能把这个结果包装成 zero-copy 或 full real-time EIS。

请优先搜索公司内部开放且合规可参考的 Jetson / NVIDIA Multimedia API / NvBufSurface / EGLImage / CUDA interop / NVENC / VPI 相关资料，重点回答：
1. 在 Jetson MMAPI/NvBufSurface 场景下，CUDA kernel 对 EGL-mapped pitch-linear NV12/NV12_ER surface 做 full-frame random read/write 后，正确的 cache sync / map / unmap / ownership 规则是什么？
2. 是否有官方或内部 sample 展示 CUDA 对 NvBufSurface/EGLImage 做 full-frame warp/resize/remap 后再送 NVENC，而不只是画 ROI label？
3. 如果 EGL-mapped NvBufSurface 不适合 random-sampling warp，推荐的工程路径是什么？例如 CUDA-owned surface -> NvBufSurfTransform 回 encoder surface、NvBuffer APIs、EGLStream、VPI wrapper、或者 GStreamer NVMM 插件。
4. 需要避免哪些已知坑：pitch padding、plane layout、UV order、cache sync、resource unregister、block-linear/pitch-linear、NV12_ER full-range、encoder input layout 等？
5. 请给出最小可复现代码路径或关键 API 顺序，而不是概念解释。

请按以下格式返回：
- 最相关的 3-5 个资料/仓库/sample：名称 + 路径/链接 + 为什么相关；
- 每个资料中最值得看的文件/函数；
- 推荐的最小 API 调用顺序；
- 已知坑点和不适合照搬的地方；
- 如果没有强相关资料，请明确说没有，并给出最接近的替代方向。
```
