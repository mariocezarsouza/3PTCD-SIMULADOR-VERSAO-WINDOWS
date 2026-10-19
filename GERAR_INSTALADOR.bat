@echo off
chcp 65001 >nul
title Simulador de Armazenagem UCE II - Gerar programa e instalador
cd /d "%~dp0"
echo ================================================================
echo  SIMULADOR INTELIGENTE DE ARMAZENAGEM - DESKTOP WINDOWS v4.6.0
echo  Gera o programa (pasta dist) e o instalador (installer_output)
echo ================================================================
echo.
python build_windows.py
if errorlevel 1 (
  echo.
  echo Houve um erro. Leia as mensagens acima.
) else (
  echo.
  echo Concluido. O instalador esta na pasta installer_output.
)
pause
