from __future__ import annotations

import html
import json

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from ..core.ollama_client import PERSONAS, OllamaClient, OllamaError, ToolBox, system_prompt
from .i18n import tr
from . import theme as T

EXAMPLES = [
    "What's my current situation on the character banner?",
    "I have 9,600 Astrite and 12 Radiant Tides. What are my chances for the next limited character?",
    "How many pulls do I need for S1 (2 copies) with 90 % certainty?",
    "Was I lucky or unlucky on my 50/50s?",
    "Can I get Lynae S1 and her weapon with 25,000 Astrite?",
    "What are the best weapons for Hsin?",
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
        self.messages = [{"role": "system", "content": system_prompt(state.get("persona"))}]
        self.worker = None
        self.toolbox = ToolBox(lambda: self.state.stats, lambda: self.state.hazard(), lambda: self.state.gd,
                               lambda: self.state.prydwen if self.state.prydwen_on() else None,
                               lambda: self.state.owned_snapshot)
        self.toolbox.redeemed = lambda: list(self.state.get("redeemed_codes") or [])
        self.toolbox.income = lambda: self.income_snapshot
        self.toolbox.rag_dirs = lambda: self.rag_snapshot
        self.income_snapshot = {"astrite_per_day": 0.0}
        self.rag_snapshot = (None, None, None)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        top = QHBoxLayout()
        t = QLabel("AI Assistant (Ollama, runs locally)"); t.setObjectName("h1")
        top.addWidget(t); top.addStretch()
        top.addWidget(QLabel("Persona:"))
        self.persona = QComboBox()
        for k, (label, _) in PERSONAS.items():
            self.persona.addItem(label, k)
        self.persona.setCurrentIndex(max(0, self.persona.findData(state.get("persona"))))
        self.persona.currentIndexChanged.connect(self._persona)
        top.addWidget(self.persona)
        top.addSpacing(12)
        top.addWidget(QLabel("Model:"))
        self.model = QComboBox(); self.model.setMinimumWidth(220)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Reload model list from Ollama")
        self.clear_btn = QPushButton("New chat")
        self.summary_btn = QPushButton("Weekly summary")
        self.summary_btn.clicked.connect(self.weekly)
        self.bench_btn = QPushButton("Benchmark models…")
        self.bench_btn.setToolTip("Ask every installed model the same questions about your data and score them")
        self.bench_btn.clicked.connect(self.benchmark)
        top.addWidget(self.model); top.addWidget(self.refresh_btn); top.addWidget(self.clear_btn)
        top.addWidget(self.summary_btn); top.addWidget(self.bench_btn)
        lay.addLayout(top)

        self.status = QLabel(); self.status.setObjectName("muted")
        lay.addWidget(self.status)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        lay.addWidget(self.view, 1)

        ex = QHBoxLayout()
        for e in EXAMPLES[:4]:
            b = QPushButton(e if len(e) < 46 else e[:43] + "…")
            b.setToolTip(e)
            b.clicked.connect(lambda _=False, e=e: self.ask(e))
            ex.addWidget(b)
        lay.addLayout(ex)
        ex2 = QHBoxLayout()
        for e in EXAMPLES[4:]:
            b = QPushButton(e if len(e) < 60 else e[:57] + "…")
            b.setToolTip(e)
            b.clicked.connect(lambda _=False, e=e: self.ask(e))
            ex2.addWidget(b)
        ex2.addStretch()
        notes = QLabel("Add your own notes (.md/.txt) to the notes folder (Settings → Open notes folder); "
                       "the assistant searches them.")
        notes.setObjectName("muted")
        ex2.addWidget(notes)
        lay.addLayout(ex2)

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

    def shutdown(self, ms: int = 6000):
        """Wait for background requests to Ollama, so quitting never tears down a running thread."""
        for th in (getattr(self, "lister", None), self.worker):
            if th is not None and th.isRunning():
                th.wait(ms)

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

    def _persona(self):
        self.state.set("persona", self.persona.currentData())
        self.new_chat()

    def weekly(self):
        from .dialogs import WeeklySummaryDialog
        self._wd = WeeklySummaryDialog(self.state, self)
        self._wd.show()

    def benchmark(self):
        models = [self.model.itemText(i) for i in range(self.model.count())]
        if not models:
            self.status.setText("⚠ No Ollama models found. Start Ollama and click ↻ first.")
            return
        self._snapshot()
        BenchmarkDialog(self.state, models, self.toolbox, self).exec()

    def _snapshot(self):
        """Values the worker thread reads (it must not touch SQLite)."""
        self.income_snapshot = self.state.income_rate()
        self.rag_snapshot = (self.state.notes_dir, self.state.prydwen.dir if self.state.prydwen_on() else None,
                             self.state.gd.raw)

    def new_chat(self):
        self.messages = [{"role": "system", "content": system_prompt(self.state.get("persona"))}]
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
        self._snapshot()
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


class BenchmarkWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(object)

    def __init__(self, host, models, toolbox, system):
        super().__init__()
        self.host, self.models, self.toolbox, self.system = host, models, toolbox, system
        self._stop = False

    def run(self):
        from ..core import benchmark
        res = benchmark.run(OllamaClient(self.host, timeout=180), self.models, self.toolbox, system=self.system,
                            progress=self.progress.emit, stop=lambda: self._stop)
        self.finished_ok.emit(res)


class BenchmarkDialog(QDialog):
    def __init__(self, state, models, toolbox, parent=None):
        super().__init__(parent)
        from ..core import benchmark
        self.state, self.toolbox = state, toolbox
        self.setWindowTitle("Benchmark Ollama models")
        self.resize(760, 560)
        v = QVBoxLayout(self)
        info = QLabel("Every selected model gets the same questions about <b>your</b> data. The right answers are "
                      "computed first by the app's exact engine; a model scores when its answer contains the right "
                      "number. Also measured: did it call the right tool, and how long did it take.")
        info.setWordWrap(True)
        v.addWidget(info)
        self.list = QListWidget()
        for m in models:
            it = QListWidgetItem(m); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked)
            self.list.addItem(it)
        self.list.setMaximumHeight(120)
        v.addWidget(self.list)
        self.questions = benchmark.build_questions(toolbox)
        q = QLabel("Questions: " + " · ".join(f"{i + 1}. {x.text}" for i, x in enumerate(self.questions)))
        q.setWordWrap(True); q.setObjectName("muted")
        v.addWidget(q)
        self.out = QTextBrowser()
        v.addWidget(self.out, 1)
        row = QHBoxLayout()
        self.status = QLabel(); self.status.setObjectName("muted")
        self.go = QPushButton("Run benchmark"); self.go.setObjectName("primary"); self.go.clicked.connect(self.start)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False); self.stop_btn.clicked.connect(self.stop)
        row.addWidget(self.status, 1); row.addWidget(self.stop_btn); row.addWidget(self.go)
        v.addLayout(row)
        self.worker = None

    def start(self):
        models = [self.list.item(i).text() for i in range(self.list.count())
                  if self.list.item(i).checkState() == Qt.Checked]
        if not models:
            return
        self.go.setEnabled(False); self.stop_btn.setEnabled(True)
        self.worker = BenchmarkWorker(self.state.get("ollama_host"), models, self.toolbox,
                                      system_prompt(self.state.get("persona")))
        self.worker.progress.connect(self.status.setText)
        self.worker.finished_ok.connect(self.done)
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker._stop = True
            self.status.setText("Stopping after the current question…")

    def done(self, results):
        from ..core import benchmark
        self.go.setEnabled(True); self.stop_btn.setEnabled(False)
        self.status.setText("Done.")
        md = "### Results\n\n" + benchmark.report(results) + "\n\n### Answers\n\n"
        for r in results:
            for s in r.scores:
                mark = "✅" if s.correct else "❌"
                tool = "🔧" if s.used_tool else "–"
                ans = (s.error or s.answer or "(empty)").replace("\n", " ")[:220]
                md += f"- {mark} {tool} **{r.model}** · {s.question} *(expected {s.expected:g})*: {ans} ({s.seconds:.1f} s)\n"
        self.out.setMarkdown(md)

    def closeEvent(self, ev):
        if self.worker and self.worker.isRunning():
            self.worker._stop = True
            self.worker.wait(200)
        super().closeEvent(ev)
