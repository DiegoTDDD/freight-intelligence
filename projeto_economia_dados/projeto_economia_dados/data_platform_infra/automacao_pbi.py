import pyautogui
import time

print("O robô vai assumir o controle em 5 segundos. Mude para a tela do Power BI e solte o mouse!")
time.sleep(5)

# Move o mouse e arrasta (coordenadas de exemplo)
pyautogui.moveTo(1700, 400, duration=1) 
pyautogui.dragTo(1500, 600, duration=1.5, button='left') 

print("Mapeamento visual concluído.")
