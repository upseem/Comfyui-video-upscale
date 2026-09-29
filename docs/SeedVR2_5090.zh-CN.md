# RTX 5090 / ComfyUI 视频超分方案

## 当前交付状态

已拉取源码、生成两个 UI 工作流、在独立高清库新增批处理节点，原 loop 库不改动。
只完成源码/JSON 静态检查、CPU 分块算法与 FFmpeg 冒烟测试；尚未启动 ComfyUI、验证前端导入、下载模型或进行 GPU 推理。不能据此宣称显存足够、高清效果合格或无接缝。
未修改现有远端 GPU 机器。

## 源码版本

- ComfyUI: `d669bcfeb15c0e42e33bc0ba551438df50860112`
- upseem/ComfyUI_video_loop 基线: `abf464b048e0cf33d94ae2d0acabaecd81c3166e`
- numz/ComfyUI-SeedVR2_VideoUpscaler: `4490bd1f482e026674543386bb2a4d176da245b9`

## 结论

视频解码为帧并不等于逐帧独立推理。SeedVR2 应接连续帧 IMAGE batch。
原 VideoLoopReadFrame / WriteFrame 每次只有一帧，适合图像超分，不适合发挥 SeedVR2 时间建模优势。
loop 库保留原四节点，本库注册 VideoUpscaleBatchPlan / VideoUpscaleReadBatch / VideoUpscaleWriteBatch 三节点。

### 工作流 1：短片效果基准

`example_workflows/SeedVR2_5090_short_clip_1080p.json`

LoadVideo → GetVideoComponents → SeedVR2VideoUpscaler → CreateVideo → SaveVideo。
原音频和帧率接回 CreateVideo。仅加载手工准备的 5–10 秒短片；这个工作流没有自动截短，整段图片和输出可能驻留内存。不用于长视频。
该工作流只依赖 ComfyUI 和 SeedVR2 插件，不依赖新增循环节点，作为质量对照。

### 工作流 2：磁盘连续帧分块循环

`example_workflows/SeedVR2_5090_disk_batch_1080p.json`

Prepare → BatchPlan → StartLoop → ReadBatch → SeedVR2 → WriteBatch → EndLoop → Assemble。

- Prepare 默认只取前 10 秒，processing_fps=0；确认通过后 duration 改为 0 处理全片。
- BatchPlan 每块写回 49 帧，左右各读最多 8 帧上下文。
- 一块最多读取 65 帧；SeedVR2 内部 batch_size=17，temporal_overlap=4。
- WriteBatch 校验 job、计划和输出帧数，丢弃两侧上下文，仅写本块所属帧。没有重复或遗漏索引。
- 注意两个层级：SeedVR2 overlap 是同一次调用内部的融合；外层 chunk 的上下文是重算并裁掉，不是跨调用融合，也不是隐藏状态传递。仍需检查第 49/98/... 帧附近的画面跳变。
- EndLoop accumulate=false，只传字符串回执，不累积 IMAGE。
- Assemble 使用原模块，默认 AAC 音频、H.264 CRF18，保留磁盘帧以便排查。

## 初始参数（未实测，不是性能承诺）

| 参数 | 初始值 |
| --- | --- |
| DiT | seedvr2_ema_3b_fp16.safetensors |
| VAE | ema_vae_fp16.safetensors |
| resolution | 1080，指短边，不是宽度 |
| max_resolution | 1920，长边限制；非 16:9 素材可能短边低于 1080 |
| batch_size | 17，遵守 4n+1 |
| temporal_overlap | 4 |
| uniform_batch_size | true |
| seed | 42，固定；不保证不同块输出完全一致 |
| color_correction | lab |
| input / latent noise | 0 / 0 |
| VAE encode / decode tile | 512 / 512，overlap 64 |
| offload_device | cpu |
| DiT blocks_to_swap | 16，显存有余量后可减少 |
| model cache | true，用于跨块复用权重 |
| attention | sdpa，先不用额外编译的注意力扩展 |
| torch.compile | 未连接，先保证跑通 |

4K 后续测试：resolution=2160，max_resolution=3840；从 batch_size=5 或 9 开始，根据显存和质量调整，不直接沿用 1080p 吞吐假设。外层 chunk_size 可缩小以降低 CPU RAM 压力，但接缝更频繁。

## 部署到现有 5090 机器时

1. 先检查 ComfyUI 版本、原生 StartLoop/EndLoop 支持、Python/PyTorch/CUDA、GPU 空闲显存、系统 RAM 和磁盘空间。不要直接覆盖已有 ComfyUI。
2. 部署本库到 `ComfyUI/custom_nodes/Comfyui-video-upscale`，另安装原版 ComfyUI_video_loop 与 SeedVR2 插件；无需使用之前 loop 库的高清分支。
3. 用运行 ComfyUI 的同一 Python 环境安装三个插件 requirements。先核对版本冲突，不在未知环境盲目升级 PyTorch。
4. 模型目录：`ComfyUI/models/SEEDVR2/`。所需两个 safetensors 如上。插件支持首次使用自动下载；正式执行前确认网络和磁盘，避免推理时意外等待大文件。
5. 首轮不启用 SageAttention、FlashAttention、torch.compile；减少 5090 环境排错变量。
6. 长片循环建议以 `--cache-none` 启动 ComfyUI，限制执行图缓存驻留；它不等于清空 SeedVR2 自身的权重缓存。仍应实测 GPU/CPU 内存是否跨轮增长。
7. 将测试片放入 input，导入 JSON 后在 Prepare / LoadVideo 重新选择实际文件；占位文件名是 input.mp4。
8. 先短片基准，再磁盘循环同片对比，再 4K，最后长视频。

## 明确限制与后续优化

- 输入最好是单镜头 SDR CFR。当前没有自动镜头检测；不要把不同镜头的帧放在同一上下文中。多镜头先按镜头分割处理。
- 原插件 `processing_fps=0` 实际使用 avg_frame_rate + FFmpeg fps 滤镜，VFR 会被转换为 CFR；不是原始 PTS 保真。严格 VFR 保留需要扩展 timestamp manifest 与编码链路。
- PNG / 当前输出链路是 RGB 8-bit + yuv420p SDR，没有 HDR/10-bit 色彩管理承诺。
- Prepare 会全片抽帧，因此内存不随全片帧数直接增长，但磁盘仍可能很大；4K PNG 每分钟可能占用数 GB 甚至更多，必须测样本估算。
- 原生循环会展开迭代图，非常长的视频还会增加图元数据。超长任务建议后续改为 API 逐块排队/分镜头任务。
- 当前 skip_valid 在推理之后跳过写盘，不会跳过 SeedVR2 计算；不是完整计算断点续跑。重跑 Prepare 也可能生成新 job。可靠续跑需要固定 job + 参数/权重指纹 + 推理前完整性检查，未在本版宣称实现。
- 改模型或分辨率用新 job，避免混入旧结果；默认 overwrite。
- 原 Assemble 以存在性检查缺帧，并未完整验证所有 PNG 尺寸/内容；还有音轨偏移、短音轨触发 -shortest 等特殊输入风险。实测验收必须核对时长和音画同步。
- 上下文裁切不保证跨块无缝。若对照发现跳变，先按镜头加长块；必要时实现跨块重叠区落盘融合并增加顺序/原子性测试，不能仅把 overlap 参数当作保证。

## 验收

- 同片同尺寸比较短片整段输入与磁盘循环结果，连续播放检查脸、文字、手部、纹理、运动和块边界。
- 输入 CFR 的预期帧数与输出一致；无重复帧/漏帧，音画同步，输出尺寸符合预期。
- 记录推理耗时、峰值 GPU 显存、CPU RAM、每轮内存变化和磁盘占用。
- 不将“JSON 生成成功”当作“ComfyUI 工作流执行成功”。

## 本地验证命令

```bash
python3 -m pytest -q
python3 -m compileall -q src
git diff --check
```
