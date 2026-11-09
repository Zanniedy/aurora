import argparse
import asyncio
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]


def contact_sheet(directory):
    from PIL import Image, ImageDraw, ImageFont

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    title_font = ImageFont.truetype(font_path, 32)
    text_font = ImageFont.truetype(font_path, 20)
    sheet = Image.new("RGB", (1600, 1500), "#101c2a")
    draw = ImageDraw.Draw(sheet)
    draw.text((30, 20), "AURORA / RMUL 2027 STL", font=title_font, fill="#ecf4fa")
    draw.text((30, 65), "Unmodified STL | Key dimensions checked against the supplied V1.0.0 rule manual", font=text_font, fill="#a9bacb")
    with Image.open(directory / "overview.png") as image:
        sheet.paste(image.convert("RGB").resize((1540, 866)), (30, 110))
    for name, offset, caption in (
        ("tunnel", 30, "TUNNEL / 800 mm wide, 250 mm clear height"),
        ("stairs", 815, "HIGHLAND / 200 mm above ground"),
    ):
        draw.text((offset, 996), caption, font=text_font, fill="#ecf4fa")
        with Image.open(directory / f"{name}.png") as image:
            sheet.paste(image.convert("RGB").resize((755, 425)), (offset, 1030))
    draw.text((30, 1470), "Units: meters | No MID360 sensor or point-cloud simulation in this preview", font=text_font, fill="#a9bacb")
    sheet.save(directory / "aurora_preview.png")


def main():
    parser = argparse.ArgumentParser(description="View or render the Aurora USD scene using Isaac Sim.")
    parser.add_argument("--scene", type=Path, default=ROOT / "scenes/aurora_terrain.usda")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--capture", action="store_true", help="Also save screenshots when opening the GUI")
    parser.add_argument("--camera", choices=("Overview", "Tunnel", "Stairs", "Top"), default="Tunnel")
    args = parser.parse_args()
    scene_path = args.scene.resolve()
    if not scene_path.is_file():
        parser.error(f"Scene does not exist: {scene_path}. Run scripts/build_scene.py first.")

    from isaacsim import SimulationApp

    app = SimulationApp({
        "headless": not args.gui,
        "width": 1600,
        "height": 900,
        "renderer": "RaytracedLighting",
        "anti_aliasing": 1,
        "multi_gpu": False,
    })
    exit_code = 0
    try:
        import omni.usd
        import omni.kit.renderer_capture
        from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport

        if not omni.usd.get_context().open_stage(str(scene_path)):
            raise RuntimeError(f"Cannot open scene: {scene_path}")
        for _ in range(90):
            app.update()
        viewport = get_active_viewport()
        if viewport is None:
            raise RuntimeError("Isaac Sim did not create an active viewport")
        viewport.set_texture_resolution((1600, 900))
        viewport.camera_path = f"/World/Cameras/{args.camera}"
        print(f"Scene ready: {scene_path}", flush=True)
        if args.gui and not args.capture:
            while app.is_running():
                app.update()
            return

        args.output.mkdir(parents=True, exist_ok=True)
        for name in ("Overview", "Tunnel", "Stairs"):
            viewport.camera_path = f"/World/Cameras/{name}"
            for _ in range(90):
                app.update()
            output = (args.output / f"{name.lower()}.png").resolve()
            capture = capture_viewport_to_file(viewport, str(output))
            pending = asyncio.ensure_future(capture.wait_for_result())
            print(f"Capturing: {name}", flush=True)
            deadline = time.monotonic() + 300
            while not pending.done():
                if time.monotonic() > deadline:
                    pending.cancel()
                    raise TimeoutError(f"Timed out rendering {output}")
                app.update()
            if not pending.result():
                raise RuntimeError(f"No render AOV was available for {name}")
            app.update()
            omni.kit.renderer_capture.acquire_renderer_capture_interface().wait_async_capture()
            if not output.is_file():
                raise RuntimeError(f"Capture did not write {output}")
            print(f"Rendered: {output}", flush=True)
        contact_sheet(args.output)
        print(f"Preview: {(args.output / 'aurora_preview.png').resolve()}", flush=True)
        if args.gui:
            viewport.camera_path = f"/World/Cameras/{args.camera}"
            while app.is_running():
                app.update()
    except Exception:
        exit_code = 1
        traceback.print_exc()
    finally:
        app.close(exit_code=exit_code)


if __name__ == "__main__":
    main()
