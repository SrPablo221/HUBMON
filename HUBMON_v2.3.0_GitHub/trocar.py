"""Troca a entrada do monitor diretamente por DDC/CI, sem servidor local.

Uso:
    python trocar.py hdmi  # PS5 (0x01)
    python trocar.py dp    # PC  (0x03)
    python trocar.py 0xNN  # código manual
"""
import sys

from monitorcontrol import get_monitors

CODIGOS = {"hdmi": 0x01, "dp": 0x03}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    alvo = sys.argv[1].lower()
    valor = CODIGOS[alvo] if alvo in CODIGOS else int(alvo, 0)
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    monitores = get_monitors()
    if idx >= len(monitores):
        print("Monitor não encontrado (DDC/CI ligado no OSD?)")
        return 1
    with monitores[idx] as m:
        m.set_input_source(valor)
    print(f"Enviado {alvo} (0x{valor:02X})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
