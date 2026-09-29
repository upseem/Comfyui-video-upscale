# Comfyui-video-upscale

独立的视频高清 / 超分节点与工作流库，首个后端为 SeedVR2。

## 职责分离

- **本仓库**：超分连续帧批处理适配、模型工作流、GPU 参数与高清效果验证。
- **[ComfyUI_video_loop](https://github.com/upseem/ComfyUI_video_loop)**：通用视频抽帧、循环磁盘读写、视频合成。使用原版 main，无需合并之前的高清 PR。
- **[ComfyUI-SeedVR2_VideoUpscaler](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler)**：模型加载与推理。

不重复打包 ComfyUI、SeedVR2 模型或 loop 库源码。

## 安装

在现有 ComfyUI 环境里安装这三个 custom_nodes 仓库及各自 requirements（已安装的依赖不要重复克隆）。本库当前为私有库，访问需要 GitHub 授权。

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/upseem/Comfyui-video-upscale.git
git clone https://github.com/upseem/ComfyUI_video_loop.git
git clone https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git
/path/to/comfy-python -m pip install -r Comfyui-video-upscale/requirements.txt
/path/to/comfy-python -m pip install -r ComfyUI_video_loop/requirements.txt
/path/to/comfy-python -m pip install -r ComfyUI-SeedVR2_VideoUpscaler/requirements.txt
```

需要 FFmpeg/FFprobe、支持 V3 API 与原生 StartLoop/EndLoop 的 ComfyUI。重启后，本库三个节点位于 `Video Upscale/Batch`。

## 节点

- `VideoUpscaleBatchPlan`：计算块数、上下文配置。
- `VideoUpscaleReadBatch`：通过 loop 库的磁盘 job 读取连续帧与两侧上下文。
- `VideoUpscaleWriteBatch`：检查输出帧数，裁掉上下文，通过 loop 原有 writer 原子写回。

通过运行时节点注册表解析 loop 库，无需依赖插件文件夹的 Python 包名或加载顺序。当前适配其内部 disk API，升级后需要重新做兼容验证。

## 工作流

- [短片 1080p 质量基准](example_workflows/SeedVR2_5090_short_clip_1080p.json)：整段载入内存，只选择 5–10 秒短片。此工作流本身不需要 loop 库。
- [磁盘连续帧 1080p 循环](example_workflows/SeedVR2_5090_disk_batch_1080p.json)：默认先处理前 10 秒；确认后可将 duration 改为 0。

导入后重新选择实际输入文件，默认占位名是 `input.mp4`。建议长片运行使用 `--cache-none`，同时监测主存/显存。

## 验证状态

已进行 CPU 分块/FFmpeg 测试、依赖解析单元测试、Python 编译和工作流链接静态检查。**尚未验证 ComfyUI 前端导入和 5090 GPU 推理**。

初始建议：3B FP16、1080p、内部 17 帧、内部 overlap=4，外层每块保留 49 帧并带左右各 8 帧上下文。不是显存或吞吐承诺。

上下文裁切不保证跨调用无缝；VFR 转 CFR，当前磁盘链路为 8-bit SDR；不支持完整推理断点续跑。详见 [方案与已知限制](docs/SeedVR2_5090.zh-CN.md)。

```bash
python3 -m pytest -q tests
```
