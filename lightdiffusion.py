"""
LightDiffusion Newelle Extension

This extension integrates Newelle with a running LightDiffusion backend server.
It's modeled after the Stable Diffusion WebUI extension and reuses
its ImageGeneratorWidget. (https://github.com/FrancescoCaracciolo/Newelle-Image-Generator)
"""

# TODO : add support for img2img mode

from __future__ import annotations

import base64
import json
import os
import traceback
from threading import Thread
import re
from typing import Any, Dict, Optional

import requests
from gi.repository import Gtk, Gdk, GdkPixbuf
from .ui import load_image_with_callback

from .handlers import ExtraSettings, PromptDescription
from .extensions import NewelleExtension


class LightDiffusionExtension(NewelleExtension):
    name = "LightDiffusion"
    id = "lightdiffusion"

    def __init__(self, pip_path: str, extension_path: str, settings: dict):
        super().__init__(pip_path, extension_path, settings)
        self.cache_dir = os.path.join(self.extension_path, "generated_images")
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_replace_codeblocks_langs(self) -> list:
        # Support either a generic tag or a specific one
        return ["generateimage", "lightdiffusion"]

    def get_additional_prompts(self) -> list:
        return [
            PromptDescription(
                "generate-image-lightdiffusion",
                "Generate Image",
                "Generate images using the LightDiffusion backend",
                (

                    "If prompted to generate an image, only follow this instruction and this exact format written just below"
                    "```generateimage\n"
                    "your prompt here\n"
                    "```\n"
                    "Use detailed prompts, with english words separated by commas\n"
                ),
            ),
        ]

    def get_extra_settings(self) -> list:
        # Mirror sdwebui-style settings for familiarity; most are optional.
        return [
            ExtraSettings.EntrySetting(
                "url",
                "URL",
                "URL of the LightDiffusion server",
                "http://localhost:7861",
            ),
            ExtraSettings.MultilineEntrySetting(
                "positive-prompt",
                "Positive Prompt Template",
                "Prompt template for positive prompt, [input] will be replaced with the AI input",
                "[input]",
            ),
            ExtraSettings.MultilineEntrySetting(
                "negative-prompt",
                "Negative Prompt",
                "Prompt template for negative prompt",
                "(worst quality, low quality:1.4), (zombie, sketch, interlocked fingers, comic), (embedding:badhandv4),",
            ),
            ExtraSettings.ScaleSetting(
                "width",
                "Width",
                "Width of the generated image",
                512,
                128,
                2048,
                0,
            ),
            ExtraSettings.ScaleSetting(
                "height",
                "Height",
                "Height of the generated image",
                512,
                128,
                2048,
                0,
            ),
            ExtraSettings.NestedSetting(
                "advanced_settings",
                "Advanced Settings",
                "Advanced settings like steps, guidance scale, seed...",
                [
                    # Core sampling controls
                    ExtraSettings.ScaleSetting(
                        "steps",
                        "Steps",
                        "Number of steps for the generation (if supported)",
                        20,
                        1,
                        150,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "guidance_scale",
                        "CFG Guidance Scale",
                        "Guidance scale for the generation (if supported)",
                        7,
                        1,
                        20,
                        0,
                    ),
                    ExtraSettings.EntrySetting(
                        "seed",
                        "Seed",
                        "Seed for the generation (-1 for random)",
                        "-1",
                    ),

                    # Feature toggles (0 = off, 1 = on)
                    ExtraSettings.ScaleSetting(
                        "hires_fix",
                        "Hires Fix",
                        "Enable high-resolution fix",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "adetailer",
                        "ADetailer",
                        "Enable automatic face/body enhancement",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "img2img_enabled",
                        "Img2Img (Upscale)",
                        "Enable Image-to-Image mode; the server reads the image from this path",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.EntrySetting(
                        "img2img_image",
                        "Img2Img Image Path",
                        "Absolute path to the source image on the server machine",
                        "",
                    ),
                    ExtraSettings.ScaleSetting(
                        "stable_fast",
                        "Stable-Fast",
                        "Compile/optimize for faster inference (first run compiles)",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "reuse_seed",
                        "Reuse Seed",
                        "Reuse the last/explicit seed for reproducibility",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "flux_enabled",
                        "Flux Mode",
                        "Enable Flux mode (quantized UNet + dual CLIP), requires at least 8GB VRAM with 32GB RAM",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "prio_speed",
                        "Prioritize Speed",
                        "Use a faster sampler at some quality cost",
                        0,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "realistic_model",
                        "Realistic Model",
                        "Switch to the realistic model checkpoint",
                        0,
                        0,
                        1,
                        0,
                    ),

                    # Multiscale diffusion controls
                    ExtraSettings.ScaleSetting(
                        "multiscale_enabled",
                        "Multiscale Enabled",
                        "Enable multi-scale diffusion for performance",
                        1,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "multiscale_intermittent",
                        "Intermittent Full-Res",
                        "Occasionally render full-res in low-res region",
                        1,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "multiscale_factor",
                        "Multiscale Factor",
                        "Scale factor for intermediate steps (0.10 - 1.00)",
                        0.5,
                        0.1,
                        1.0,
                        2,
                    ),
                    ExtraSettings.ScaleSetting(
                        "multiscale_fullres_start",
                        "Full-Res Start Steps",
                        "Number of first steps at full resolution",
                        3,
                        0,
                        30,
                        0,
                    ),
                    ExtraSettings.ScaleSetting(
                        "multiscale_fullres_end",
                        "Full-Res End Steps",
                        "Number of last steps at full resolution",
                        8,
                        0,
                        60,
                        0,
                    ),

                    # Misc
                    ExtraSettings.ScaleSetting(
                        "keep_models_loaded",
                        "Keep Models Loaded",
                        "Keep weights in memory between requests",
                        1,
                        0,
                        1,
                        0,
                    ),
                    ExtraSettings.MultilineEntrySetting(
                        "extra_payload",
                        "Extra Options",
                        "Manually specify extra options in JSON format. You can include 'endpoint_path' here to override the default '/api/generate'.",
                        "{}",
                    ),
                ],
            ),
        ]

    def restore_gtk_widget(self, codeblock: str, lang: str, msg_uuid: str) -> Gtk.Widget | None:
        widget = ImageGeneratorWidget(width=400, height=400)
        # Normalize the incoming block so we support both multi-line and one-liner formats
        normalized_prompt = self._extract_prompt_from_block(codeblock, lang)
        widget.set_prompt(normalized_prompt)
        cached_path = os.path.join(self.cache_dir, f"{msg_uuid}.png")
        if os.path.exists(cached_path):
            widget.set_image_from_path(cached_path)
        return widget

    def get_gtk_widget(self, codeblock: str, lang: str, msg_uuid: str = None) -> Gtk.Widget | None:
        widget = ImageGeneratorWidget(width=400, height=400)
        # Normalize the incoming block so we support both multi-line and one-liner formats
        normalized_prompt = self._extract_prompt_from_block(codeblock, lang)
        widget.set_prompt(normalized_prompt)
        Thread(target=self.generate_image, args=(normalized_prompt, widget, msg_uuid)).start()
        return widget

    # --- Generation logic ---
    def generate_image(self, prompt: str, widget: 'ImageGeneratorWidget', msg_uuid: Optional[str]):
        def show_error_message(msg: str):
            print(f"[LightDiffusionExtension] Error: {msg}")
            try:
                widget.show_loading(False)
            except Exception:
                pass

        try:
            # Read live settings via Newelle API (ensures UI changes are applied)
            base_url_raw = self.get_setting("url") or "http://localhost:7861"
            base_url: str = str(base_url_raw).rstrip("/")

            pos_tpl: str = self.get_setting("positive-prompt") or "[input]"
            neg_tpl: str = self.get_setting("negative-prompt") or ""

            # Width/height must reflect Newelle settings precisely
            try:
                width = int(self.get_setting("width"))
            except Exception:
                width = 512
            try:
                height = int(self.get_setting("height"))
            except Exception:
                height = 512

            # Advanced settings are exposed flat by Newelle despite nesting in UI
            steps_val = self.get_setting("steps")
            try:
                steps: Optional[int] = int(steps_val) if steps_val is not None else None
            except Exception:
                steps = None

            gs_val = self.get_setting("guidance_scale")
            try:
                guidance_scale: Optional[float] = float(gs_val) if gs_val is not None else None
            except Exception:
                guidance_scale = None

            seed_raw = self.get_setting("seed")
            try:
                seed: int = int(seed_raw) if seed_raw not in (None, "", "-1") else -1
            except Exception:
                seed = -1

            extra_payload_raw = self.get_setting("extra_payload") or "{}"
            try:
                extra_payload: Dict[str, Any] = json.loads(extra_payload_raw)
            except Exception:
                extra_payload = {}

            endpoint_path: str = extra_payload.get("endpoint_path", "/api/generate")
            url = f"{base_url}{endpoint_path}"

            # Prepare prompts
            positive = pos_tpl.replace("[input]", prompt)
            negative = neg_tpl

            # Helpers to coerce values from settings
            def get_int(name: str, default: int) -> int:
                try:
                    v = self.get_setting(name)
                    if v is None:
                        return default
                    return int(v)
                except Exception:
                    return default

            def get_float(name: str, default: float) -> float:
                try:
                    v = self.get_setting(name)
                    if v is None:
                        return default
                    return float(v)
                except Exception:
                    return default

            def get_bool(name: str, default: bool) -> bool:
                v = self.get_setting(name)
                if v is None:
                    return default
                if isinstance(v, bool):
                    return v
                # ScaleSetting likely returns numbers; treat >0 as True
                try:
                    return bool(int(v))
                except Exception:
                    s = str(v).strip().lower()
                    if s in ("true", "yes", "on", "1"):
                        return True
                    if s in ("false", "no", "off", "0"):
                        return False
                    return default

            # Construct a LightDiffusion-friendly payload (aligns with app.py defaults)
            payload: Dict[str, Any] = {
                "prompt": positive,
                "negative_prompt": negative,
                "width": width,
                "height": height,
                "num_images": get_int("num_images", 1),
                "batch_size": get_int("batch_size", 1),
                "hires_fix": get_bool("hires_fix", False),
                "adetailer": get_bool("adetailer", False),
                "enhance_prompt": get_bool("enhance_prompt", False),
                "img2img_enabled": get_bool("img2img_enabled", False),
                "img2img_image": (self.get_setting("img2img_image") or None),
                "stable_fast": get_bool("stable_fast", False),
                # If explicit seed is provided, server will force reuse; otherwise honor UI toggle
                "reuse_seed": (seed != -1) or get_bool("reuse_seed", False),
                "flux_enabled": get_bool("flux_enabled", False),
                "prio_speed": get_bool("prio_speed", False),
                "realistic_model": get_bool("realistic_model", False),
                "multiscale_enabled": get_bool("multiscale_enabled", True),
                "multiscale_intermittent": get_bool("multiscale_intermittent", False),
                "multiscale_factor": get_float("multiscale_factor", 0.5),
                "multiscale_fullres_start": get_int("multiscale_fullres_start", 3),
                "multiscale_fullres_end": get_int("multiscale_fullres_end", 8),
                "keep_models_loaded": get_bool("keep_models_loaded", True),
                "enable_preview": get_bool("enable_preview", False),
            }

            # If Img2Img is enabled, ensure an input image path is provided
            try:
                img2img_enabled = bool(int(self.get_setting("img2img_enabled") or 0))
            except Exception:
                img2img_enabled = False
            img2img_image = (self.get_setting("img2img_image") or "").strip()
            if img2img_enabled and not img2img_image:
                show_error_message("Img2Img is enabled but no image path is set in Advanced Settings.")
                return

            # Attach commonly requested extras if backend supports them
            if steps is not None:
                payload["steps"] = steps
            if guidance_scale is not None:
                payload["guidance_scale"] = guidance_scale
            if seed >= 0:
                payload["seed"] = seed

            # Merge user-specified extras (last-wins)
            if isinstance(extra_payload, dict):
                # `endpoint_path` is meta, not for backend payload
                extra_payload = {k: v for k, v in extra_payload.items() if k != "endpoint_path"}
                payload.update(extra_payload)

            # Fire request
            resp = requests.post(url, json=payload, timeout=120)
            if not resp.ok:
                show_error_message(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return

            # Interpret response
            data = resp.json()
            cache_out = os.path.join(self.cache_dir, f"{msg_uuid or 'latest'}.png")

            # 1) List of base64 images
            if isinstance(data, dict) and isinstance(data.get("images"), list) and data["images"]:
                img_b64 = data["images"][0]
                self._save_base64_png(img_b64, cache_out)
                widget.set_image_from_path(cache_out)
                return

            # 2) Single base64 image
            if isinstance(data, dict) and isinstance(data.get("image"), str):
                img_b64 = data["image"]
                self._save_base64_png(img_b64, cache_out)
                widget.set_image_from_path(cache_out)
                return

            # 3) Direct image URL
            if isinstance(data, dict) and isinstance(data.get("image_url"), str):
                widget.set_image_from_url(data["image_url"], callback=lambda ok: (
                    widget.download_and_save(cache_out) if ok else None
                ))
                return

            # 4) Local file path
            if isinstance(data, dict) and isinstance(data.get("file_path"), str):
                widget.set_image_from_path(data["file_path"])  # also leave a cached copy
                try:
                    widget.download_and_save(cache_out)
                except Exception:
                    pass
                return

            show_error_message("Unexpected response format from backend.")
        except Exception as e:
            traceback.print_exc()
            show_error_message(str(e))

    # --- Helpers ---
    def _extract_prompt_from_block(self, codeblock: str | None, lang: str | None) -> str:
        """Extract a clean prompt string from either the code block body or the lang/info string.

        Supports all of these forms:
        1) Standard fenced block with body:
           ```generateimage\n<your prompt>\n```
        2) One-liner info string (LLM sometimes emits):
           ```generateimage <your prompt>```
        3) Body that mistakenly includes the tag:
           generateimage <your prompt>

        We try to be permissive and strip leading tags and backticks.
        """

        def strip_ticks(s: str) -> str:
            s = s.strip()
            # Remove surrounding triple backticks if present
            if s.startswith("```") and s.endswith("```") and len(s) >= 6:
                s = s[3:-3]
            return s.strip()

        # Accept optional punctuation like ':' or '-' after the tag
        tag_patterns = [r"^generateimage\b[:\-]?", r"^lightdiffusion\b[:\-]?"]

        body = (codeblock or "").strip()
        info = (lang or "").strip()

        # If body is empty, try to parse the info string as: "generateimage <prompt>"
        if not body and info:
            # Accept either exact tag or tag followed by optional punctuation and prompt
            for tag_re in tag_patterns:
                m = re.match(tag_re + r"\s*(.*)$", info, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            # If info equals the tag exactly, return empty (no prompt)
            for tag_re in tag_patterns:
                if re.match(tag_re + r"$", info, re.IGNORECASE):
                    return ""

        # If body is present, clean it up
        body = strip_ticks(body)

        # Some models might include the tag at the beginning of body; strip it
        for tag_re in tag_patterns:
            body = re.sub(tag_re + r"\s*", "", body, count=1, flags=re.IGNORECASE)

        # Also handle cases where body is something like: "```generateimage prompt```"
        # which could slip through as-is in some pipelines.
        if body.startswith("```"):
            inner = strip_ticks(body)
            # If inner starts with tag, strip it
            for tag_re in tag_patterns:
                inner = re.sub(tag_re + r"\s*", "", inner, count=1, flags=re.IGNORECASE)
            body = inner.strip()

        return body.strip()

    def _save_base64_png(self, b64_data: str, out_path: str) -> None:
        # Some APIs prefix with data:image/png;base64,
        if "," in b64_data and b64_data.strip().startswith("data:"):
            b64_data = b64_data.split(",", 1)[1]
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(b64_data))


# Image generator widget
class ImageGeneratorWidget(Gtk.Box):
    """
    A sophisticated image widget with loading animation and save capabilities
    """
    
    def __init__(self, width=400, height=400):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.width = width
        self.height = height
        self.current_pixbuf = None
        self.current_url = None
        self.prompt = None  # Store the original prompt
        
        # Set up CSS for loading animation
        self.setup_css()
         
        # Create the main container
        self.image_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.image_container.set_size_request(self.width, self.height)
        self.image_container.set_halign(Gtk.Align.CENTER)
        self.image_container.set_valign(Gtk.Align.CENTER)
        
        
        # Create loading overlay
        self.loading_overlay = Gtk.Overlay()
        
        # Create placeholder for loading state
        self.loading_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.loading_container.set_halign(Gtk.Align.CENTER)
        self.loading_container.set_valign(Gtk.Align.CENTER)
        self.loading_container.add_css_class("loading-container")
        
        # Loading animation elements
        self.loading_pulse = Gtk.Box()
        self.loading_pulse.set_size_request(60, 60)
        self.loading_pulse.add_css_class("loading-pulse")
        
        self.loading_text = Gtk.Label(label="Loading image...")
        self.loading_text.add_css_class("loading-text")
        
        self.loading_container.append(self.loading_pulse)
        self.loading_container.append(self.loading_text)
        
        # Create the actual image widget
        self.image = Gtk.Image()
        self.image.set_size_request(self.width, self.height)
        
        # Create the image overlay 
        self.overlay_buttons = Gtk.Box(valign=Gtk.Align.START, halign=Gtk.Align.END)
        self.copy_button = Gtk.Button(icon_name="edit-copy-symbolic", css_classes=["success", "flat"])
        self.copy_button.set_tooltip_text("Copy prompt to clipboard")
        self.copy_button.connect("clicked", self.on_copy_clicked)
        self.overlay_buttons.append(self.copy_button)

        self.save_button = Gtk.Button(icon_name="document-save-symbolic", css_classes=["accent", "flat"])
        self.save_button.set_tooltip_text("Save image to file")
        self.save_button.connect("clicked", self.on_save_clicked)
        self.overlay_buttons.append(self.save_button)

        self.image_overlay = Gtk.Overlay()
        self.image_overlay.set_child(self.image)
        self.image_overlay.add_overlay(self.overlay_buttons)

        # On hover show buttons
        ev = Gtk.EventControllerMotion.new()
        ev.connect("enter", lambda x, y, data: self.overlay_buttons.set_visible(True))
        ev.connect("leave", lambda data: self.overlay_buttons.set_visible(False))
        self.image_overlay.add_controller(ev)
        
        # Setup overlay
        self.loading_overlay.set_child(self.image_overlay)
        self.loading_overlay.add_overlay(self.loading_container)

        self.image_container.append(self.loading_overlay) 
        self.append(self.image_container)
        
        # Initially show loading state
        self.show_loading(True)

    def setup_css(self):
        """Setup CSS for loading animations"""
        css_provider = Gtk.CssProvider()
        css = """
        .loading-container {
            border-radius: 12px;
            padding: 24px;
        }
        
        .loading-pulse {
            background: linear-gradient(45deg, #6366f1, #8b5cf6, #06b6d4, #10b981);
            background-size: 300% 300%;
            border-radius: 12px;
            width: 60px;
            height: 60px;
            min-width: 60px;
            min-height: 60px;
            max-width: 60px;
            max-height: 60px;
            animation: loading-pulse 2s ease-in-out infinite, loading-gradient 3s ease-in-out infinite;
        }
        
        .loading-text {
            margin-top: 16px;
            font-weight: 500;
            opacity: 0.8;
            animation: loading-fade 1.5s ease-in-out infinite alternate;
        }
        
        @keyframes loading-pulse {
            0%, 100% { 
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.4);
            }
            50% { 
                transform: scale(1.1);
                box-shadow: 0 0 0 10px rgba(99, 102, 241, 0);
            }
        }
        
        @keyframes loading-gradient {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes loading-fade {
            0% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .image-loaded {
            transition: all 0.7s ease-in-out;
            opacity: 1;
        }
        
        .image-loading {
            filter: blur(2px);
            opacity: 0.7;
            transition: all 0.3s ease-in-out;
        }
        """
        
        css_provider.load_from_data(css.encode())
        
        # Apply CSS to default display
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, 
            css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def set_size(self, width, height):
        """Set the size of the image widget"""
        self.width = width
        self.height = height
        self.image_container.set_size_request(width, height)
        self.image.set_size_request(width, height)

    def show_loading(self, show=True):
        """Show or hide the loading animation"""
        self.loading_container.set_visible(show)
        if show:
            self.image.add_css_class("image-loading")
        else:
            self.image.remove_css_class("image-loading")
            self.image.add_css_class("image-loaded")

    def set_image_from_url(self, url, callback=None):
        """Load image from URL with loading animation"""
        self.current_url = url
        self.show_loading(True)
        def load_complete_callback(pixbuf_loader):
            self.current_pixbuf = pixbuf_loader.get_pixbuf()
            # Scale pixbuf to fit widget size while maintaining aspect ratio
            scaled_pixbuf = self.scale_pixbuf_to_fit(self.current_pixbuf)
            self.image.set_from_pixbuf(scaled_pixbuf)
            self.show_loading(False)
            if callback:
                callback(True)
        
        def load_error_callback():
            self.show_loading(False)
            # Show error placeholder
            self.image.set_from_icon_name("image-missing")
            if callback:
                callback(False)
        
        try:
            load_image_with_callback(url, load_complete_callback)
        except Exception as e:
            print(f"Error loading image from URL: {e}")
            load_error_callback()

    def set_image_from_path(self, path, callback=None):
        """Load image from local file path"""
        self.show_loading(True)
        
        def load_in_thread():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
                self.current_pixbuf = pixbuf
                
                # Update UI in main thread
                def update_ui():
                    scaled_pixbuf = self.scale_pixbuf_to_fit(pixbuf)
                    self.image.set_from_pixbuf(scaled_pixbuf)
                    self.show_loading(False)
                    if callback:
                        callback(True)
                    return False  # Don't repeat
                
                from gi.repository import GLib
                GLib.idle_add(update_ui)
                
            except Exception as e:
                print(f"Error loading image from path: {e}")
                
                def show_error():
                    self.show_loading(False)
                    self.image.set_from_icon_name("image-missing")
                    if callback:
                        callback(False)
                    return False
                
                from gi.repository import GLib
                GLib.idle_add(show_error)
        
        thread = Thread(target=load_in_thread)
        thread.daemon = True
        thread.start()

    def scale_pixbuf_to_fit(self, pixbuf):
        """Scale pixbuf to fit widget size while maintaining aspect ratio"""
        if not pixbuf:
            return pixbuf
            
        orig_width = pixbuf.get_width()
        orig_height = pixbuf.get_height()
        
        # Calculate scaling factor to fit within widget bounds
        scale_x = self.width / orig_width
        scale_y = self.height / orig_height
        scale = min(scale_x, scale_y)
        
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        
        return pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)

    def save_image(self, file_path, format="png"):
        """Save the current image to a file"""
        if not self.current_pixbuf:
            raise ValueError("No image loaded to save")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save the original pixbuf (not the scaled version)
        self.current_pixbuf.savev(file_path, format, [], [])
        return True

    def download_and_save(self, save_path, format="png", callback=None):
        """Download current URL and save to path"""
        if not self.current_url:
            raise ValueError("No URL set to download")
        
        def download_complete(success):
            if success:
                try:
                    self.save_image(save_path, format)
                    if callback:
                        callback(True, save_path)
                except Exception as e:
                    print(f"Error saving image: {e}")
                    if callback:
                        callback(False, str(e))
            else:
                if callback:
                    callback(False, "Failed to load image")
        
        # If image is already loaded, save it directly
        if self.current_pixbuf:
            try:
                self.save_image(save_path, format)
                if callback:
                    callback(True, save_path)
            except Exception as e:
                if callback:
                    callback(False, str(e))
        else:
            # Load image first, then save
            self.set_image_from_url(self.current_url, download_complete)

    def on_save_clicked(self, button):
        """Handle save button click - open file chooser and save image as PNG"""
        if not self.current_pixbuf:
            # Show error dialog if no image is loaded
            dialog = Gtk.AlertDialog()
            dialog.set_message("No image to save")
            dialog.set_detail("Please wait for the image to load before saving.")
            dialog.show(self.get_root())
            return
        
        # Create file chooser dialog
        dialog = Gtk.FileDialog()
        dialog.set_title("Save Image as PNG")
        dialog.set_accept_label("Save")
        
        # Create PNG filter
        png_filter = Gtk.FileFilter()
        png_filter.set_name("PNG Images (*.png)")
        png_filter.add_pattern("*.png")
        dialog.set_default_filter(png_filter)
        
        # Set default filename
        dialog.set_initial_name("generated_image.png")
        
        # Show dialog and handle response
        def on_save_response(dialog, result):
            try:
                file = dialog.save_finish(result)
                if file:
                    file_path = file.get_path()
                    
                    # Ensure .png extension
                    if not file_path.lower().endswith('.png'):
                        file_path += '.png'
                    
                    # Save the image as PNG
                    try:
                        self.save_image(file_path, "png")
                        print(f"Image successfully saved to: {file_path}")
                        
                    except Exception as e:
                        # Show error dialog
                        error_dialog = Gtk.AlertDialog()
                        error_dialog.set_message("Failed to save image")
                        error_dialog.set_detail(f"Error: {str(e)}")
                        error_dialog.show(self.get_root())
                        
            except Exception as e:
                # Handle dialog cancellation silently
                if "dismissed" not in str(e).lower():
                    print(f"Save dialog error: {e}")
        
        dialog.save(self.get_root(), None, on_save_response)

    def set_prompt(self, prompt):
        """Set the original prompt for this image"""
        self.prompt = prompt

    def on_copy_clicked(self, button):
        """Handle copy button click - copy prompt to clipboard"""
        if not self.prompt:
            # Show info dialog if no prompt available
            dialog = Gtk.AlertDialog()
            dialog.set_message("No prompt to copy")
            dialog.set_detail("The original prompt is not available.")
            dialog.show(self.get_root())
            return
        
        # Get the clipboard
        clipboard = Gdk.Display.get_default().get_clipboard()
        
        # Copy the prompt to clipboard
        clipboard.set(self.prompt)
        
        # Show success feedback
        print(f"Copied to clipboard: {self.prompt}")
        
        # Optional: Brief visual feedback by changing button state
        original_classes = self.copy_button.get_css_classes()
        self.copy_button.set_css_classes(["success", "flat", "suggested-action"])
        
        # Reset button appearance after a short delay
        def reset_button():
            self.copy_button.set_css_classes(original_classes)
            return False  # Don't repeat
        
        from gi.repository import GLib
        GLib.timeout_add(1000, reset_button)  # Reset after 1 second
