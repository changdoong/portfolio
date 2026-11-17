"""개발 환경 검증: CUDA PyTorch 가 CPU 버전으로 바뀌지 않았는지 확인.

    .\\.venv\\Scripts\\python.exe scripts\\check_env.py

종료 코드: 0 = 정상(CUDA 빌드 + GPU 인식 + FP16 연산 성공), 1 = 문제 있음
"""
import platform
import sys


def main() -> int:
    ok = True
    print(f"Python      : {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform    : {platform.platform()}")

    try:
        import torch
    except ImportError:
        print("[FAIL] torch 가 설치되어 있지 않습니다. requirements-torch-cu128.txt 를 먼저 설치하세요.")
        return 1

    print(f"torch       : {torch.__version__} (CUDA build: {torch.version.cuda})")
    if torch.version.cuda is None or "+cpu" in torch.__version__:
        print("[FAIL] CPU 전용 torch 가 설치되어 있습니다. requirements-torch-cu128.txt 로 재설치하세요.")
        ok = False

    if not torch.cuda.is_available():
        print("[FAIL] torch.cuda.is_available() == False (드라이버/GPU 확인 필요)")
        ok = False
    else:
        props = torch.cuda.get_device_properties(0)
        print(f"GPU         : {props.name} | CC {props.major}.{props.minor} | VRAM {props.total_memory / 1024**3:.1f} GB")
        print(f"cuDNN       : {torch.backends.cudnn.version()}")
        a = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
        b = a @ a
        torch.cuda.synchronize()
        print(f"FP16 matmul : OK ({b.dtype}, {b.device})")

    for name in ("ultralytics", "cv2", "numpy", "lap", "yaml"):
        try:
            mod = __import__(name)
            print(f"{name:12s}: {getattr(mod, '__version__', 'ok')}")
        except ImportError:
            print(f"[FAIL] {name} 미설치 (pip install -r requirements.txt)")
            ok = False

    print("\n결과:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
