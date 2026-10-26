from __future__ import annotations

import html
import json

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

from ..core.ollama_client import SYSTEM_PROMPT, OllamaClient, OllamaError, ToolBox
from . import theme as T

EXAMPLES = [
    "What's my current situation on the character banner?",
    "I have 9,600 Astrite and 12 Radiant Tides. What are my chances for the next limited character?",
    "How many pulls do I need for S1 (2 copies) with 90 % certainty?",
    "Was I lucky or unlucky on my 50/50s?",
]


class ChatWorker(QThread):
    tool_used = Signal(str, str, str)
    finished_ok = Signal(str, list)
    failed = Signal(str)

    def __init__(self, client, model, messages, toolbox):
        super().__init__()
        self.client, self.model, self.messages, self.toolbox = client, model, messages, toolbox

    def run(self):
        try:
            ans, msgs = self.client.chat(
                self.model, self.messages, self.toolbox,
                on_tool=lambda n, a, r: self.tool_used.emit(n, json.dumps(a), json.dumps(r)[:600]))
            self.finished_ok.emit(ans, msgs)
        except Exception as e:
            self.failed.emit(str(e))


class ModelLister(QThread):
    done = Signal(list, str)

    def __init__(self, host):
        super().__init__()
        self.host = host

    def run(self):
        try:
            self.done.emit(OllamaClient(self.host).list_models(), "")
        except OllamaError as e:
            self.done.emit([], str(e))


class AssistantTab(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.worker = None
        self.toolbox = ToolBox(lambda: self.state.stats, lambda: self.state.hazard(), lambda: self.state.gd)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        t = QLabel("AI Assistant (Ollama, runs locally)"); t.setObjectName("h1")
        top.addWidget(t); top.addStretch()
        top.addWidget(QLabel("Model:"))
        self.model = QComboBox(); self.model.setMinimumWidth(220)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Reload model list from Ollama")
        self.clear_btn = QPushButton("New chat")
        top.addWidget(self.model); top.addWidget(self.refresh_btn); top.addWidget(self.clear_btn)
        lay.addLayout(top)

        self.status = QLabel(); self.status.setObjectName("muted")
        lay.addWidget(self.status)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)

        ex = QHBoxLayout()
        for e in EXAMPLES:
            b = QPushButton(e if len(e) < 46 else e[:43] + "…")
            b.setToolTip(e)
            b.clicked.connect(lambda _=False, e=e: self.ask(e))
            ex.addWidget(b)
        lay.addLayout(ex)

        bottom = QHBoxLayout()
        self.input = QPlainTextEdit(); self.input.setPlaceholderText("Ask about your pulls… (Ctrl+Enter to send)")
        self.input.setFixedHeight(70)
        self.send = QPushButton("Send"); self.send.setObjectName("primary"); self.send.setFixedHeight(70)
        bottom.addWidget(self.input, 1); bottom.addWidget(self.send)
        lay.addLayout(bottom)

        self.send.clicked.connect(lambda: self.ask(self.input.toPlainText()))
        self.refresh_btn.clicked.connect(self.load_models)
        self.clear_btn.clicked.connect(self.new_chat)
        self.model.currentTextChanged.connect(lambda m: m and self.state.set("ollama_model", m))
        self.input.installEventFilter(self)
        self.new_chat()
        self.load_models()

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent, Qt
        if obj is self.input and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Return, Qt.Key_Enter) \
                and ev.modifiers() & Qt.ControlModifier:
            self.ask(self.input.toPlainText())
            return True
        return super().eventFilter(obj, ev)

    def load_models(self):
        self.status.setText("Contacting Ollama…")
        self.lister = ModelLister(self.state.get("ollama_host"))
        self.lister.done.connect(self.on_models)
        self.lister.start()

    def on_models(self, models, err):
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(models)
        saved = self.state.get("ollama_model")
        if saved in models:
            self.model.setCurrentText(saved)
        self.model.blockSignals(False)
        if err:
            self.status.setText(f"⚠ {err}\nInstall Ollama from ollama.com, then run e.g.  ollama pull qwen2.5:7b  "
                                "(a model with tool support: qwen2.5, llama3.1, mistral-nemo).")
        elif not models:
            self.status.setText("Ollama is running but has no models. Run:  ollama pull qwen2.5:7b")
        else:
            self.status.setText(f"Connected to {self.state.get('ollama_host')} · {len(models)} model(s). "
                                "Tool-capable models (qwen2.5, llama3.1…) give exact numbers.")

    def new_chat(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.view.setHtml(f"<p style='color:{T.MUTED}'>Ask anything about your Convene history. The assistant "
                          "uses the app's exact probability engine via tool calls, so the numbers are computed, "
                          "not guessed.</p>")

    def _append(self, who, text, color, markdown=False):
        self.view.append(f"<p style='margin-top:12px'><b style='color:{color}'>{who}</b></p>")
        if markdown:
            # render the model's markdown (bold, lists, tables) via a temporary document
            from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment
            doc = QTextDocument(); doc.setMarkdown(text)
            cur = self.view.textCursor()
            cur.movePosition(QTextCursor.End)
            cur.insertBlock()
            cur.insertFragment(QTextDocumentFragment(doc))
        else:
            self.view.append(f"<span>{html.escape(text).replace(chr(10), '<br>')}</span>")
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def ask(self, text: str):
        text = text.strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        model = self.model.currentText()
        if not model:
            self.status.setText("⚠ No Ollama model selected. Click ↻ after starting Ollama.")
            return
        if not self.state.pulls:
            self.status.setText("⚠ Import your pulls first (File → Import).")
        self.input.clear()
        self._append("You", text, T.BLUE)
        self.messages.append({"role": "user", "content": text})
        self.send.setEnabled(False)
        self.status.setText(f"{model} is thinking…")
        client = OllamaClient(self.state.get("ollama_host"))
        self.worker = ChatWorker(client, model, self.messages, self.toolbox)
        self.worker.tool_used.connect(lambda n, a, r: self.view.append(
            f"<span style='color:{T.MUTED}; font-size:8pt'>⚙ {html.escape(n)}({html.escape(a)}) → "
            f"{html.escape(r)}</span>"))
        self.worker.finished_ok.connect(self.on_answer)
        self.worker.failed.connect(self.on_fail)
        self.worker.start()

    def on_answer(self, ans, msgs):
        self.messages = msgs
        self._append("Assistant", ans or "(empty answer)", T.GOLD, markdown=True)
        self.send.setEnabled(True)
        self.status.setText("")

    def on_fail(self, err):
        self.messages.pop()  # drop the unanswered user message
        self._append("Error", err, T.RED)
        self.send.setEnabled(True)
        self.status.setText("")
