#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动脚本 - 检查环境并启动应用
"""

import sys
import os
import subprocess

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 7):
        print("错误: 需要Python 3.7或更高版本")
        print(f"当前版本: {sys.version}")
        return False
    return True

def check_dependencies():
    """检查依赖包"""
    required_packages = [
        'PyQt5',
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("缺少以下依赖包:")
        for package in missing_packages:
            print(f" - {package}")
        
        print("\n正在自动安装依赖...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
            ])
            print("依赖安装完成！")
            return True
        except subprocess.CalledProcessError:
            print("依赖安装失败，请手动运行: pip install -r requirements.txt")
            return False
    
    return True

def create_directories():
    """创建必要的目录"""
    directories = ['data', 'logs', 'config']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"创建目录: {directory}")

def main():
    """主函数"""
    print("全自动广告系统启动器 v1.0")
    print("=" * 40)
    
    # 检查Python版本
    if not check_python_version():
        input("按任意键退出...")
        return
    
    # 检查依赖
    if not check_dependencies():
        input("按任意键退出...")
        return
    
    # 创建目录
    create_directories()
    
    # 启动主程序
    try:
        print("正在启动应用程序...")
        from main import main as app_main
        app_main()
    except Exception as e:
        print(f"启动失败: {e}")
        input("按任意键退出...")

if __name__ == "__main__":
    main()