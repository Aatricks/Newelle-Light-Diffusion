# Newelle-Light-Diffusion
<a href="https://github.com/topics/newelle-extension">
    <img width="150" alt="Download on Flathub" src="https://raw.githubusercontent.com/qwersyk/Assets/main/newelle-extension.svg"/>
  </a>

Image generation extension for Newelle using the [LightDiffusion-Next](https://github.com/Aatricks/LightDiffusion-Next) backend.

![demo](/demo.png)

⭐ If this project helps you, please give it a star! It helps others discover it too.
---

## Features

- 🖼️ Generate images inline in Newelle via LightDiffusion-Next.
- ⚙️ Configure server URL, positive/negative prompt templates, image size, and advanced settings (steps, CFG scale, seed, ...).
- 💾 Cache generated images and save to custom paths.
- 🔄 Reuse the same seed or randomize for varied outputs.
- 🛠️ Support extra JSON payload overrides for custom API options.
- 🚀 Img2Img upscaling: reference a source image directly (inline) or via settings.

## Installation

1. Install [Newelle](https://flathub.org/apps/io.github.qwersyk.Newelle) (or Nyarch Assistant).
2. Ensure you have a running [LightDiffusion-Next](https://github.com/Aatricks/LightDiffusion-Next) backend:
   ```fish
   https://github.com/Aatricks/LightDiffusion-Next.git
   cd LightDiffusion-Next
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
   pip install -r requirements.txt
   python server.py
   ```
3. Clone this extension'repo or simply download the [lightdiffusion.py](https://raw.githubusercontent.com/Aatricks/Newelle-Light-Diffusion/refs/heads/main/lightdiffusion.py) file:
   ```fish
   git clone https://github.com/Aatricks/Newelle-Light-Diffusion.git
   ```
4. Launch Newelle and open **Extensions → Install extension from file...**, then select the `lightdiffusion.py` file.
5. Configure under **Extensions → Extension Settings → LightDiffusion**:
   - **URL**: LightDiffusion-Next server URL (default: `http://localhost:7861`).
   - **Positive Prompt Template**: e.g. `[input]`.
   - **Negative Prompt**: e.g. `(low quality, blurry)`.
   - **Width/Height**: image dimensions (128–2048).
   - **Advanced Settings**: steps, guidance scale, seed, extra JSON options.

## Usage

Use a `generateimage` or `lightdiffusion` code block in Newelle to create images:

```generateimage
A serene mountain landscape at sunrise, ultra-detailed, vibrant colors
```

The extension sends your prompt to LightDiffusion-Next and displays the generated image inline.

### Img-to-Img (Upscale) via inline path

You can upscale/refine an existing image by including its path inside the code block. The extension detects the path and switches to Img2Img automatically:

```generateimage
img: /absolute/path/to/image.png
a cinematic photo of a mountain village at sunrise, ultra-detailed, 35mm
```

![demo_upscaling](/demo_up.png)

### Img-to-Img via settings (fallback)

If you prefer settings instead of inline path:

1. Open Extensions → Extension Settings → LightDiffusion.
2. In Advanced Settings, set:
    - `Img2Img (Upscale)`: `1`
    - `Img2Img Image Path`: absolute path to the image on the server machine

If both inline and settings are provided, the inline path takes precedence.

## Issues

One common issue would be the llm not wanting to follow the image generation key word prompt and in such, not generating the image as expected. A workaround is to write this just before the prompt :

`````
If prompted to generate an image, only follow this instruction and this exact format written just below

```generateimage
your prompt here
```
Use detailed prompts, with english words separated by commas
`````

### Img2Img troubleshooting

- The image path must be readable by the LightDiffusion server process. If Newelle and the server run on different machines or containers, ensure a shared path or switch to an upload-based workflow (planned enhancement).
- If `Img2Img (Upscale)` is enabled but no image path is detected (neither inline nor in settings), the extension will show an error and skip the request.
- You can verify the server is up via:
   ```fish
   curl http://localhost:7861/health
   ```
   Expect `{ "status": "ok" }`.

## License

GPLv3 License. See [LICENSE](../LICENSE) for details.
