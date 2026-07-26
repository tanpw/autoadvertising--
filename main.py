#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全自动广告系统 - 主程序
Author: AI Assistant
License: Custom License (非MIT协议)
"""

import sys
import os
import json
import sqlite3
import threading
import time
from datetime import datetime
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
except ImportError:
    print("请安装PyQt5: pip install PyQt5")
    sys.exit(1)

@dataclass
class AdData:
    """广告数据结构"""
    id: str
    title: str
    content: str
    keywords: List[str]
    target_audience: str
    budget: float
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""

class CacheManager:
    """缓存管理器"""
    def __init__(self, cache_file="ad_cache.json"):
        self.cache_file = cache_file
        self.cache_data = self.load_cache()
        self.lock = threading.Lock()
    
    def load_cache(self) -> Dict:
        """加载缓存数据"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载缓存失败: {e}")
        return {}
    
    def save_cache(self):
        """保存缓存数据"""
        with self.lock:
            try:
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"保存缓存失败: {e}")
    
    def get(self, key: str, default=None):
        """获取缓存值"""
        return self.cache_data.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self.lock:
            self.cache_data[key] = value
            self.save_cache()

class DatabaseManager:
    """数据库管理器"""
    def __init__(self, db_file="ads.db"):
        self.db_file = db_file
        self.init_database()
        self.lock = threading.Lock()
    
    def init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT,
                    target_audience TEXT,
                    budget REAL,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT,
                    updated_at TEXT,
                    hash TEXT UNIQUE
                )
            ''')
            conn.commit()
    
    def add_ad(self, ad: AdData) -> bool:
        """添加广告数据，自动去重"""
        content_hash = hashlib.md5(ad.content.encode()).hexdigest()
        
        with self.lock:
            try:
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.cursor()
                    
                    # 检查重复
                    cursor.execute("SELECT id FROM ads WHERE hash = ?", (content_hash,))
                    if cursor.fetchone():
                        return False  # 重复数据
                    
                    # 插入新数据
                    cursor.execute('''
                        INSERT INTO ads (id, title, content, keywords, target_audience, 
                                       budget, status, created_at, updated_at, hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ad.id, ad.title, ad.content, json.dumps(ad.keywords),
                        ad.target_audience, ad.budget, ad.status,
                        ad.created_at, ad.updated_at, content_hash
                    ))
                    conn.commit()
                    return True
            except Exception as e:
                print(f"添加广告数据失败: {e}")
                return False
    
    def get_all_ads(self) -> List[AdData]:
        """获取所有广告数据"""
        ads = []
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ads ORDER BY created_at DESC")
                for row in cursor.fetchall():
                    ads.append(AdData(
                        id=row[0], title=row[1], content=row[2],
                        keywords=json.loads(row[3] or "[]"),
                        target_audience=row[4], budget=row[5],
                        status=row[6], created_at=row[7], updated_at=row[8]
                    ))
        except Exception as e:
            print(f"获取广告数据失败: {e}")
        return ads
    
    def update_ad(self, ad: AdData) -> bool:
        """更新广告数据"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE ads SET title=?, content=?, keywords=?, target_audience=?,
                                     budget=?, status=?, updated_at=?
                        WHERE id=?
                    ''', (
                        ad.title, ad.content, json.dumps(ad.keywords),
                        ad.target_audience, ad.budget, ad.status,
                        ad.updated_at, ad.id
                    ))
                    conn.commit()
                    return True
            except Exception as e:
                print(f"更新广告数据失败: {e}")
                return False
    
    def delete_ad(self, ad_id: str) -> bool:
        """删除广告数据"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM ads WHERE id=?", (ad_id,))
                    conn.commit()
                    return True
            except Exception as e:
                print(f"删除广告数据失败: {e}")
                return False

class AdProcessor:
    """广告处理器 - 多线程处理"""
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_ads_batch(self, ads: List[AdData], callback=None) -> List[AdData]:
        """批量处理广告数据"""
        processed_ads = []
        
        # 提交任务到线程池
        futures = {
            self.executor.submit(self.process_single_ad, ad): ad 
            for ad in ads
        }
        
        # 收集结果
        for future in as_completed(futures):
            try:
                processed_ad = future.result()
                if processed_ad:
                    processed_ads.append(processed_ad)
                    if callback:
                        callback(len(processed_ads), len(ads))
            except Exception as e:
                print(f"处理广告失败: {e}")
        
        return processed_ads
    
    def process_single_ad(self, ad: AdData) -> AdData:
        """处理单个广告 - 深度思考和逻辑推理"""
        try:
            # 模拟处理时间
            time.sleep(0.1)
            
            # 深度思考：分析广告内容
            processed_ad = self.deep_analysis(ad)
            
            # 逻辑推理：优化广告策略
            processed_ad = self.logical_reasoning(processed_ad)
            
            # 反思：检查和修复
            processed_ad = self.reflection_and_fix(processed_ad)
            
            return processed_ad
            
        except Exception as e:
            print(f"处理单个广告失败: {e}")
            return ad
    
    def deep_analysis(self, ad: AdData) -> AdData:
        """深度思考分析"""
        # 分析关键词密度
        content_lower = ad.content.lower()
        keyword_count = sum(1 for kw in ad.keywords if kw.lower() in content_lower)
        
        # 如果关键词密度不足，补充关键词
        if keyword_count < len(ad.keywords) * 0.5:  # 50%密度阈值
            ad.status = "needs_optimization"
        
        return ad
    
    def logical_reasoning(self, ad: AdData) -> AdData:
        """逻辑推理优化"""
        # 根据目标受众调整预算
        audience_budget_map = {
            "青年": 1000,
            "中年": 1500,
            "老年": 800,
            "全年龄": 1200
        }
        
        recommended_budget = audience_budget_map.get(ad.target_audience, 1000)
        
        # 逻辑推理：预算过低或过高时调整
        if ad.budget < recommended_budget * 0.5:
            ad.budget = recommended_budget * 0.8  # 调整到推荐值的80%
        elif ad.budget > recommended_budget * 2:
            ad.budget = recommended_budget * 1.5  # 调整到推荐值的150%
        
        return ad
    
    def reflection_and_fix(self, ad: AdData) -> AdData:
        """反思和修复逻辑错误"""
        # 检查标题长度
        if len(ad.title) > 50:
            ad.title = ad.title[:47] + "..."
        
        # 检查内容完整性
        if len(ad.content) < 10:
            ad.content += " [内容需要完善]"
        
        # 检查关键词数量
        if len(ad.keywords) == 0:
            ad.keywords = ["默认关键词"]
        
        # 修复预算逻辑错误
        if ad.budget <= 0:
            ad.budget = 100.0  # 设置最小预算
        
        return ad
    
    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("全自动广告系统 v1.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化组件
        self.db_manager = DatabaseManager()
        self.cache_manager = CacheManager()
        self.ad_processor = AdProcessor()
        
        # 设置UI
        self.setup_ui()
        
        # 加载数据
        self.load_ads()
    
    def setup_ui(self):
        """设置用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧面板 - 广告编辑
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右侧面板 - 广告列表
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, 2)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建状态栏
        self.statusBar().showMessage("就绪")
    
    def create_left_panel(self):
        """创建左侧编辑面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 标题
        layout.addWidget(QLabel("广告编辑"))
        
        # 表单
        form_layout = QFormLayout()
        
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("请输入广告标题")
        form_layout.addRow("标题:", self.title_edit)
        
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("请输入广告内容")
        form_layout.addRow("内容:", self.content_edit)
        
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("关键词，用逗号分隔")
        form_layout.addRow("关键词:", self.keywords_edit)
        
        self.audience_combo = QComboBox()
        self.audience_combo.addItems(["青年", "中年", "老年", "全年龄"])
        form_layout.addRow("目标受众:", self.audience_combo)
        
        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setRange(0, 999999)
        self.budget_spin.setValue(1000)
        form_layout.addRow("预算:", self.budget_spin)
        
        layout.addLayout(form_layout)
        
        # 按钮组
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("添加广告")
        self.add_btn.clicked.connect(self.add_ad)
        button_layout.addWidget(self.add_btn)
        
        self.update_btn = QPushButton("更新广告")
        self.update_btn.clicked.connect(self.update_ad)
        self.update_btn.setEnabled(False)
        button_layout.addWidget(self.update_btn)
        
        self.clear_btn = QPushButton("清空表单")
        self.clear_btn.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        # 批量处理按钮
        self.process_btn = QPushButton("批量处理广告")
        self.process_btn.clicked.connect(self.process_all_ads)
        layout.addWidget(self.process_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        return panel
    
    def create_right_panel(self):
        """创建右侧列表面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 标题和搜索
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("广告列表"))
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索广告...")
        self.search_edit.textChanged.connect(self.filter_ads)
        top_layout.addWidget(self.search_edit)
        
        layout.addLayout(top_layout)
        
        # 广告列表
        self.ads_table = QTableWidget()
        self.ads_table.setColumnCount(6)
        self.ads_table.setHorizontalHeaderLabels([
            "标题", "目标受众", "预算", "状态", "创建时间", "操作"
        ])
        self.ads_table.horizontalHeader().setStretchLastSection(True)
        self.ads_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ads_table.itemSelectionChanged.connect(self.on_ad_selected)
        
        layout.addWidget(self.ads_table)
        
        return panel
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        # 另存为功能
        save_action = QAction('另存为...', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_as)
        file_menu.addAction(save_action)
        
        # 导入功能
        import_action = QAction('导入数据...', self)
        import_action.triggered.connect(self.import_data)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu('工具')
        
        # 清理缓存
        clear_cache_action = QAction('清理缓存', self)
        clear_cache_action.triggered.connect(self.clear_cache)
        tools_menu.addAction(clear_cache_action)
        
        # 数据统计
        stats_action = QAction('数据统计', self)
        stats_action.triggered.connect(self.show_statistics)
        tools_menu.addAction(stats_action)
    
    def add_ad(self):
        """添加广告"""
        ad_data = self.get_form_data()
        if not ad_data:
            return
        
        ad_data.id = f"ad_{int(time.time())}"
        ad_data.created_at = datetime.now().isoformat()
        ad_data.updated_at = ad_data.created_at
        
        if self.db_manager.add_ad(ad_data):
            self.statusBar().showMessage("广告添加成功")
            self.load_ads()
            self.clear_form()
        else:
            QMessageBox.warning(self, "警告", "添加失败，可能是重复数据")
    
    def update_ad(self):
        """更新广告"""
        current_row = self.ads_table.currentRow()
        if current_row < 0:
            return
        
        ad_data = self.get_form_data()
        if not ad_data:
            return
        
        # 获取ID
        ad_data.id = self.current_ad_id
        ad_data.updated_at = datetime.now().isoformat()
        
        if self.db_manager.update_ad(ad_data):
            self.statusBar().showMessage("广告更新成功")
            self.load_ads()
            self.clear_form()
        else:
            QMessageBox.warning(self, "警告", "更新失败")
    
    def get_form_data(self) -> AdData:
        """获取表单数据"""
        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        keywords = [kw.strip() for kw in self.keywords_edit.text().split(',') if kw.strip()]
        audience = self.audience_combo.currentText()
        budget = self.budget_spin.value()
        
        if not title or not content:
            QMessageBox.warning(self, "警告", "请填写标题和内容")
            return None
        
        return AdData(
            id="", title=title, content=content,
            keywords=keywords, target_audience=audience, budget=budget
        )
    
    def clear_form(self):
        """清空表单"""
        self.title_edit.clear()
        self.content_edit.clear()
        self.keywords_edit.clear()
        self.audience_combo.setCurrentIndex(0)
        self.budget_spin.setValue(1000)
        self.update_btn.setEnabled(False)
        self.current_ad_id = None
    
    def load_ads(self):
        """加载广告列表"""
        ads = self.db_manager.get_all_ads()
        self.display_ads(ads)
    
    def display_ads(self, ads: List[AdData]):
        """显示广告列表"""
        self.ads_table.setRowCount(len(ads))
        
        for i, ad in enumerate(ads):
            self.ads_table.setItem(i, 0, QTableWidgetItem(ad.title))
            self.ads_table.setItem(i, 1, QTableWidgetItem(ad.target_audience))
            self.ads_table.setItem(i, 2, QTableWidgetItem(f"¥{ad.budget:.2f}"))
            self.ads_table.setItem(i, 3, QTableWidgetItem(ad.status))
            self.ads_table.setItem(i, 4, QTableWidgetItem(ad.created_at[:19]))
            
            # 操作按钮
            delete_btn = QPushButton("删除")
            delete_btn.clicked.connect(lambda checked, ad_id=ad.id: self.delete_ad(ad_id))
            self.ads_table.setCellWidget(i, 5, delete_btn)
    
    def on_ad_selected(self):
        """广告选中事件"""
        current_row = self.ads_table.currentRow()
        if current_row < 0:
            return
        
        ads = self.db_manager.get_all_ads()
        if current_row < len(ads):
            ad = ads[current_row]
            self.title_edit.setText(ad.title)
            self.content_edit.setPlainText(ad.content)
            self.keywords_edit.setText(', '.join(ad.keywords))
            
            # 设置下拉框
            index = self.audience_combo.findText(ad.target_audience)
            if index >= 0:
                self.audience_combo.setCurrentIndex(index)
            
            self.budget_spin.setValue(ad.budget)
            self.update_btn.setEnabled(True)
            self.current_ad_id = ad.id
    
    def delete_ad(self, ad_id: str):
        """删除广告"""
        reply = QMessageBox.question(self, '确认删除', '确定要删除这个广告吗？',
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.db_manager.delete_ad(ad_id):
                self.statusBar().showMessage("广告删除成功")
                self.load_ads()
                self.clear_form()
    
    def filter_ads(self):
        """过滤广告"""
        search_text = self.search_edit.text().lower()
        ads = self.db_manager.get_all_ads()
        
        if search_text:
            filtered_ads = [
                ad for ad in ads 
                if search_text in ad.title.lower() or 
                   search_text in ad.content.lower() or
                   search_text in ad.target_audience.lower()
            ]
        else:
            filtered_ads = ads
        
        self.display_ads(filtered_ads)
    
    def process_all_ads(self):
        """批量处理所有广告"""
        ads = self.db_manager.get_all_ads()
        if not ads:
            QMessageBox.information(self, "提示", "没有可处理的广告")
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(ads))
        self.progress_bar.setValue(0)
        self.process_btn.setEnabled(False)
        
        def progress_callback(completed, total):
            """进度回调"""
            self.progress_bar.setValue(completed)
            self.statusBar().showMessage(f"处理进度: {completed}/{total}")
        
        def process_thread():
            """处理线程"""
            try:
                processed_ads = self.ad_processor.process_ads_batch(ads, progress_callback)
                
                # 更新数据库
                for ad in processed_ads:
                    self.db_manager.update_ad(ad)
                
                # 更新UI（在主线程中执行）
                QTimer.singleShot(0, self.on_processing_finished)
                
            except Exception as e:
                print(f"批量处理失败: {e}")
                QTimer.singleShot(0, self.on_processing_finished)
        
        # 启动处理线程
        threading.Thread(target=process_thread, daemon=True).start()
    
    def on_processing_finished(self):
        """处理完成回调"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.statusBar().showMessage("批量处理完成")
        self.load_ads()
    
    def save_as(self):
        """另存为功能"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "另存为", "ads_export.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                ads = self.db_manager.get_all_ads()
                ads_dict = [
                    {
                        'id': ad.id, 'title': ad.title, 'content': ad.content,
                        'keywords': ad.keywords, 'target_audience': ad.target_audience,
                        'budget': ad.budget, 'status': ad.status,
                        'created_at': ad.created_at, 'updated_at': ad.updated_at
                    }
                    for ad in ads
                ]
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(ads_dict, f, ensure_ascii=False, indent=2)
                
                self.statusBar().showMessage(f"数据已保存到: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {e}")
    
    def import_data(self):
        """导入数据"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入数据", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    ads_data = json.load(f)
                
                imported_count = 0
                for ad_dict in ads_data:
                    ad = AdData(**ad_dict)
                    if self.db_manager.add_ad(ad):
                        imported_count += 1
                
                self.statusBar().showMessage(f"成功导入 {imported_count} 条广告数据")
                self.load_ads()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
    
    def clear_cache(self):
        """清理缓存"""
        reply = QMessageBox.question(self, '确认清理', '确定要清理所有缓存吗？',
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.cache_manager.cache_data.clear()
            self.cache_manager.save_cache()
            self.statusBar().showMessage("缓存已清理")
    
    def show_statistics(self):
        """显示数据统计"""
        ads = self.db_manager.get_all_ads()
        total_ads = len(ads)
        total_budget = sum(ad.budget for ad in ads)
        
        status_count = {}
        audience_count = {}
        
        for ad in ads:
            status_count[ad.status] = status_count.get(ad.status, 0) + 1
            audience_count[ad.target_audience] = audience_count.get(ad.target_audience, 0) + 1
        
        stats_text = f"""数据统计报告
        
总广告数量: {total_ads}
总预算: ¥{total_budget:.2f}
平均预算: ¥{total_budget/total_ads if total_ads > 0 else 0:.2f}

状态分布:
{chr(10).join(f'  {k}: {v}' for k, v in status_count.items())}

受众分布:
{chr(10).join(f'  {k}: {v}' for k, v in audience_count.items())}
        """
        
        QMessageBox.information(self, "数据统计", stats_text)
    
    def closeEvent(self, event):
        """关闭事件"""
        self.ad_processor.shutdown()
        self.cache_manager.save_cache()
        event.accept()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("全自动广告系统")
    app.setApplicationVersion("1.0")
    
    # 设置应用图标和样式
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()