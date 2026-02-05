import gradio as gr
import subprocess
import os
import json
import re
import shutil
import threading
import time
from pathlib import Path
from dotenv import dotenv_values, set_key

AUTOMV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoMV_repo")
RESULT_DIR = os.path.join(AUTOMV_DIR, "result")
ENV_PATH = os.path.join(AUTOMV_DIR, ".env")

API_KEYS = [
    ("GEMINI_API_KEY", "Gemini API Key (Google)"),
    ("DOUBAO_API_KEY", "Ark API Key (BytePlus or Volcengine)"),
    ("ALIYUN_OSS_ACCESS_KEY_ID", "Aliyun OSS Access Key ID"),
    ("ALIYUN_OSS_ACCESS_KEY_SECRET", "Aliyun OSS Access Key Secret"),
    ("ALIYUN_OSS_BUCKET_NAME", "Aliyun OSS Bucket Name"),
    ("HUOSHAN_ACCESS_KEY", "Huoshan Access Key (China only, for lip-sync)"),
    ("HUOSHAN_SECRET_KEY", "Huoshan Secret Key (China only, for lip-sync)"),
]

PROVIDER_SETTING = ("ARK_PROVIDER", "API Provider", "byteplus")

MODEL_SETTINGS = [
    ("GPU_ID", "GPU Device ID", "0"),
    ("WHISPER_MODEL", "Whisper Model", "openai/whisper-large-v2"),
    ("QWEN_OMNI_MODEL", "Qwen Omni Model", "Qwen/Qwen2.5-Omni-7B"),
    ("MODEL_SEEDREAM", "Seedream Model ID", "seedream-4-0-250828"),
    ("MODEL_SEEDANCE", "Seedance Model ID", "seedance-1-0-pro-250528"),
    ("MODEL_SEED_LLM", "Seed LLM Model ID", "seed-1.6-250615"),
]


def load_env():
    if os.path.exists(ENV_PATH):
        return dotenv_values(ENV_PATH)
    return {}


def save_env_settings(provider, *values):
    all_keys = [k for k, _ in API_KEYS] + [k for k, _, _ in MODEL_SETTINGS]
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w") as f:
            f.write("")

    # Save provider
    set_key(ENV_PATH, "ARK_PROVIDER", provider.strip() if provider else "byteplus")

    for key, val in zip(all_keys, values):
        if val and val.strip():
            set_key(ENV_PATH, key, val.strip())

    env = load_env()
    configured = [k for k, _ in API_KEYS if env.get(k)]
    missing = [label for k, label in API_KEYS if not env.get(k)]

    prov = env.get("ARK_PROVIDER", "byteplus")
    status = f"Provider: {prov}\n"
    status += f"Configured: {len(configured)}/{len(API_KEYS)} API keys"
    if missing:
        status += f"\nMissing: {', '.join(missing)}"
    else:
        status += "\nAll API keys are set."

    if prov == "byteplus":
        status += "\n\nNote: Lip-sync (Jimeng) requires Volcengine (China). Set to 'None' if using BytePlus."
    return status


def get_env_status():
    env = load_env()
    prov = env.get("ARK_PROVIDER", "byteplus")
    lines = [f"  Provider: {prov}"]
    for key, label in API_KEYS:
        val = env.get(key, "")
        if val:
            lines.append(f"  {label}: set")
        else:
            lines.append(f"  {label}: MISSING")
    return "\n".join(lines)


def sanitize_music_name(name):
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def list_projects():
    if not os.path.exists(RESULT_DIR):
        return []
    projects = []
    for d in sorted(os.listdir(RESULT_DIR)):
        if os.path.isdir(os.path.join(RESULT_DIR, d)):
            projects.append(d)
    return projects


def generate_music_video(audio_file, music_name, lip_sync, resolution):
    if not audio_file:
        yield "Error: Please upload a music file."
        return

    music_name = sanitize_music_name(music_name or "untitled")
    if not music_name:
        yield "Error: Please provide a valid music name (letters, numbers, underscores)."
        return

    env = load_env()
    missing = [label for k, label in API_KEYS[:2] if not env.get(k)]
    if missing:
        yield f"Error: Required API keys not configured: {', '.join(missing)}\nPlease go to the Settings tab."
        return

    # Warn if using BytePlus with lip-sync
    provider = env.get("ARK_PROVIDER", "byteplus")
    if provider == "byteplus" and lip_sync != "None":
        yield "Warning: Lip-sync (Jimeng) requires Volcengine (China) credentials.\nSwitching lip-sync to 'None' for BytePlus provider.\n\n"
        lip_sync = "None"

    project_dir = os.path.join(RESULT_DIR, music_name)
    os.makedirs(project_dir, exist_ok=True)

    ext = os.path.splitext(audio_file)[1].lower()
    if ext not in (".mp3", ".wav"):
        yield "Error: Only .mp3 and .wav files are supported."
        return

    dest_audio = os.path.join(project_dir, f"{music_name}.mp3")
    shutil.copy2(audio_file, dest_audio)

    log = f"=== AutoMV Pipeline ===\n"
    log += f"Provider: {provider}\n"
    log += f"Music: {music_name}\n"
    log += f"Lip-sync: {lip_sync}\n"
    log += f"Resolution: {resolution}\n"
    log += f"Audio copied to: {dest_audio}\n\n"
    yield log

    run_env = {**os.environ, **env}
    run_env["PYTHONPATH"] = AUTOMV_DIR

    # Patch config.py music_name before running
    config_path = os.path.join(AUTOMV_DIR, "config.py")
    with open(config_path, "r") as f:
        config_content = f.read()
    original_config = config_content
    config_content = re.sub(
        r'music_name\s*=\s*"[^"]*"',
        f'music_name = "{music_name}"',
        config_content,
    )
    with open(config_path, "w") as f:
        f.write(config_content)

    try:
        # Stage 1: Picture Generation (SongFormer + images)
        log += "--- Stage 1: Picture Generation ---\n"
        log += "Running SongFormer analysis + image generation...\n"
        yield log

        proc = subprocess.Popen(
            ["python", "-m", "picture_generate.main"],
            cwd=AUTOMV_DIR,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            log += line
            yield log

        proc.wait()
        if proc.returncode != 0:
            log += f"\nStage 1 failed with exit code {proc.returncode}\n"
            yield log
            return

        log += "\nStage 1 complete.\n\n"
        yield log

        # Stage 2: Video Generation
        log += "--- Stage 2: Video Generation ---\n"

        # Build the generation command based on lip-sync choice
        gen_script = _build_gen_script(music_name, lip_sync, resolution)
        gen_script_path = os.path.join(AUTOMV_DIR, "_ui_generate.py")
        with open(gen_script_path, "w") as f:
            f.write(gen_script)

        log += "Generating video clips and assembling final MV...\n"
        yield log

        proc = subprocess.Popen(
            ["python", "_ui_generate.py"],
            cwd=AUTOMV_DIR,
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            log += line
            yield log

        proc.wait()
        if proc.returncode != 0:
            log += f"\nStage 2 failed with exit code {proc.returncode}\n"
            yield log
            return

        # Clean up temp script
        if os.path.exists(gen_script_path):
            os.remove(gen_script_path)

        final_video = os.path.join(project_dir, f"mv_{music_name}.mp4")
        if os.path.exists(final_video):
            log += f"\nDone! Final video: {final_video}\n"
        else:
            log += "\nPipeline finished but final video not found. Check logs above.\n"
        yield log

    finally:
        # Restore original config
        with open(config_path, "w") as f:
            f.write(original_config)


def _build_gen_script(music_name, lip_sync, resolution):
    lines = [
        "from video_generate.video_generate_pipeline import full_video_gen",
        "from config import Config",
    ]
    if lip_sync == "Jimeng (fast)":
        lines.append("from generate_lip_video.gen_lip_sycn_video_jimeng import gen_lip_sync_video_jimeng")
        lines.append(f'gen_lip_sync_video_jimeng("{music_name}", config=Config)')
    elif lip_sync == "Wan2.2 (slow, cheap)":
        lines.append("from generate_lip_video.gen_lip_sycn_video import gen_lip_sync_video")
        lines.append(f'gen_lip_sync_video("{music_name}")')

    res = "480p" if resolution == "480p" else "720p"
    lines.append(f'full_video_gen("{music_name}", resolution="{res}", config=Config)')
    return "\n".join(lines) + "\n"


def load_project(project_name):
    if not project_name:
        return None, "No project selected", "No project selected", [], None

    project_dir = os.path.join(RESULT_DIR, project_name)

    # Video
    video_path = os.path.join(project_dir, f"mv_{project_name}.mp4")
    video = video_path if os.path.exists(video_path) else None

    # Storyboard
    story_path = os.path.join(project_dir, "story.json")
    storyboard = "No storyboard found."
    if os.path.exists(story_path):
        with open(story_path, "r", encoding="utf-8") as f:
            story_data = json.load(f)
        rows = []
        for seg in story_data:
            rows.append(
                f"**#{seg.get('number', '?')}** [{seg.get('start', 0):.1f}s - {seg.get('end', 0):.1f}s] "
                f"({seg.get('label', 'unknown')})\n"
                f"Lyrics: {seg.get('text', 'N/A')}\n"
                f"Scene: {seg.get('story', 'N/A')}\n"
            )
        storyboard = "\n---\n".join(rows) if rows else "Empty storyboard."

    # Characters
    label_path = os.path.join(project_dir, "label.json")
    characters = "No character data found."
    if os.path.exists(label_path):
        with open(label_path, "r", encoding="utf-8") as f:
            label_data = json.load(f)
        char_lines = []
        style = label_data.get("style_requirement", "")
        if style:
            char_lines.append(f"**Style:** {style}\n")
        chars = label_data.get("character_depiction", {})
        for name, info in chars.items():
            char_lines.append(
                f"**{info.get('name', name)}** — {info.get('gender', '?')}, {info.get('age', '?')}\n"
                f"Appearance: {info.get('appearance', 'N/A')}\n"
                f"Role: {info.get('role', 'N/A')}\n"
            )
        characters = "\n---\n".join(char_lines) if char_lines else "No characters defined."

    # Keyframes
    picture_dir = os.path.join(project_dir, "picture")
    keyframes = []
    if os.path.exists(picture_dir):
        for seg_dir in sorted(os.listdir(picture_dir)):
            seg_path = os.path.join(picture_dir, seg_dir)
            if os.path.isdir(seg_path):
                for img_file in sorted(os.listdir(seg_path)):
                    if img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                        keyframes.append(os.path.join(seg_path, img_file))

    # Download
    download = video_path if video else None

    return video, storyboard, characters, keyframes, download


def refresh_projects():
    return gr.update(choices=list_projects())


# ── Build UI ──────────────────────────────────────────────────────────────────

with gr.Blocks(title="AutoMV — Music Video Generator") as app:
    gr.Markdown("# AutoMV — Music Video Generator\nGenerate complete music videos from songs automatically using AI agents.")

    with gr.Tabs():
        # ── Settings Tab ─────────────────────────────────────────────────────
        with gr.Tab("Settings"):
            env = load_env()

            gr.Markdown("### API Provider")
            gr.Markdown(
                "**BytePlus** (international, no Chinese phone needed) or "
                "**Volcengine** (China, requires +86 phone).\n\n"
                "Get your BytePlus API key at [console.byteplus.com/ark](https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey)"
            )
            provider_input = gr.Radio(
                label="Provider",
                choices=["byteplus", "volcengine"],
                value=env.get("ARK_PROVIDER", "byteplus"),
                info="BytePlus = international access. Volcengine = China access.",
            )

            gr.Markdown("### API Keys")
            gr.Markdown("Configure the API keys required by AutoMV. Keys are saved to `AutoMV_repo/.env`.")

            api_inputs = []
            for key, label in API_KEYS:
                inp = gr.Textbox(
                    label=label,
                    value=env.get(key, ""),
                    type="password",
                    placeholder=f"Enter {label}...",
                )
                api_inputs.append(inp)

            gr.Markdown("### Model Settings")
            model_inputs = []
            for key, label, default in MODEL_SETTINGS:
                inp = gr.Textbox(
                    label=label,
                    value=env.get(key, default),
                    placeholder=default,
                )
                model_inputs.append(inp)

            save_btn = gr.Button("Save Settings", variant="primary")
            settings_status = gr.Textbox(label="Status", value=get_env_status(), interactive=False, lines=10)

            save_btn.click(
                fn=save_env_settings,
                inputs=[provider_input] + api_inputs + model_inputs,
                outputs=settings_status,
            )

        # ── Generate Tab ─────────────────────────────────────────────────────
        with gr.Tab("Generate"):
            gr.Markdown("### Generate Music Video")
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(label="Upload Music (.mp3 / .wav)", type="filepath")
                    music_name_input = gr.Textbox(
                        label="Music Name",
                        placeholder="my_song (letters, numbers, underscores only)",
                        info="Used as the project folder name. Auto-sanitized.",
                    )
                    lip_sync_input = gr.Radio(
                        label="Lip-Sync Mode",
                        choices=["None", "Jimeng (fast)", "Wan2.2 (slow, cheap)"],
                        value="None",
                        info="Jimeng requires Volcengine (China). Not available with BytePlus.",
                    )
                    resolution_input = gr.Dropdown(
                        label="Resolution",
                        choices=["480p", "720p"],
                        value="480p",
                    )
                    generate_btn = gr.Button("Generate Music Video", variant="primary", size="lg")

                with gr.Column(scale=2):
                    progress_log = gr.Textbox(
                        label="Pipeline Log",
                        lines=30,
                        max_lines=50,
                        interactive=False,
                        autoscroll=True,
                    )

            generate_btn.click(
                fn=generate_music_video,
                inputs=[audio_input, music_name_input, lip_sync_input, resolution_input],
                outputs=progress_log,
            )

        # ── Results Tab ──────────────────────────────────────────────────────
        with gr.Tab("Results"):
            gr.Markdown("### Browse Generated Music Videos")
            with gr.Row():
                project_dropdown = gr.Dropdown(
                    label="Select Project",
                    choices=list_projects(),
                    interactive=True,
                )
                refresh_btn = gr.Button("Refresh", size="sm")

            with gr.Row():
                with gr.Column(scale=2):
                    video_output = gr.Video(label="Final Music Video")
                    download_output = gr.File(label="Download Video")
                with gr.Column(scale=1):
                    gr.Markdown("#### Keyframes")
                    keyframes_gallery = gr.Gallery(label="Generated Keyframes", columns=3, height="auto")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Storyboard")
                    storyboard_output = gr.Markdown("Select a project to view storyboard.")
                with gr.Column():
                    gr.Markdown("#### Characters")
                    characters_output = gr.Markdown("Select a project to view characters.")

            refresh_btn.click(fn=refresh_projects, outputs=project_dropdown)
            project_dropdown.change(
                fn=load_project,
                inputs=project_dropdown,
                outputs=[video_output, storyboard_output, characters_output, keyframes_gallery, download_output],
            )


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
