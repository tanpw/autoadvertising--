@echo off
echo 正在构建全自动广告系统...

REM 检查依赖
pip install -r requirements.txt

REM 使用PyInstaller打包
pyinstaller --onefile --windowed --name "AutoAdSystem" --icon=icon.ico main.py

echo 构建完成！可执行文件位于 dist/ 目录中
pause