"""Capability probe run at end of setup.sh. Prints what is genuinely usable.
Never claims readiness it cannot demonstrate."""
import shutil, sys

def main():
    report = {}
    try:
        import cv2  # noqa
        report["opencv"] = cv2.__version__
    except Exception as e:
        report["opencv"] = f"MISSING: {e}"
    try:
        from deepface import DeepFace
        DeepFace.build_model("Facenet512")
        report["deepface+Facenet512"] = "loaded"
    except Exception as e:
        report["deepface+Facenet512"] = f"FAILED: {str(e)[:200]}"
    try:
        import torch
        report["torch"] = torch.__version__
    except Exception as e:
        report["torch"] = f"MISSING: {e}"
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        report["tesseract"] = "binary ok"
    except Exception as e:
        report["tesseract"] = f"FAILED: {e}"
    report["ffmpeg"] = "ok" if shutil.which("ffmpeg") else "MISSING"
    import os
    sf = os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "Silent-Face-Anti-Spoofing", "resources", "anti_spoof_models")
    report["silent-face-models"] = "ok" if os.path.isdir(sf) and any(f.endswith('.pth') for f in os.listdir(sf)) else "MISSING"
    vm = os.path.join(os.path.dirname(__file__), "..", "..", "models", "vosk-model-small-en-us-0.15")
    report["vosk-model"] = "ok" if os.path.isdir(vm) else "MISSING"
    for k, v in report.items():
        print(f"  {k:28s} {v}")

if __name__ == "__main__":
    main()
