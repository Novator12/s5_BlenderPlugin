from pathlib import Path

import bpy


OUTPUT = Path(__file__).resolve().parents[1] / "images" / "fig-01-blender-5-0-1-startup.png"


def capture():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = bpy.ops.screen.screenshot(filepath=str(OUTPUT), check_existing=False)
        print(f"HANDBOOK_SCREENSHOT={OUTPUT} RESULT={sorted(result)}")
    except Exception as exc:
        print(f"HANDBOOK_SCREENSHOT_ERROR={type(exc).__name__}: {exc}")
    finally:
        bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(capture, first_interval=2.0)
