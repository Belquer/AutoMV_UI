"""
Patches the AutoMV repo to support BytePlus (international) as an alternative
to Volcengine (China-only). Run automatically by AutoMV_UI.command after cloning.

Changes:
- config.py: Adds ARK_PROVIDER, get_ark_base_url(), get_model_name() helpers
- picture_generate/picture.py: Uses BytePlus SDK import + config-driven model names
- video_generate/video_generate_pipeline.py: Uses BytePlus SDK import + config base_url
- video_generate/call_gemini.py: Uses config-driven base_url and model names
- generate_lip_video/gen_lip_sycn_video_jimeng.py: Uses config credentials instead of hardcoded
"""

import re
import os
import sys

REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoMV_repo")


def patch_file(filepath, replacements, marker="byteplussdkarkruntime"):
    """Apply a list of (old, new) string replacements to a file.
    Skips if marker string is already present (idempotent)."""
    full_path = os.path.join(REPO_DIR, filepath)
    if not os.path.exists(full_path):
        print(f"  [SKIP] {filepath} not found")
        return False

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    if marker and marker in content:
        print(f"  [OK] {filepath} already patched")
        return True

    original = content
    for old, new in replacements:
        if old not in content:
            print(f"  [WARN] Pattern not found in {filepath}: {old[:60]}...")
            continue
        content = content.replace(old, new, 1)

    if content == original:
        print(f"  [OK] {filepath} no changes needed")
        return True

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [PATCHED] {filepath}")
    return True


def patch_config():
    """Patch config.py to add BytePlus provider support."""
    filepath = "config.py"
    full_path = os.path.join(REPO_DIR, filepath)

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if already patched
    if "ARK_PROVIDER" in content:
        print(f"  [OK] {filepath} already patched")
        return True

    replacements = [
        (
            '    music_name = "1"',
            '    music_name = "1"\n'
            '\n'
            '    # BytePlus (international) vs Volcengine (China) configuration\n'
            '    ARK_PROVIDER = os.getenv(\'ARK_PROVIDER\', \'byteplus\')\n'
            '\n'
            '    @classmethod\n'
            '    def get_ark_base_url(cls):\n'
            '        if cls.ARK_PROVIDER == \'byteplus\':\n'
            '            return "https://ark.ap-southeast.bytepluses.com/api/v3"\n'
            '        return "https://ark.cn-beijing.volces.com/api/v3"\n'
            '\n'
            '    @classmethod\n'
            '    def get_model_name(cls, model_short):\n'
            '        if cls.ARK_PROVIDER == \'byteplus\':\n'
            '            return model_short\n'
            '        return f"doubao-{model_short}"\n'
            '\n'
            '    MODEL_SEEDREAM = os.getenv(\'MODEL_SEEDREAM\', \'seedream-4-0-250828\')\n'
            '    MODEL_SEEDANCE = os.getenv(\'MODEL_SEEDANCE\', \'seedance-1-0-pro-250528\')\n'
            '    MODEL_SEED_LLM = os.getenv(\'MODEL_SEED_LLM\', \'seed-1.6-250615\')\n'
        ),
        (
            '        if not cls.DOUBAO_API_KEY:\n'
            '            raise ValueError("OPENAI_API_KEY not found in .env")',
            '        if not cls.DOUBAO_API_KEY:\n'
            '            raise ValueError("DOUBAO_API_KEY not found in .env")',
        ),
    ]
    return patch_file(filepath, replacements)


def patch_picture():
    """Patch picture_generate/picture.py for BytePlus SDK."""
    return patch_file("picture_generate/picture.py", [
        (
            "from volcenginesdkarkruntime import Ark",
            "try:\n    from byteplussdkarkruntime import Ark\nexcept ImportError:\n    from volcenginesdkarkruntime import Ark",
        ),
        (
            "client_doubao = Ark(\n    api_key=Config.DOUBAO_API_KEY\n)",
            "client_doubao = Ark(\n    api_key=Config.DOUBAO_API_KEY,\n    base_url=Config.get_ark_base_url(),\n)",
        ),
        (
            'model="doubao-seedream-4-0-250828",',
            "model=Config.get_model_name(Config.MODEL_SEEDREAM),",
        ),
        (
            'model="doubao-seed-1.6-250615",',
            "model=Config.get_model_name(Config.MODEL_SEED_LLM),",
        ),
    ])


def patch_video_pipeline():
    """Patch video_generate/video_generate_pipeline.py for BytePlus SDK."""
    return patch_file("video_generate/video_generate_pipeline.py", [
        (
            "from volcenginesdkarkruntime import Ark",
            "try:\n    from byteplussdkarkruntime import Ark\nexcept ImportError:\n    from volcenginesdkarkruntime import Ark",
        ),
        (
            'def __init__(self, api_key: str, base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):\n'
            '        self.client = Ark(base_url=base_url, api_key=api_key)',
            'def __init__(self, api_key: str, base_url: str = None):\n'
            '        if base_url is None:\n'
            '            base_url = Config.get_ark_base_url()\n'
            '        self.client = Ark(base_url=base_url, api_key=api_key)',
        ),
        (
            '    model = "doubao-seedance-1-0-pro-250528"',
            '    model = config.get_model_name(config.MODEL_SEEDANCE)',
        ),
    ])


def patch_call_gemini():
    """Patch video_generate/call_gemini.py for BytePlus base URL."""
    return patch_file("video_generate/call_gemini.py", marker="get_ark_base_url", replacements=[
        (
            'base_url="https://ark.cn-beijing.volces.com/api/v3"',
            "base_url=Config.get_ark_base_url()",
        ),
        (
            'model="doubao-seed-1.6-250615",',
            "model=Config.get_model_name(Config.MODEL_SEED_LLM),",
        ),
    ])


def patch_lip_sync():
    """Patch lip sync to use config credentials instead of hardcoded keys."""
    filepath = "generate_lip_video/gen_lip_sycn_video_jimeng.py"
    full_path = os.path.join(REPO_DIR, filepath)
    if not os.path.exists(full_path):
        print(f"  [SKIP] {filepath} not found")
        return False

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "config.HUOSHAN_ACCESS_KEY" in content:
        print(f"  [OK] {filepath} already patched")
        return True

    # Replace hardcoded set_ak/set_sk with config-based values
    new_content = re.sub(
        r"    visual_service\.set_ak\('[^']+'\)\n    visual_service\.set_sk\('[^']+'\)",
        "    # Note: Jimeng lip-sync requires Volcengine (China) credentials.\n"
        "    # This feature is NOT available via BytePlus (international).\n"
        "    visual_service.set_ak(config.HUOSHAN_ACCESS_KEY)\n"
        "    visual_service.set_sk(config.HUOSHAN_SECRET_KEY)",
        content,
    )

    if new_content == content:
        print(f"  [WARN] Could not find set_ak/set_sk pattern in {filepath}")
        return False

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  [PATCHED] {filepath}")
    return True


def main():
    print("Applying BytePlus patches to AutoMV repo...")
    if not os.path.exists(REPO_DIR):
        print(f"ERROR: AutoMV repo not found at {REPO_DIR}")
        sys.exit(1)

    patch_config()
    patch_picture()
    patch_video_pipeline()
    patch_call_gemini()
    patch_lip_sync()
    print("Done! BytePlus support patched successfully.")


if __name__ == "__main__":
    main()
