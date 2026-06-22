"""AI 感知 - 主标签页（GUI 集成）

包含 4 个子面板：
1. 总开关 + 传感器选择（剪贴板/窗口/文件/进程）
2. 嗅探规则编辑（含启用/禁用）
3. 进程黑名单编辑
4. 后端设置 + 实时活动日志

装配 ContextSensorManager + Gatekeeper + ToastManager + ContextAgent
"""
from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QCheckBox, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QLineEdit, QTextEdit, QSpinBox,
    QFormLayout, QTabWidget, QFileDialog, QMessageBox, QComboBox, QSizePolicy, QSpacerItem,
    QDialog, QScrollArea, QAbstractItemView,
)

from context_sensor import ContextSensorManager, ContextCapsule
from context_gatekeeper import Gatekeeper, SniffRule, DEFAULT_PROCESS_BLACKLIST, DEFAULT_SNIFF_RULES
from context_toast import ToastManager, ToastIntent, ToastBubble
from context_agent import ContextAgent, EchoBackend, OpenAICompatibleBackend
from proactive_sniff import (
    ProactiveScheduler, ProactiveRunner, QuestionGenerator,
    UserProfile, ProactiveQuestion, BehaviorInterestMatcher,
)
from context_chat import ContextChatTab, MiniChatDialog, set_tavily_api_key
from i18n import t
from reminders import get_all_pending_reminders, update_reminder_status

# ---------------------------------------------------------------------------
# 后台 Worker: 拉取模型列表 (避免同步 HTTP 阻塞 UI)
# ---------------------------------------------------------------------------
class _ModelFetchWorker(QThread):
    success = Signal(list)   # [model_id, ...]
    failed = Signal(str)

    def __init__(self, base_url: str, api_key: str, timeout: float = 4.0):
        super().__init__()
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = max(2, min(timeout, 30))

    def run(self):
        try:
            import urllib.request, json as _json
            req = urllib.request.Request(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.failed.emit(str(e))
            return
        # 解析 (OpenAI 格式: {"object": "list", "data": [{"id": "..."}, ...]})
        items = data.get("data") if isinstance(data, dict) else None
        if not items and isinstance(data, list):
            items = data
        if not items:
            self.failed.emit(f"响应格式不认识:\n{str(data)[:300]}")
            return
        ids = []
        for it in items:
            if isinstance(it, dict):
                mid = it.get("id") or it.get("name") or it.get("model")
                if mid:
                    ids.append(str(mid))
            elif isinstance(it, str):
                ids.append(it)
        if not ids:
            self.failed.emit("未提取到任何模型 id")
            return
        self.success.emit(sorted(set(ids)))


try:
    from data_paths import USER_DATA_DIR
except Exception:
    USER_DATA_DIR = Path.home() / "桌面自动化助手"
if not USER_DATA_DIR.exists():
    try:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
CONFIG_FILE = USER_DATA_DIR / "context_aware_config.json"


class ContextTab(QWidget):
    """AI 感知主标签页"""

    # AI 主动推送的气泡 (同步到 AI 对话 tab)
    toast_broadcast = Signal(object)  # ToastIntent

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = False
        self._sensor_manager = ContextSensorManager()
        self._gatekeeper = Gatekeeper()
        self._toast_manager = ToastManager(self)
        self._agent = ContextAgent(backend=EchoBackend(), parent=self, infer_timeout=15.0)
        self._mini_chat_dialog = None
        self._learning_toast_timers = {}
        self._learning_toast_pending = {}
        self._learning_toast_last_shown = {}
        # 主动嗅探
        self._proactive_history = deque(maxlen=100)
        self._proactive_generator = QuestionGenerator(self._agent._backend, timeout=15.0)
        self._proactive_scheduler = ProactiveScheduler(
            self._proactive_generator, self._proactive_history, parent=self
        )
        self._proactive_runner = ProactiveRunner(self._proactive_scheduler, self._toast_manager, parent=self)
        # 行为兴趣触发器——检测到匹配关键词时立即推送
        self._behavior_matcher = BehaviorInterestMatcher(
            self._proactive_generator, self._proactive_history, parent=self
        )

        self._config = self._load_config()

        # 应用配置
        if "blacklist_extra" in self._config:
            for app in self._config["blacklist_extra"]:
                self._gatekeeper.add_to_blacklist(app)
        if "rule_overrides" in self._config:
            for r in self._config["rule_overrides"]:
                self._gatekeeper.toggle_rule(r["name"], r["enabled"])

        # 信号连接
        self._sensor_manager.captured.connect(self._on_capsule)
        self._sensor_manager.captured.connect(self._behavior_matcher.on_capsule)
        self._toast_manager.toast_clicked.connect(self._on_toast_clicked)
        # AI agent 推荐 → 走 toast + 广播到 AI 对话页 (同步)
        self._agent.intent_ready.connect(self._toast_manager.show_toast)
        self._agent.intent_ready.connect(self.toast_broadcast.emit)
        self._agent.log_signal.connect(self._append_log)
        self._behavior_matcher.log_signal.connect(self._append_log)
        self._behavior_matcher.triggered.connect(self._on_behavior_question)

        self._build_ui()
        # 全域日志窗口引用（指向主窗口 DesktopAutoWindow.log_view）
        # 这样其他 tab 按钮的 _append_log 写这里，视觉反馈才正常
        self.log_view = self.window().log_view if (
            hasattr(self, 'window') and callable(self.window) and
            self.window() and hasattr(self.window(), 'log_view')
        ) else None
        self._refresh_rule_list()
        self._refresh_blacklist_list()

    # ---- UI 构建 ----
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # 顶部：总开关
        top = QHBoxLayout()
        self.master_switch = QCheckBox(t("ctx_master_switch"))
        self.master_switch.setFont(QFont("", 11, QFont.Bold))
        self.master_switch.toggled.connect(self._on_master_toggle)
        top.addWidget(self.master_switch)

        top.addStretch()
        self.status_label = QLabel("已停止")
        self.status_label.setStyleSheet("color: #888;")
        top.addWidget(self.status_label)
        root.addLayout(top)

        # 子标签页
        sub = QTabWidget()

        # === Tab 1: 感知行为 ===
        sub.addTab(self._build_sensor_panel(), t("ctx_tab_sensor"))

        # === Tab 1: AI 对话 (调用 MCP 工具) — 默认第一项 ===
        self.context_chat_tab = ContextChatTab(self)
        self.context_chat_tab.log_signal.connect(self._append_log)
        # 初始化时同步默认后端
        self.context_chat_tab.set_backend(self._agent._backend)
        # 同步 AI 主动推送 (气泡) 到对话页
        self.toast_broadcast.connect(self.context_chat_tab.on_intent)
        # 同步 AI chat 气泡事件到 toast 管理器（仅本地显示，不广播避免循环）
        self.context_chat_tab.toast_broadcast.connect(self._toast_manager.show_toast)
        # 同步用户点击气泡
        self._toast_manager.toast_clicked.connect(self.context_chat_tab.on_toast_clicked)
        sub.addTab(self.context_chat_tab, t("ctx_tab_chat"))

        # === Tab 2: 嗅探规则 ===
        sub.addTab(self._build_rules_panel(), t("ctx_tab_rules"))

        # === Tab 3: 进程黑名单 ===
        sub.addTab(self._build_blacklist_panel(), t("ctx_tab_blacklist"))

        # === Tab 4: 后端设置 ===
        sub.addTab(self._build_backend_panel(), t("ctx_tab_backend"))

        # === Tab 5: 主动嗅探 ===
        sub.addTab(self._build_proactive_panel(), t("ctx_tab_proactive"))

        # === Tab 6: 记忆引擎 ===
        sub.addTab(self._build_memory_engine_panel(), t("ctx_tab_memory"))

        root.addWidget(sub, stretch=1)

    def _build_sensor_panel(self) -> QWidget:
        """感知行为面板——选择启用哪些传感器"""
        w = QWidget()
        layout = QVBoxLayout(w)

        gb = QGroupBox(t("ctx_sensor_box"))
        v = QVBoxLayout(gb)

        self.chk_clipboard = QCheckBox(t("ctx_chk_clipboard"))
        self.chk_clipboard.setChecked(True)
        v.addWidget(self.chk_clipboard)

        self.chk_window = QCheckBox(t("ctx_chk_window"))
        self.chk_window.setChecked(True)
        v.addWidget(self.chk_window)

        self.chk_file = QCheckBox(t("ctx_chk_file"))
        self.chk_file.setChecked(False)
        v.addWidget(self.chk_file)

        self.chk_process = QCheckBox(t("ctx_chk_process"))
        self.chk_process.setChecked(True)
        v.addWidget(self.chk_process)

        layout.addWidget(gb)

        # 文件监视路径
        path_gb = QGroupBox(t("ctx_file_watch_path"))
        pv = QVBoxLayout(path_gb)
        path_row = QHBoxLayout()
        self.path_list = QListWidget()
        self.path_list.setMaximumHeight(120)
        path_row.addWidget(self.path_list, stretch=1)

        btn_col = QVBoxLayout()
        btn_add = QPushButton(t("ctx_btn_add_dir"))
        btn_add.clicked.connect(self._on_add_path)
        btn_rm = QPushButton(t("ctx_btn_rm_dir"))
        btn_rm.clicked.connect(self._on_rm_path)
        btn_col.addWidget(btn_add)
        btn_col.addWidget(btn_rm)
        btn_col.addStretch()
        path_row.addLayout(btn_col)
        pv.addLayout(path_row)
        layout.addWidget(path_gb)

        # 行为按钮
        btn_row = QHBoxLayout()
        btn_test = QPushButton(t("ctx_btn_test_clipboard"))
        btn_test.clicked.connect(self._on_test_capture)
        btn_test_toast = QPushButton(t("ctx_btn_test_toast"))
        btn_test_toast.clicked.connect(self._on_test_toast)
        btn_clear_toasts = QPushButton(t("ctx_btn_clear_toasts"))
        btn_clear_toasts.clicked.connect(self._toast_manager.stop_all)
        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_test_toast)
        btn_row.addWidget(btn_clear_toasts)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        return w

    def _build_rules_panel(self) -> QWidget:
        """嗅探规则面板——启用/禁用 + 自定义"""
        w = QWidget()
        layout = QVBoxLayout(w)

        info = QLabel(t("ctx_clipboard_hint") + "\n"
                     "取消勾选可禁用对应规则。")
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        self.rule_list = QListWidget()
        self.rule_list.setMaximumHeight(280)
        self.rule_list.itemChanged.connect(self._on_rule_item_changed)
        layout.addWidget(self.rule_list)

        learning_gb = QGroupBox(t("ctx_learning_settings"))
        lf = QFormLayout(learning_gb)
        self.default_translate_lang_input = QLineEdit("中文")
        self.default_translate_lang_input.setPlaceholderText(t("ctx_placeholder_trans_lang"))
        self.default_translate_lang_input.editingFinished.connect(self._save_config)
        lf.addRow(t("ctx_default_trans_lang"), self.default_translate_lang_input)
        tip = QLabel("勾选规则后：检测到英文 → 推送 AI 翻译；检测到学术词汇 → 推送 AI 解释。")
        tip.setStyleSheet("color:#666;")
        lf.addRow(t("ctx_rule_tip_label"), tip)
        layout.addWidget(learning_gb)
        self._load_learning_config_into_ui()

        # 自定义规则
        custom_gb = QGroupBox(t("ctx_custom_rule"))
        cv = QFormLayout(custom_gb)
        self.rule_name_input = QLineEdit()
        self.rule_name_input.setPlaceholderText(t("ctx_placeholder_rule_name"))
        self.rule_pattern_input = QLineEdit()
        self.rule_pattern_input.setPlaceholderText(t("ctx_placeholder_pattern"))
        cv.addRow(t("ctx_rule_name"), self.rule_name_input)
        cv.addRow(t("ctx_rule_pattern"), self.rule_pattern_input)
        btn_row = QHBoxLayout()
        btn_add = QPushButton(t("ctx_btn_add_rule"))
        btn_add.clicked.connect(self._on_add_rule)
        btn_rm = QPushButton(t("ctx_btn_rm_rule"))
        btn_rm.clicked.connect(self._on_rm_rule)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_rm)
        btn_row.addStretch()
        cv.addRow("", _wrap(btn_row))
        layout.addWidget(custom_gb)

        layout.addStretch()
        return w

    def _build_blacklist_panel(self) -> QWidget:
        """进程黑名单面板"""
        w = QWidget()
        layout = QVBoxLayout(w)

        warn = QLabel(t("ctx_blacklist_hint") + "\n"
                     "密码管理器、SSH 私钥工具等建议加入。")
        warn.setStyleSheet("color: #c00;")
        layout.addWidget(warn)

        self.blacklist_list = QListWidget()
        self.blacklist_list.setMaximumHeight(280)
        layout.addWidget(self.blacklist_list)

        add_gb = QGroupBox(t("ctx_add_process"))
        av = QHBoxLayout(add_gb)
        self.blacklist_input = QLineEdit()
        self.blacklist_input.setPlaceholderText(t("ctx_placeholder_process"))
        av.addWidget(self.blacklist_input, stretch=1)
        btn_add = QPushButton(t("ctx_btn_add_rule"))
        btn_add.clicked.connect(self._on_add_blacklist)
        btn_rm = QPushButton(t("ctx_btn_rm_dir"))
        btn_rm.clicked.connect(self._on_rm_blacklist)
        av.addWidget(btn_add)
        av.addWidget(btn_rm)
        layout.addWidget(add_gb)

        layout.addStretch()
        return w

    def _build_backend_panel(self) -> QWidget:
        """后端 AI 设置面板"""
        w = QWidget()
        layout = QVBoxLayout(w)

        gb = QGroupBox(t("ctx_backend_title"))
        f = QFormLayout(gb)

        self.backend_combo = QComboBox()
        self.backend_combo.addItems([t("ctx_backend_echo"),
                                    t("ctx_backend_openai")])
        f.addRow(t("ctx_backend_type"), self.backend_combo)

        self.base_url_input = QLineEdit("http://127.0.0.1:11434/v1")
        f.addRow(t("ctx_base_url"), self.base_url_input)

        self.api_key_input = QLineEdit("EMPTY")
        f.addRow(t("ctx_api_key"), self.api_key_input)

        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.model_input.setInsertPolicy(QComboBox.NoInsert)
        # 默认保留一个占位项,用户可输入也以后拉取后覆盖
        self.model_input.addItem("qwen2.5:7b")
        self.model_input.setCurrentText("qwen2.5:7b")
        f.addRow(t("ctx_model"), self.model_input)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(2, 120)
        self.timeout_spin.setValue(15)
        self.timeout_spin.setSuffix(t("ctx_seconds_suffix"))
        f.addRow(t("ctx_timeout"), self.timeout_spin)

        self.tavily_key_input = QLineEdit()
        self.tavily_key_input.setEchoMode(QLineEdit.Password)
        self.tavily_key_input.setPlaceholderText(t("ctx_placeholder_tavily"))
        f.addRow(t("ctx_tavily_key"), self.tavily_key_input)

        layout.addWidget(gb)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton(t("ctx_btn_save_backend"))
        btn_apply.clicked.connect(self._on_apply_backend)
        btn_test = QPushButton(t("ctx_btn_test_conn"))
        btn_test.clicked.connect(self._on_test_backend)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_test)

        # 拉取模型列表
        self.btn_fetch_models = QPushButton(t("ctx_btn_fetch_models"))
        self.btn_fetch_models.setToolTip("从当前 Base URL + API Key 拉取可用模型 (OpenAI 协议: GET /v1/models)")
        self.btn_fetch_models.clicked.connect(self._on_fetch_models)
        btn_row.addWidget(self.btn_fetch_models)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 工作流交互说明
        info_gb = QGroupBox(t("ctx_workflow_interaction"))
        iv = QVBoxLayout(info_gb)
        info = QLabel("• 气泡点击后会调用 AI 推荐的工具（MCP 工具或工作流）\n"
                     "• 当前支持的工具：search_local_files / run_workflow / launch_shortcut\n"
                     "• 推荐工作流需要先在「工作流」标签页创建\n"
                     "• 整个过程可在「日志」标签页查看实时活动")
        iv.addWidget(info)
        layout.addWidget(info_gb)

        self._load_backend_config_into_ui()

        layout.addStretch()
        return w

    def _build_proactive_panel(self) -> QWidget:
        """主动嗅探面板——用户档案 + 每日次数 + 调度状态"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(5, 5, 5, 5)
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 顶部：开关
        top = QHBoxLayout()
        self.proactive_switch = QCheckBox(t("ctx_proactive_switch"))
        self.proactive_switch.setFont(QFont("", 11, QFont.Bold))
        self.proactive_switch.toggled.connect(self._on_proactive_toggle)
        top.addWidget(self.proactive_switch)
        top.addStretch()
        layout.addLayout(top)

        # 每日次数
        count_gb = QGroupBox(t("ctx_daily_count"))
        count_gb.setFont(QFont("", 10, QFont.Bold))
        count_gb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        cv = QFormLayout(count_gb)
        cv.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
        self.daily_count_spin = QSpinBox()
        self.daily_count_spin.setRange(0, 20)
        self.daily_count_spin.setValue(3)
        self.daily_count_spin.setSuffix(t("ctx_count_suffix"))
        self.daily_count_spin.valueChanged.connect(self._on_daily_count_change)
        cv.addRow(t("ctx_count_label"), self.daily_count_spin)

        self.proactive_status = QLabel("状态: 未启动")
        self.proactive_status.setStyleSheet("color: #888;")
        cv.addRow(t("ctx_proactive_status"), self.proactive_status)
        layout.addWidget(count_gb)

        # 用户档案
        profile_gb = QGroupBox(t("ctx_profile_gb"))
        pv = QFormLayout(profile_gb)

        self.profile_hobbies = QLineEdit()
        self.profile_hobbies.setPlaceholderText(t("ctx_placeholder_hobbies"))
        self.profile_hobbies.textChanged.connect(self._on_profile_change)
        pv.addRow(t("ctx_profile_hobbies"), self.profile_hobbies)

        self.profile_interests = QLineEdit()
        self.profile_interests.setPlaceholderText(t("ctx_placeholder_interests"))
        self.profile_interests.textChanged.connect(self._on_profile_change)
        pv.addRow(t("ctx_profile_interests"), self.profile_interests)

        self.profile_learning = QLineEdit()
        self.profile_learning.setPlaceholderText(t("ctx_placeholder_learning"))
        self.profile_learning.textChanged.connect(self._on_profile_change)
        pv.addRow(t("ctx_profile_learning"), self.profile_learning)

        self.profile_work = QLineEdit()
        self.profile_work.setPlaceholderText(t("ctx_placeholder_work"))
        self.profile_work.textChanged.connect(self._on_profile_change)
        pv.addRow(t("ctx_profile_work"), self.profile_work)

        self.profile_keywords = QLineEdit()
        self.profile_keywords.setPlaceholderText(t("ctx_placeholder_keywords"))
        self.profile_keywords.textChanged.connect(self._on_profile_change)
        pv.addRow(t("ctx_profile_keywords"), self.profile_keywords)

        kw_hint = QLabel(t("ctx_kw_hint"))
        kw_hint.setStyleSheet("color: #888; font-size: 11px;")
        pv.addRow("", kw_hint)

        profile_gb.setFixedHeight(profile_gb.sizeHint().height() * 2)
        layout.addWidget(profile_gb)

        # 历史问题
        history_gb = QGroupBox(t("ctx_history_gb"))
        history_gb.setFont(QFont("", 10, QFont.Bold))
        history_gb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        hv = QVBoxLayout(history_gb)
        self.proactive_history_view = QListWidget()
        self.proactive_history_view.setMaximumHeight(150)
        hv.addWidget(self.proactive_history_view)
        btn_row = QHBoxLayout()
        btn_now = QPushButton(t("ctx_btn_now"))
        btn_now.clicked.connect(self._on_proactive_now)
        btn_clear = QPushButton(t("ctx_btn_clear"))
        btn_clear.clicked.connect(self._on_proactive_clear)
        btn_row.addWidget(btn_now)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        hv.addLayout(btn_row)
        layout.addWidget(history_gb)

        # 提示
        info = QLabel(t("ctx_proactive_hint2"))
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        # 加载配置 + 启动状态轮询
        self._load_proactive_config()
        self._proactive_scheduler.log_signal.connect(self._append_log)
        self._proactive_scheduler.schedule_updated.connect(self._on_proactive_status_update)

        layout.addStretch()
        return w

    def _build_memory_engine_panel(self) -> QWidget:
        """记忆引擎面板 — Module A(基础收集) / B(每日复盘) / C(任务提醒) / D(专属日志)"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(5, 5, 5, 5)

        # ============================================================
        # Module A: 基础记忆收集
        # ============================================================
        mem_gb = QGroupBox(t("ctx_mem_master"))
        mem_gb.setFont(QFont("", 10, QFont.Bold))
        mag = QGridLayout(mem_gb)

        # 主开关
        self.mem_master_switch = QCheckBox(t("ctx_mem_master_switch"))
        self.mem_master_switch.setFont(QFont("", 10, QFont.Bold))
        self.mem_master_switch.stateChanged.connect(self._on_mem_master_toggle)
        mag.addWidget(self.mem_master_switch, 0, 0, 1, 2)

        # 状态指示
        self.mem_status_label = QLabel(t("ctx_mem_status_off"))
        self.mem_status_label.setStyleSheet("color: #c00;")
        mag.addWidget(self.mem_status_label, 1, 0, 1, 1)

        # 暂停/恢复按钮
        btn_pause_1h = QPushButton(t("ctx_mem_pause_1h"))
        btn_pause_1h.clicked.connect(lambda: self._on_mem_pause(3600))
        mag.addWidget(btn_pause_1h, 1, 1)

        btn_resume = QPushButton(t("ctx_mem_resume"))
        btn_resume.clicked.connect(self._on_mem_resume)
        mag.addWidget(btn_resume, 1, 2)

        # 采样间隔
        mag.addWidget(QLabel(t("ctx_mem_interval")), 2, 0)
        self.mem_interval_spin = QSpinBox()
        self.mem_interval_spin.setRange(1, 60)
        self.mem_interval_spin.setValue(5)
        self.mem_interval_spin.setSuffix(" " + t("ctx_mem_interval_unit"))
        self.mem_interval_spin.valueChanged.connect(self._on_mem_interval_change)
        mag.addWidget(self.mem_interval_spin, 2, 1, 1, 2)

        layout.addWidget(mem_gb)

        # ============================================================
        # Module B: AI 每日复盘
        # ============================================================
        diary_gb = QGroupBox(t("ctx_diary_gb"))
        diary_gb.setFont(QFont("", 10, QFont.Bold))
        dag = QGridLayout(diary_gb)

        # 开关
        self.diary_enable_chk = QCheckBox(t("ctx_diary_enable"))
        self.diary_enable_chk.setChecked(self._config.get("diary_enabled", True))
        self.diary_enable_chk.stateChanged.connect(self._on_diary_enable_toggle)
        dag.addWidget(self.diary_enable_chk, 0, 0, 1, 3)

        # 提醒时间
        dag.addWidget(QLabel(t("ctx_diary_time")), 1, 0)
        self.diary_hour_spin = QSpinBox()
        self.diary_hour_spin.setRange(0, 23)
        self.diary_hour_spin.setValue(int(self._config.get("diary_first_hour", 22)))
        self.diary_hour_spin.setSuffix(":00")
        self.diary_hour_spin.valueChanged.connect(self._on_diary_hour_change)
        dag.addWidget(self.diary_hour_spin, 1, 1)

        # 每日最多次数
        dag.addWidget(QLabel(t("ctx_diary_max")), 1, 2)
        self.diary_max_spin = QSpinBox()
        self.diary_max_spin.setRange(1, 10)
        self.diary_max_spin.setValue(int(self._config.get("diary_max_prompts", 2)))
        self.diary_max_spin.setSuffix(" " + t("ctx_diary_times"))
        self.diary_max_spin.valueChanged.connect(self._on_diary_max_change)
        dag.addWidget(self.diary_max_spin, 1, 3)

        # 按钮行
        btn_row_d = QHBoxLayout()
        btn_diary_now = QPushButton(t("ctx_diary_now"))
        btn_diary_now.clicked.connect(self._on_diary_generate_now)
        btn_row_d.addWidget(btn_diary_now)

        btn_diary_dir = QPushButton(t("ctx_diary_open_dir"))
        btn_diary_dir.clicked.connect(self._on_diary_open_dir)
        btn_row_d.addWidget(btn_diary_dir)
        btn_row_d.addStretch()
        dag.addLayout(btn_row_d, 2, 0, 1, 4)

        layout.addWidget(diary_gb)

        # ============================================================
        # Module C: AI 任务与主动提醒 (Phase D 占位)
        # ============================================================
        remind_gb = QGroupBox(t("ctx_remind_gb"))
        remind_gb.setFont(QFont("", 10, QFont.Bold))
        rag = QVBoxLayout(remind_gb)

        self.remind_auto_chk = QCheckBox(t("ctx_remind_auto_switch"))
        self.remind_auto_chk.setChecked(self._config.get("ai_reminder_auto", False))
        self.remind_auto_chk.stateChanged.connect(self._on_remind_auto_toggle)
        rag.addWidget(self.remind_auto_chk)

        btn_pending = QPushButton(t("ctx_remind_view_pending"))
        btn_pending.clicked.connect(self._on_remind_view_pending)
        rag.addWidget(btn_pending)

        layout.addWidget(remind_gb)

        # ============================================================
        # Module D: 记忆引擎专属日志
        # ============================================================
        log_gb = QGroupBox(t("ctx_mem_log_gb"))
        log_gb.setFont(QFont("", 10, QFont.Bold))
        log_layout = QVBoxLayout(log_gb)

        log_row = QHBoxLayout()
        btn_log_clear = QPushButton(t("ctx_mem_log_clear"))
        btn_log_clear.clicked.connect(self._on_mem_log_clear)
        log_row.addWidget(btn_log_clear)
        log_row.addStretch()
        self.mem_log_count_label = QLabel(t("ctx_mem_log_count").format(n=0))
        log_row.addWidget(self.mem_log_count_label)
        log_layout.addLayout(log_row)

        self.mem_log_view = QTextEdit()
        self.mem_log_view.setReadOnly(True)
        self.mem_log_view.setMaximumHeight(200)
        log_layout.addWidget(self.mem_log_view)

        layout.addWidget(log_gb)

        # 连接 log_bus，Module D 只显示 [MEM] 标签的记录
        try:
            from log_bus import log_bus
            self._mem_log_conn = log_bus.log_signal.connect(self._on_mem_log_bus)
        except Exception:
            pass

        layout.addStretch()
        return w

    # ---- 总开关 ----
    def _on_master_toggle(self, checked: bool):
        self._enabled = checked
        if checked:
            modes = {
                "clipboard": self.chk_clipboard.isChecked(),
                "window": self.chk_window.isChecked(),
                "file": self.chk_file.isChecked(),
                "process": self.chk_process.isChecked(),
            }
            self._sensor_manager.start(modes)
            self.status_label.setText(t("ctx_status_running"))
            self.status_label.setStyleSheet("color: #0a0;")
            self._append_log(f"[系统] 上下文感知已启动，启用模式: {modes}")
        else:
            self._sensor_manager.stop_all()
            self.status_label.setText(t("ctx_status_stopped"))
            self.status_label.setStyleSheet("color: #888;")
            self._append_log("[系统] 上下文感知已停止")

    # ---- 记忆引擎事件 (Module A) ----
    def _on_mem_master_toggle(self, checked: bool) -> None:
        # memory_engine_mgr 在 DesktopAutoWindow (self.window()) 上，不在 ContextAgent 上
        win = self.window()
        if not win or not hasattr(win, 'memory_engine_mgr') or not win.memory_engine_mgr:
            self._append_log("[MEM] 记忆引擎未就绪，请先启动应用")
            return
        if checked:
            win.memory_start()
            self.mem_status_label.setText(t("ctx_mem_status_on"))
            self.mem_status_label.setStyleSheet("color: #0a0;")
            self._append_log("[MEM] 记忆引擎已启动")
        else:
            win.memory_engine_mgr.stop()
            self.mem_status_label.setText(t("ctx_mem_status_off"))
            self.mem_status_label.setStyleSheet("color: #c00;")
            self._append_log("[MEM] 记忆引擎已停止")

    def _on_mem_pause(self, seconds: int) -> None:
        win = self.window()
        if win and hasattr(win, 'memory_pause'):
            win.memory_pause(seconds)
            self._append_log(f"[MEM] 已暂停 {seconds // 3600} 小时")

    def _on_mem_resume(self) -> None:
        win = self.window()
        if win and hasattr(win, 'memory_start'):
            win.memory_start()
            self._append_log("[MEM] 记忆引擎已恢复")

    def _on_mem_interval_change(self) -> None:
        val = self.mem_interval_spin.value()
        self._config['memory_interval_sec'] = val
        self._save_config()
        win = self.window()
        if win and hasattr(win, 'memory_engine_mgr') and win.memory_engine_mgr:
            win.memory_engine_mgr.set_interval(val)
        self._append_log(f"[MEM] 采样间隔已更新为 {val} 秒")

    def _on_mem_log_bus(self, msg: str) -> None:
        """Module D 日志: 只显示 [Memory] 标签的记录（[MemoryEngine]/[Memory]/[IdleWatcher]/[MainPoll]）"""
        if not hasattr(self, 'mem_log_view'):
            return
        # memory_engine 发: [MemoryEngine], [Memory], [IdleWatcher], [MainPoll]
        if not any(tag in msg for tag in ("[MemoryEngine]", "[Memory]", "[IdleWatcher]", "[MainPoll]")):
            return
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.mem_log_view.append(f"[{ts}] {msg}")
        # 更新计数
        count = self.mem_log_view.document().blockCount()
        if hasattr(self, 'mem_log_count_label'):
            self.mem_log_count_label.setText(t("ctx_mem_log_count").format(n=count - 1))
        # 限制行数
        if count > 300:
            cursor = self.mem_log_view.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 100)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _on_mem_log_clear(self) -> None:
        self.mem_log_view.clear()
        if hasattr(self, 'mem_log_count_label'):
            self.mem_log_count_label.setText(t("ctx_mem_log_count").format(n=0))

    # ---- 每日复盘事件 (Module B) ----
    def _on_diary_enable_toggle(self, checked: bool) -> None:
        self._config['diary_enabled'] = bool(checked)
        self._save_config()
        self._append_log(f"[MEM] 每日复盘 {'已启用' if checked else '已禁用'}")

    def _on_diary_hour_change(self) -> None:
        self._config['diary_first_hour'] = self.diary_hour_spin.value()
        self._save_config()
        self._append_log(f"[MEM] 复盘提醒时间已更新为 {self.diary_hour_spin.value()}:00")

    def _on_diary_max_change(self) -> None:
        self._config['diary_max_prompts'] = self.diary_max_spin.value()
        self._save_config()
        self._append_log(f"[MEM] 每日复盘次数已更新为 {self.diary_max_spin.value()} 次")

    def _on_diary_generate_now(self) -> None:
        from daily_diary import build_diary_prompt
        win = self.window()
        if not (win and hasattr(win, 'memory_engine_mgr') and win.memory_engine_mgr):
            self._append_log("[MEM] 立即复盘失败: 记忆引擎未启动")
            return
        if not hasattr(win.memory_engine_mgr, 'db') or not win.memory_engine_mgr.db:
            self._append_log("[MEM] 立即复盘失败: 数据库未就绪")
            return
        try:
            db = win.memory_engine_mgr.db
            sys_p, user_p = build_diary_prompt(db)
            self._append_log(f"[MEM] 复盘生成请求已提交 ({len(sys_p)} char prompt)")
            intent = ToastIntent(
                intent="📝 立即复盘",
                message="已触发立即复盘，请稍候...",
                suggested_action="generate_diary",
                action_param=None,
            )
            self._toast_manager.show_toast(intent)
            self.toast_broadcast.emit(intent)
        except Exception as e:
            self._append_log(f"[MEM] 立即复盘异常: {e}")

    def _on_diary_open_dir(self) -> None:
        diary_dir = USER_DATA_DIR / 'diary'
        if not diary_dir.exists():
            diary_dir.mkdir(parents=True, exist_ok=True)
        import subprocess
        subprocess.Popen(['explorer', str(diary_dir.resolve())])
        self._append_log(f"[MEM] 已打开日记目录: {diary_dir.resolve()}")

    # ---- 任务提醒事件 (Module C) ----
    def _on_remind_auto_toggle(self, checked: bool) -> None:
        self._config['ai_reminder_auto'] = bool(checked)
        self._save_config()
        self._append_log(f"[MEM] AI 自动创建提醒 {'已启用' if checked else '已禁用'}")

    def _on_remind_view_pending(self) -> None:
        """弹出挂起提醒查看器窗口"""
        self._append_log(f"[REM] 方法被调用")
        try:
            dlg = QDialog(self.window(), Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
            dlg.setWindowTitle(t("ctx_remind_view_pending"))
            dlg.setMinimumSize(600, 400)
        except Exception as e:
            self._append_log(f"[REM] 弹窗异常: {e}")
            QMessageBox.critical(
                self.window(),
                t("error") if hasattr(t, '__call__') else "错误",
                f"无法打开提醒查看器: {e}",
            )
            return
        main_layout = QVBoxLayout(dlg)

        # 标题栏
        title_label = QLabel(t("ctx_remind_view_pending"))
        title_label.setFont(QFont("", 11, QFont.Bold))
        main_layout.addWidget(title_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(list_container)
        main_layout.addWidget(scroll)

        def _refresh():
            # 清空旧列表
            while list_layout.count():
                item = list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            reminders = get_all_pending_reminders()
            if not reminders:
                empty_lbl = QLabel(t("ctx_no_pending_reminders") if hasattr(t, '__call__') else "暂无挂起提醒")
                empty_lbl.setAlignment(Qt.AlignCenter)
                empty_lbl.setStyleSheet("color: #888; padding: 20px;")
                list_layout.addWidget(empty_lbl)
                return

            for rem in reminders:
                card = QWidget()
                card_layout = QHBoxLayout(card)
                card_layout.setContentsMargins(4, 4, 4, 4)

                # 时间 + 内容
                info_layout = QVBoxLayout()
                time_str = rem["trigger_time"][:16].replace("T", " ")
                time_lbl = QLabel(f"🕐 {time_str}")
                time_lbl.setFont(QFont("", 9, QFont.Bold))
                content_lbl = QLabel(rem["content"][:80])
                content_lbl.setWordWrap(True)
                content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                action_lbl = QLabel(f"📌 {rem['action_type'] or 'toast'}")
                action_lbl.setFont(QFont("", 8))
                action_lbl.setStyleSheet("color: #888;")
                info_layout.addWidget(time_lbl)
                info_layout.addWidget(content_lbl)
                info_layout.addWidget(action_lbl)
                info_layout.addStretch()

                # 按钮组
                btn_layout = QVBoxLayout()
                btn_done = QPushButton("✅ 完成")
                btn_done.setFixedWidth(70)
                btn_done.clicked.connect(
                    lambda checked, rid=rem["id"]: _on_done(rid)
                )
                btn_delete = QPushButton("🗑 删除")
                btn_delete.setFixedWidth(70)
                btn_delete.setStyleSheet("QPushButton { color: #c00; }")
                btn_delete.clicked.connect(
                    lambda checked, rid=rem["id"]: _on_delete(rid)
                )
                btn_layout.addWidget(btn_done)
                btn_layout.addWidget(btn_delete)
                btn_layout.addStretch()

                card_layout.addLayout(info_layout, 1)
                card_layout.addLayout(btn_layout)

                # 分隔线
                sep = QLabel()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background: #eee;")
                list_layout.addWidget(card)
                list_layout.addWidget(sep)

        def _on_done(rid: int):
            update_reminder_status(rid, "done")
            self._append_log(f"[MEM] 提醒已完成: ID={rid}")
            _refresh()

        def _on_delete(rid: int):
            update_reminder_status(rid, "dismissed")
            self._append_log(f"[MEM] 提醒已删除: ID={rid}")
            _refresh()

        # 底部按钮栏
        bottom_layout = QHBoxLayout()
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(_refresh)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.accept)
        bottom_layout.addWidget(btn_refresh)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)
        main_layout.addLayout(bottom_layout)

        _refresh()
        dlg.exec()

    # ---- 胶囊事件 ----
    def _on_capsule(self, capsule: ContextCapsule):
        """接收到 ContextCapsule，过滤后送 AI 推理

        注意：process 启动/退出事件不走剪贴板规则，也不全量送 AI。
        它由 BehaviorInterestMatcher 根据用户档案/行为关键词过滤后再主动推送，避免日志和 AI 请求噪声。
        """
        if capsule.source == "process":
            # 行为匹配器通过独立 signal 连接会收到同一 capsule；这里不再全量记录/放行
            return

        self._append_log(f"[{capsule.source}] {capsule.foreground_window or '(无窗口)'} | "
                        f"内容前30字: {capsule.clipboard_text[:30]!r}")
        result = self._gatekeeper.check(capsule)
        if not result.passed:
            self._append_log(f"[拦截] {result.blocked_reason}")
            return

        self._append_log(f"[放行] 命中规则: {result.rule_name}")
        # 学习类规则由本地规则直接生成 AI 任务，不再送 LLM 做意图判断，避免额外推荐/重复气泡
        if capsule.source == "clipboard" and result.rule_name in ("英文文本", "学术词汇"):
            self._fallback_toast_by_rule(capsule, result.rule_name)
            return
        # 剪贴板事件: 先按规则兑底弹一条气泡, LLM 如果推荐更好会覆盖
        if capsule.source == "clipboard":
            self._agent.process(capsule)
            self._fallback_toast_by_rule(capsule, result.rule_name)

    def _on_behavior_question(self, q: ProactiveQuestion):
        """行为兴趣触发器产出的问题 → 转成气泡 + 同步到 AI 对话页"""
        # q 已在 BehaviorInterestMatcher 内写入 _proactive_history，这里只刷新 UI
        self._refresh_proactive_history()
        icon_map = {"work": "💼", "study": "📚", "hobby": "🎮", "chat": "💬"}
        intent = ToastIntent(
            intent=f"行为主动嗅探 - {q.category}",
            message=f"{icon_map.get(q.category, '💬')} {q.text}",
            suggested_action="open_chat",
            action_param=q.category,
        )
        self._toast_manager.show_toast(intent)
        self.toast_broadcast.emit(intent)

    def _open_mini_chat(self, intent: ToastIntent | None = None):
        """打开/激活小聊天窗，复用 AI 对话标签页的同一份记录。"""
        if not hasattr(self, "context_chat_tab"):
            return
        if self._mini_chat_dialog is None or not self._mini_chat_dialog.isVisible():
            self._mini_chat_dialog = MiniChatDialog(self.context_chat_tab, self)
        self._mini_chat_dialog.show()
        self._mini_chat_dialog.raise_()
        self._mini_chat_dialog.activateWindow()
        if intent is not None:
            self.context_chat_tab.on_toast_clicked(intent)

    def _fallback_toast_by_rule(self, capsule: ContextCapsule, rule_name: str) -> None:
        """兑底: 根据嗅探规则名直接弹一条气泡,不依赖 LLM

        场景: LLM 返回 need_action=false (小模型不够智能),但规则已明确
        匹配到 IP/URL/报错/路径等 → 应该帮用户推一跟动作。
        """
        text = (capsule.clipboard_text or "").strip()
        if not text:
            return
        if rule_name == "英文文本":
            lang = "中文"
            try:
                lang = self.default_translate_lang_input.text().strip() or "中文"
            except Exception:
                pass
            prompt = f"请把下面这段英文翻译成{lang}，保留专有名词，并在必要时补充一句上下文说明：\n\n{text}"
            preview = self._learning_text_preview(text)
            msg = f"📘 翻译为{lang}: {preview}"
            self._show_learning_toast(rule_name, msg, prompt)
            return
        if rule_name == "学术词汇":
            prompt = f"请解释下面内容中的学术词汇/概念：先用通俗中文解释，再给一个例子，最后列出关键词。\n\n{text}"
            preview = self._learning_text_preview(text)
            msg = f"🎓 解释: {preview}"
            self._show_learning_toast(rule_name, msg, prompt)
            return

        # 规则 -> 动作 映射表
        RULE_FALLBACK = {
            t("ctx_ip_address"):       ("launch_shortcut",  "mstsc",            f"检测到 IP {text},打开远程桌面？"),
            "报错信息":      ("search_local_files", text[:30],          "发现报错,搜索相关日志?"),
            "URL":          ("launch_shortcut",  text,                f"检测到链接,打开?"),
            "域名":         ("launch_shortcut",  "https://" + text,   f"检测到域名,打开?"),
            "Windows 路径": ("launch_shortcut",  "explorer",          f"打开路径 {text}?"),
            "Unix 路径":    ("search_local_files", text,                f"搜索路径 {text}?"),
            t("ctx_nginx_config"):   ("search_local_files", "nginx.conf",        "查找 nginx 配置?"),
            "命令行":        ("search_local_files", text,                "查找相关脚本?"),
            "单据/表格":    ("search_local_files", text[:30],          "查找单据相关文件?"),
        }
        if rule_name not in RULE_FALLBACK:
            return
        sug, param, msg = RULE_FALLBACK[rule_name]
        # 避免 LLM 已经在 intent_ready 中推过同一条 → 重复
        # 解决方案: 只在 LLM 决策后没产生 toast 的情况下 (现在 05s 后)才兑底
        # 简单点: 先用 QTimer.singleShot 延迟推, 让 LLM 先推
        def _show():
            from log_bus import log_bus
            log_bus.emit(f"[兑底] 按规则「{rule_name}」生成推荐: {msg}")
            intent = ToastIntent(
                intent=f"兑底-{rule_name}",
                message=msg,
                suggested_action=sug,
                action_param=param,
            )
            self._toast_manager.show_toast(intent)
        # 延迟 4 秒,给 LLM 先推的机会(LLM 需 3-11 秒)
        QTimer.singleShot(4000, _show)

    def _learning_text_preview(self, text: str, max_len: int = 90) -> str:
        clean = " ".join((text or "").split())
        if len(clean) <= max_len:
            return clean
        return clean[:max_len].rstrip() + "…"

    def _show_learning_toast(self, rule_name: str, msg: str, prompt: str):
        import time
        # 学习规则容易在一次复制/选择时收到多个剪贴板片段：做 debounce，并保留更长的 prompt。
        now = time.time()
        last = self._learning_toast_last_shown.get(rule_name, 0)
        if now - last < 3.0:
            self._append_log(f"[学习规则] 去重跳过: {rule_name}")
            return

        pending = self._learning_toast_pending.get(rule_name)
        if not pending or len(prompt) >= len(pending.get("prompt", "")):
            self._learning_toast_pending[rule_name] = {"msg": msg, "prompt": prompt}

        old_timer = self._learning_toast_timers.get(rule_name)
        if old_timer:
            try:
                old_timer.stop()
                old_timer.deleteLater()
            except Exception:
                pass

        timer = QTimer(self)
        timer.setSingleShot(True)

        def _show():
            from log_bus import log_bus
            data = self._learning_toast_pending.pop(rule_name, {"msg": msg, "prompt": prompt})
            self._learning_toast_timers.pop(rule_name, None)
            self._learning_toast_last_shown[rule_name] = time.time()
            log_bus.emit(f"[学习规则] 按规则「{rule_name}」生成推荐: {data['msg']}")
            intent = ToastIntent(
                intent=f"学习-{rule_name}",
                message=data["msg"],
                suggested_action="ai_prompt",
                action_param=data["prompt"],
            )
            self._toast_manager.show_toast(intent)
            self.toast_broadcast.emit(intent)
            timer.deleteLater()

        timer.timeout.connect(_show)
        self._learning_toast_timers[rule_name] = timer
        timer.start(900)

    def _inject_toast_context(self, intent: ToastIntent):
        if not hasattr(self, "context_chat_tab"):
            return
        msg = getattr(intent, "message", "") or ""
        tag = getattr(intent, "intent", "") or ""
        action = getattr(intent, "suggested_action", "") or ""
        param = getattr(intent, "action_param", "") or ""
        ctx = (
            "用户刚点击了一个桌面主动气泡。请把它当作当前对话上文，不要说你不知道气泡内容。\n"
            f"气泡类型: {tag}\n"
            f"气泡内容: {msg}\n"
            f"建议动作: {action}\n"
            f"动作参数: {param[:1000]}"
        )
        visible = " ".join((msg or tag or action or "").split())
        if len(visible) > 90:
            visible = visible[:90].rstrip() + "…"
        self.context_chat_tab.add_next_context(ctx, visible_hint=visible)

    def _on_toast_clicked(self, intent: ToastIntent):
        """用户点击了气泡 → 打开小聊天窗，并同步 AI 对话标签页记录"""
        self._append_log(f"[点击] 用户点击气泡: {intent.suggested_action}({intent.action_param})")
        action = getattr(intent, "suggested_action", "") or ""
        if action.startswith("reminder_"):
            try:
                parent = self.parent()
                handler = getattr(parent, "handle_reminder_toast_action", None)
                if handler and handler(action, getattr(intent, "action_param", "") or ""):
                    return
            except Exception as e:
                self._append_log(f"[Reminder] 点击处理失败: {e}")
        self._inject_toast_context(intent)
        # 学习规则点击后只发送一条真实 AI 请求，不再额外追加“已接受推荐/点击气泡”两段记录
        if getattr(intent, "suggested_action", "") == "ai_prompt" and hasattr(self, "context_chat_tab"):
            self._open_mini_chat(None)
            prompt = getattr(intent, "action_param", "") or ""
            if prompt:
                QTimer.singleShot(150, lambda p=prompt: self.context_chat_tab.send_text(p))
            return
        if hasattr(self, "context_chat_tab"):
            self.context_chat_tab.on_action_executed(intent)
        self._open_mini_chat(intent)

    # ---- 测试 ----
    def _on_test_capture(self):
        from PySide6.QtGui import QGuiApplication
        text = QGuiApplication.clipboard().text() or ""
        if not text:
            QMessageBox.warning(self, "测试失败", "剪贴板为空，请先复制一些内容")
            return
        cap = ContextCapsule(
            source="clipboard",
            clipboard_text=text,
            foreground_window="(测试)",
            foreground_app="test.exe",
        )
        self._on_capsule(cap)

    def _on_test_toast(self):
        """直接测试气泡渲染链路，不经过 AI/规则。"""
        intent = ToastIntent(
            intent="测试气泡渲染",
            message="这是一条测试气泡",
            suggested_action="search_local_files",
            action_param="toast test",
        )
        self._append_log("[Toast] 手动测试气泡")
        self._toast_manager.show_toast(intent)

    # ---- 路径管理 ----
    def _on_add_path(self):
        d = QFileDialog.getExistingDirectory(self, "选择要监视的目录")
        if d:
            self._sensor_manager.file.add_path(d)
            self._refresh_path_list()
            self._append_log(f"[文件] 添加监视路径: {d}")

    def _on_rm_path(self):
        item = self.path_list.currentItem()
        if item:
            path = item.text()
            self._sensor_manager.file._watcher.removePath(path)
            self._refresh_path_list()

    def _refresh_path_list(self):
        self.path_list.clear()
        for p in self._sensor_manager.file.watched_paths():
            self.path_list.addItem(p)

    # ---- 规则管理 ----
    def _refresh_rule_list(self):
        self.rule_list.blockSignals(True)
        self.rule_list.clear()
        for rule in self._gatekeeper.get_rules():
            text = f"{'✅' if rule.enabled else '⬜'} {rule.name}  |  {rule.pattern}"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if rule.enabled else Qt.Unchecked)
            item.setData(Qt.UserRole, rule.name)
            self.rule_list.addItem(item)
        self.rule_list.blockSignals(False)

    def _on_rule_item_changed(self, item: QListWidgetItem):
        name = item.data(Qt.UserRole)
        enabled = item.checkState() == Qt.Checked
        self._gatekeeper.toggle_rule(name, enabled)
        self.rule_list.blockSignals(True)
        item.setText(f"{'✅' if enabled else '⬜'} {name}  |  " + next((r.pattern for r in self._gatekeeper.get_rules() if r.name == name), ""))
        self.rule_list.blockSignals(False)
        self._save_config()

    def _on_add_rule(self):
        name = self.rule_name_input.text().strip()
        pattern = self.rule_pattern_input.text().strip()
        if not name or not pattern:
            return
        try:
            import re as _re
            _re.compile(pattern)
        except _re.error as e:
            QMessageBox.warning(self, "正则错误", f"正则表达式不合法: {e}")
            return
        self._gatekeeper.add_rule(name, pattern)
        self.rule_name_input.clear()
        self.rule_pattern_input.clear()
        self._refresh_rule_list()
        self._save_config()

    def _on_rm_rule(self):
        item = self.rule_list.currentItem()
        if item:
            name = item.data(Qt.UserRole)
            self._gatekeeper.remove_rule(name)
            self._refresh_rule_list()
            self._save_config()

    # ---- 黑名单管理 ----
    def _refresh_blacklist_list(self):
        self.blacklist_list.clear()
        for app in self._gatekeeper.get_blacklist():
            self.blacklist_list.addItem(app)

    def _on_add_blacklist(self):
        app = self.blacklist_input.text().strip()
        if app:
            self._gatekeeper.add_to_blacklist(app)
            self.blacklist_input.clear()
            self._refresh_blacklist_list()
            self._save_config()

    def _on_rm_blacklist(self):
        item = self.blacklist_list.currentItem()
        if item:
            self._gatekeeper.remove_from_blacklist(item.text())
            self._refresh_blacklist_list()
            self._save_config()

    # ---- 后端 ----
    def _on_apply_backend(self):
        self._apply_backend_from_ui(silent=False)
        self._save_config()
        QMessageBox.information(self, "应用成功", "AI 后端已切换")

    def _on_test_backend(self):
        backend = OpenAICompatibleBackend(
            base_url=self.base_url_input.text().strip(),
            api_key=self.api_key_input.text().strip(),
            model=self.model_input.currentText().strip(),
        )
        result = backend.infer("你是一个测试 AI。", "ping", timeout=self.timeout_spin.value())
        if result:
            QMessageBox.information(self, "连通成功", f"后端响应:\n{result[:200]}")
        else:
            QMessageBox.warning(self, "连通失败", "后端无响应，请检查 URL/Key/Model")

    def _on_fetch_models(self):
        """从当前 Base URL + API Key 拉取可用模型列表 (OpenAI 协议 GET /v1/models)

        走 QThread,避免 urllib 同步阻塞 UI 造成「一直拉取中」的假象。
        """
        base_url = self.base_url_input.text().strip().rstrip("/")
        api_key = self.api_key_input.text().strip() or "EMPTY"
        if not base_url:
            QMessageBox.warning(self, "提示", "请先填写 Base URL")
            return

        if hasattr(self, "_model_fetch_worker") and self._model_fetch_worker and self._model_fetch_worker.isRunning():
            QMessageBox.information(self, "提示", "上一次拉取还在进行中,请稍候...")
            return

        self.btn_fetch_models.setEnabled(False)
        self.btn_fetch_models.setText("⏳ 拉取中...")
        self._append_log(f"[后端] 拉取模型: GET {base_url}/models (后台线程)")

        self._model_fetch_worker = _ModelFetchWorker(base_url, api_key, timeout=self.timeout_spin.value())
        self._model_fetch_worker.success.connect(self._on_fetch_models_ok)
        self._model_fetch_worker.failed.connect(self._on_fetch_models_fail)
        self._model_fetch_worker.finished.connect(self._on_fetch_models_finished)
        self._model_fetch_worker.start()

    def _on_fetch_models_ok(self, ids: list):
        prev = self.model_input.currentText().strip()
        self.model_input.blockSignals(True)
        self.model_input.clear()
        self.model_input.addItems(ids)
        if prev and prev in ids:
            self.model_input.setCurrentText(prev)
        elif ids:
            self.model_input.setCurrentIndex(0)
        self.model_input.blockSignals(False)
        self._append_log(f"[后端] 拉取成功,共 {len(ids)} 个模型: {ids[:5]}{'...' if len(ids) > 5 else ''}")
        QMessageBox.information(self, "拉取成功", f"获取到 {len(ids)} 个模型, 已在下拉框中。\n请选择后点“应用设置”生效。")

    def _on_fetch_models_fail(self, err: str):
        self._append_log(f"[后端] 拉取模型失败: {err}")
        # 提示中追加常见问题原因
        hint = ""
        if "actively refused" in err or "Connection refused" in err or "refused" in err.lower():
            hint = "\n\n💡 提示:连接被拒绝,可能是后端服务没启动。\n  - Ollama: 请在另一个终端运行 `ollama serve`\n  - 本地代理: 检查代理是否在指定端口运行"
        elif "timeout" in err.lower() or "timed out" in err.lower():
            hint = "\n\n💡 提示:连接超时,请检查 URL 是否正确,服务是否可达。"
        elif "Name or service not known" in err or "getaddrinfo failed" in err:
            hint = "\n\n💡 提示:域名解析失败,请检查 Base URL 拼写。"
        QMessageBox.warning(self, "拉取失败", f"{err}{hint}")

    def _on_fetch_models_finished(self):
        self.btn_fetch_models.setEnabled(True)
        self.btn_fetch_models.setText("🔄 拉取模型列表")
        if hasattr(self, "_model_fetch_worker"):
            self._model_fetch_worker.deleteLater()
            self._model_fetch_worker = None

    # ---- 日志 ----
    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        # 1. 写本 tab 的本地 log_view (如果存在)
        if hasattr(self, 'log_view') and self.log_view:
            self.log_view.append(f"[{ts}] {msg}")
            # 限制行数 (限 300 行,减轻 QTextEdit 负担)
            if self.log_view.document().blockCount() > 300:
                cursor = self.log_view.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.movePosition(cursor.Down, cursor.KeepAnchor, 100)
                cursor.removeSelectedText()
                cursor.deleteChar()
        
        # 2. 推全局 log_bus (后台线程写文件 + Qt Signal 转发到主窗口 log)
        if not msg.startswith("[AI感知]"):
            try:
                from log_bus import log_bus
                log_bus.emit(f"[AI感知] {msg}")
            except Exception:
                pass

    # ---- 配置持久化 ----
    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _load_learning_config_into_ui(self):
        learning_cfg = self._config.get("learning", {}) if isinstance(self._config, dict) else {}
        lang = str(learning_cfg.get("default_translate_lang") or "中文")
        if hasattr(self, "default_translate_lang_input"):
            self.default_translate_lang_input.setText(lang)

    def _load_backend_config_into_ui(self):
        backend_cfg = self._config.get("backend", {}) if isinstance(self._config, dict) else {}
        if not backend_cfg:
            return
        try:
            self.backend_combo.setCurrentIndex(int(backend_cfg.get("type", self.backend_combo.currentIndex())))
        except Exception:
            pass
        if "base_url" in backend_cfg:
            self.base_url_input.setText(str(backend_cfg.get("base_url") or ""))
        if "api_key" in backend_cfg:
            self.api_key_input.setText(str(backend_cfg.get("api_key") or ""))
        if "model" in backend_cfg:
            self.model_input.setCurrentText(str(backend_cfg.get("model") or ""))
        try:
            self.timeout_spin.setValue(int(backend_cfg.get("timeout", self.timeout_spin.value())))
        except Exception:
            pass
        tavily_key = str(backend_cfg.get("tavily_api_key") or "")
        if hasattr(self, "tavily_key_input"):
            self.tavily_key_input.setText(tavily_key)
        set_tavily_api_key(tavily_key)
        self._apply_backend_from_ui(silent=True)

    def _apply_backend_from_ui(self, silent: bool = False):
        if self.backend_combo.currentIndex() == 0:
            backend = EchoBackend()
        else:
            backend = OpenAICompatibleBackend(
                base_url=self.base_url_input.text().strip(),
                api_key=self.api_key_input.text().strip(),
                model=self.model_input.currentText().strip(),
            )
        self._agent.set_backend(backend)
        set_tavily_api_key(self.tavily_key_input.text().strip())
        try:
            t = float(self.timeout_spin.value())
            self._agent._worker._infer_timeout = max(2.0, t)
        except Exception:
            pass
        self._proactive_generator.set_backend(backend)
        try:
            self._proactive_generator.set_timeout(float(self.timeout_spin.value()))
        except Exception:
            pass
        if hasattr(self, "context_chat_tab"):
            self.context_chat_tab.set_backend(backend)
        if not silent:
            self._append_log(f"[后端] 切换到: {type(backend).__name__}")
        return backend

    def _save_config(self):
        # 保留 _save_proactive_config 写入的 proactive 段，避免保存后端/规则时把用户档案覆盖掉
        cfg = dict(self._config) if isinstance(self._config, dict) else {}
        cfg.update({
            "blacklist_extra": self._gatekeeper.get_blacklist(),
            "rule_overrides": [
                {"name": r.name, "enabled": r.enabled}
                for r in self._gatekeeper.get_rules()
            ],
            "learning": {
                "default_translate_lang": self.default_translate_lang_input.text().strip() or "中文",
            },
            "backend": {
                "type": self.backend_combo.currentIndex(),
                "base_url": self.base_url_input.text(),
                "api_key": self.api_key_input.text(),
                "model": self.model_input.currentText(),
                "timeout": self.timeout_spin.value(),
                "tavily_api_key": self.tavily_key_input.text().strip(),
            },
        })
        self._config = cfg
        try:
            CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self._append_log(f"[配置] 保存失败: {e}")

    def shutdown(self):
        self._append_log("[系统] 关闭中...")
        self._save_config()
        self._sensor_manager.stop_all()
        self._toast_manager.stop_all()
        try:
            self._proactive_scheduler.stop()
        except Exception:
            pass
        self._agent.shutdown()

    # ---- 主动嗅探面板逻辑 ----
    def _on_proactive_toggle(self, checked: bool):
        if checked:
            # 主动嗅探依赖窗口/进程行为；开启时自动确保进程监听勾选
            if not self.chk_process.isChecked():
                self.chk_process.setChecked(True)
            if self._enabled:
                self._sensor_manager.start({"process": True})
            # 检查档案是否为空
            if self._proactive_scheduler.profile().is_empty():
                QMessageBox.warning(self, "提示", "请先填写用户档案（爱好/兴趣/学习/工作），否则话题主题会随机。")
            self._proactive_scheduler.start()
            self._behavior_matcher.set_enabled(True)
        else:
            self._proactive_scheduler.stop()
            self._behavior_matcher.set_enabled(False)

    def _on_daily_count_change(self, value: int):
        self._proactive_scheduler.set_daily_count(value)
        self._save_proactive_config()

    def _on_profile_change(self):
        profile = UserProfile(
            hobbies=self.profile_hobbies.text(),
            interests=self.profile_interests.text(),
            learning=self.profile_learning.text(),
            work=self.profile_work.text(),
            interest_keywords=self.profile_keywords.text(),
        )
        self._proactive_scheduler.set_profile(profile)
        self._behavior_matcher.set_profile(profile)
        self._save_proactive_config()

    def _on_proactive_now(self):
        """立即触发一次生成（调试用）"""
        profile = self._proactive_scheduler.profile()
        for attempt in range(3):
            q = self._proactive_generator.generate(profile, list(self._proactive_history))
            if q is None:
                QMessageBox.warning(self, "生成失败", "后端无响应")
                return
            if not self._proactive_scheduler._is_duplicate(q):
                self._proactive_history.append(q)
                self._refresh_proactive_history()
                # 显示为 toast
                intent = ToastIntent(
                    intent=f"主动嗅探 - {q.category}",
                    message=q.text,
                    suggested_action="proactive_question",
                    action_param=q.category,
                )
                self._toast_manager.show_toast(intent)
                return

    def _on_proactive_clear(self):
        self._proactive_history.clear()
        self._refresh_proactive_history()
        self._append_log("[主动嗅探] 历史已清空")

    def _on_proactive_status_update(self, status: dict):
        if not status["enabled"]:
            self.proactive_status.setText("状态: 未启动")
            self.proactive_status.setStyleSheet("color: #888;")
            return
        next_str = status.get("next_in") or "今天剩余次数已用完"
        self.proactive_status.setText(
            f"状态: 运行中 | 已问 {status['fired']}/{status['total']} | 下次: {next_str}"
        )
        self.proactive_status.setStyleSheet("color: #0a0;")

    def _refresh_proactive_history(self):
        self.proactive_history_view.clear()
        for q in reversed(list(self._proactive_history)[-20:]):
            icon = {"work": "💼", "study": "📚", "hobby": "🎮", "chat": "💬"}.get(q.category, "💬")
            ts = datetime.fromtimestamp(q.timestamp).strftime("%H:%M")
            self.proactive_history_view.addItem(f"{icon} [{ts}] {q.text}")

    def _load_proactive_config(self):
        cfg = self._config
        pa = cfg.get("proactive", {})
        if "daily_count" in pa:
            self.daily_count_spin.setValue(pa["daily_count"])
        prof = pa.get("profile", {})
        self.profile_hobbies.setText(prof.get("hobbies", ""))
        self.profile_interests.setText(prof.get("interests", ""))
        self.profile_learning.setText(prof.get("learning", ""))
        self.profile_work.setText(prof.get("work", ""))
        self.profile_keywords.setText(prof.get("interest_keywords", ""))
        # 初始化 scheduler 和 behavior_matcher 的 profile
        user_profile = UserProfile(
            hobbies=self.profile_hobbies.text(),
            interests=self.profile_interests.text(),
            learning=self.profile_learning.text(),
            work=self.profile_work.text(),
            interest_keywords=self.profile_keywords.text(),
        )
        self._proactive_scheduler.set_profile(user_profile)
        self._behavior_matcher.set_profile(user_profile)
        self._proactive_scheduler.set_daily_count(self.daily_count_spin.value())

    def _save_proactive_config(self):
        if "proactive" not in self._config:
            self._config["proactive"] = {}
        self._config["proactive"] = {
            "daily_count": self.daily_count_spin.value(),
            "profile": {
                "hobbies": self.profile_hobbies.text(),
                "interests": self.profile_interests.text(),
                "learning": self.profile_learning.text(),
                "work": self.profile_work.text(),
                "interest_keywords": self.profile_keywords.text(),
            },
        }
        self._save_config()


def _wrap(layout):
    """QHBoxLayout 包成 QWidget 便于嵌入 QFormLayout"""
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    w.setLayout(layout)
    return w
