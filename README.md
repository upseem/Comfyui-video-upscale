# Comfyui-video-upscale

独立的视频高清 / 超分节点与工作流库，首个后端为 SeedVR2。

## 职责分离

- **本仓库**：超分连续帧批处理适配、模型工作流、GPU 参数与高清效果验证。
- **[ComfyUI_video_loop](https://github.com/upseem/ComfyUI_video_loop)**：通用视频抽帧、循环磁盘读写、视频合成。使用原版 main，无需合并之前的高清 PR。
- **ComfyUI 原生 SeedVR2 节点**：主工作流的模型加载、VAE、时间 latent 分块与推理。
- **[ComfyUI-SeedVR2_VideoUpscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)**：仅供旧实验工作流使用，不是原生磁盘分块工作流的依赖。

不重复打包 ComfyUI、SeedVR2 模型或 loop 库源码。

## 安装

在支持原生 SeedVR2、V3 API 和 StartLoop/EndLoop 的当前 ComfyUI 中安装本仓库及 loop 仓库（已安装的依赖不要重复克隆）。

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/upseem/Comfyui-video-upscale.git
git clone https://github.com/upseem/ComfyUI_video_loop.git
/path/to/comfy-python -m pip install -r Comfyui-video-upscale/requirements.txt
/path/to/comfy-python -m pip install -r ComfyUI_video_loop/requirements.txt
```

原生工作流需要：

```text
ComfyUI/models/diffusion_models/seedvr2_3b_int8_convrot.safetensors
ComfyUI/models/vae/seedvr2_ema_vae_fp16.safetensors
```

需要 FFmpeg/FFprobe、支持 V3 API 与原生 StartLoop/EndLoop 的 ComfyUI。重启后，本库三个节点位于 `Video Upscale/Batch`。

## 节点

- `VideoUpscaleBatchPlan`：计算块数、上下文配置。
- `VideoUpscaleReadBatch`：通过 loop 库的磁盘 job 读取连续帧与两侧上下文。
- `VideoUpscaleWriteBatch`：检查输出帧数，裁掉上下文，通过 loop 原有 writer 原子写回。

通过运行时节点注册表解析 loop 库，无需依赖插件文件夹的 Python 包名或加载顺序。当前适配其内部 disk API，升级后需要重新做兼容验证。

## 工作流

- **[官方原生 SeedVR2 3B Int8 全视频磁盘分块](example_workflows/SeedVR2_3B_Int8_Video_Upscale_5090.json)**：主工作流。先在 Resize/VAE 之前按 49 帧落盘分块，左右各读 8 帧上下文；每个外层块内部继续使用官方自动 latent 分块和 overlap=2，最后裁掉外层上下文并接回原音频。默认处理完整时长。
- [短片第三方插件质量基准](example_workflows/SeedVR2_5090_short_clip_1080p.json)：旧实验，仅加载很短片段，需要 numz 插件及其 FP16 模型。
- [第三方插件磁盘循环](example_workflows/SeedVR2_5090_disk_batch_1080p.json)：旧实验，不要与官方原生权重混用。

导入后重新选择实际输入文件，默认占位名是 `input.mp4`。长片建议用 `--cache-none`，同时监测主存、显存和磁盘。外层 chunk 可在 5090 验证后由 49 调大；不要把“latent 自动分块”误认为会在 Resize/VAE 前拆分整段视频。

## 验证状态

已进行 CPU 分块/FFmpeg 测试、依赖解析单元测试、Python 编译和工作流链接静态检查。官方整段模板的 2 秒、60 帧、2160×3840 输出已在 5090 完成；新原生磁盘循环工作流仍需 GPU 端到端验证，不能仅凭静态检查宣称完成。

主工作流初始值：3B Int8、2×、LAB、官方内部自动 latent chunk + overlap=2，外层每块保留 49 帧并带左右各 8 帧上下文。不是吞吐或无接缝承诺。

上下文裁切不保证跨调用无缝；VFR 转 CFR，当前磁盘链路为 8-bit SDR；不支持完整推理断点续跑。详见 [方案与已知限制](docs/SeedVR2_5090.zh-CN.md)。

```bash
python3 -m pytest -q tests
```
