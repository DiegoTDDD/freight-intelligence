import pyautogui
import time

print("Rastreador ativado. Pressione Ctrl+C no terminal para parar.")
try:
    while True:
        x, y = pyautogui.position()
        print(f"Posição atual -> X: {x} | Y: {y}", end="\r")
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\nRastreamento finalizado.")
