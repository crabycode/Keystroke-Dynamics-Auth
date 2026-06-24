from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend import (
    AuthService,
    AuthenticationResult,
    KeystrokeSample,
    KeyInterval,
    MIN_ENROLLMENT_SAMPLE_COUNT,
    calculate_dwell_time_vector_ms,
    calculate_flight_time_vector_ms,
    calculate_key_press_offsets_ms,
    calculate_total_typing_time_ms,
)

class TypingRecorder:
    MODIFIER_KEYS = {
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Meta_L",
        "Meta_R",
        "Caps_Lock",
        "Num_Lock",
    }

    EDIT_KEYS = {
        "BackSpace",
        "Delete",
        "Left",
        "Right",
        "Up",
        "Down",
        "Home",
        "End",
        "Insert",
    }

    def __init__(self, entry: ttk.Entry, hint_callback: Callable[[str], None]) -> None:
        self.entry = entry
        self.hint_callback = hint_callback
        self.presses: List[Dict[str, Any]] = []
        self.active_by_key: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
        self.held_keys = set()
        self.invalid_reason = ""
        self._bind_events()

    def _bind_events(self) -> None:
        self.entry.bind("<KeyPress>", self._on_key_press, add="+")
        self.entry.bind("<KeyRelease>", self._on_key_release, add="+")
        self.entry.bind("<<Paste>>", self._block_clipboard_action, add="+")
        self.entry.bind("<<Cut>>", self._block_clipboard_action, add="+")
        self.entry.bind("<Control-v>", self._block_clipboard_action, add="+")
        self.entry.bind("<Control-V>", self._block_clipboard_action, add="+")
        self.entry.bind("<Control-x>", self._block_clipboard_action, add="+")
        self.entry.bind("<Control-X>", self._block_clipboard_action, add="+")

    def reset(self) -> None:
        self.presses = []
        self.active_by_key = {}
        self.held_keys = set()
        self.invalid_reason = ""

    def clear(self) -> None:
        current_state = str(self.entry.cget("state"))
        if current_state == "disabled":
            self.entry.configure(state="normal")
            self.entry.delete(0, tk.END)
            self.entry.configure(state="disabled")
        else:
            self.entry.delete(0, tk.END)
        self.reset()

    def mark_invalid(self, reason: str) -> None:
        if not self.invalid_reason:
            self.invalid_reason = reason
            self.hint_callback(reason)

    def _block_clipboard_action(self, _event: tk.Event) -> str:
        self.mark_invalid("Пробата е невалидна: не използвай paste/cut по време на писане.")
        return "break"

    def _event_signature(self, event: tk.Event) -> Tuple[int, str]:
        return int(getattr(event, "keycode", 0)), str(getattr(event, "keysym", ""))

    def _has_control_modifier(self, event: tk.Event) -> bool:
        return bool(int(getattr(event, "state", 0)) & 0x4)

    def _is_modifier(self, event: tk.Event) -> bool:
        return str(getattr(event, "keysym", "")) in self.MODIFIER_KEYS

    def _is_edit_key(self, event: tk.Event) -> bool:
        return str(getattr(event, "keysym", "")) in self.EDIT_KEYS

    def _is_recordable_press(self, event: tk.Event) -> bool:
        char = str(getattr(event, "char", ""))
        return len(char) == 1 and char.isprintable()
# TODO 4 - запис на клавишни събития
    # Записване на моментите на натискане на клавишите.
    def _on_key_press(self, event: tk.Event) -> Optional[str]:
        if self._has_control_modifier(event):
            self.mark_invalid("Пробата е невалидна: не използвай Ctrl комбинации.")
            return "break"

        if self._is_edit_key(event):
            self.mark_invalid("Пробата е невалидна: въведи фиксирания низ без Backspace/Delete.")
            return None

        if self._is_modifier(event) or not self._is_recordable_press(event):
            return None

        signature = self._event_signature(event)
        if signature in self.held_keys:
            return None

        self.held_keys.add(signature)
        press = {"signature": signature, "down": time.perf_counter() * 1000, "up": None}
        self.presses.append(press)
        self.active_by_key.setdefault(signature, []).append(press)
        return None

    # Записване на моментите на отпускане на клавишите.
    def _on_key_release(self, event: tk.Event) -> None:
        signature = self._event_signature(event)
        if signature not in self.held_keys and not self._is_recordable_press(event):
            return

        queue = self.active_by_key.get(signature, [])
        if queue:
            press = queue.pop(0)
        else:
            press = next((item for item in self.presses if item["up"] is None), None)

        if press and press["up"] is None:
            press["up"] = time.perf_counter() * 1000

        self.held_keys.discard(signature)
# TODO 5
    # Преобразуване на суровите събития в биометрична проба.
    def build_keystroke_sample(self, expected_text: str) -> Tuple[Optional[KeystrokeSample], str]:
        value = self.entry.get()

        if self.invalid_reason:
            return None, self.invalid_reason

        if value != expected_text:
            return None, "Въведеният фиксиран низ не съвпада с очаквания."

        completed = [press for press in self.presses if press["up"] is not None]
        if len(completed) != len(expected_text):
            return None, "Пробата е непълна. Изчисти полето и опитай отново."

        if not completed:
            return None, "Няма записани клавишни събития."

        key_intervals = [
            KeyInterval(press_time_ms=press["down"], release_time_ms=press["up"])
            for press in completed
        ]

        return (
            KeystrokeSample(
                dwell_time_vector_ms=calculate_dwell_time_vector_ms(key_intervals),
                flight_time_vector_ms=calculate_flight_time_vector_ms(key_intervals),
                total_typing_time_ms=calculate_total_typing_time_ms(key_intervals),
                key_press_offsets_ms=calculate_key_press_offsets_ms(key_intervals),
            ),
            "",
        )


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Keystroke Dynamics Prototype")
        self.geometry("1060x760")
        self.minsize(980, 700)
        self.configure(bg="#eef2f5")

        self.service = AuthService()
        self.enrollment_context: Optional[Dict[str, Any]] = None

        self.register_username_var = tk.StringVar()
        self.register_password_var = tk.StringVar()
        self.enrollment_status_var = tk.StringVar(value="Създай потребител и започни обучение.")
        self.enrollment_hint_var = tk.StringVar(value="Фиксираният низ трябва да е поне 10 символа и без интервали.")
        self.enrollment_summary_var = tk.StringVar(value="Все още няма събрани проби.")
        self.user_count_var = tk.StringVar()

        self.login_username_var = tk.StringVar()
        self.login_password_var = tk.StringVar()
        self.login_status_var = tk.StringVar(value="Въведи потребител и фиксиран низ, за да валидираш опита за автентикация.")
        self.login_hint_var = tk.StringVar(value="По време на автентикацията не използвай Backspace или paste.")
        self.login_details_var = tk.StringVar(value="Последният резултат ще се покаже тук.")

        self._configure_styles()
        self._build_layout()
        self.refresh_user_views()
        self.render_timeline(None)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background="#eef2f5")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Headline.TLabel", background="#eef2f5", foreground="#173042", font=("Segoe UI", 20, "bold"))
        style.configure("Subhead.TLabel", background="#eef2f5", foreground="#486172", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#173042", font=("Segoe UI", 13, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#314654", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#637583", font=("Segoe UI", 9))
        style.configure("State.TLabel", background="#ffffff", foreground="#0b5563", font=("Consolas", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background="#eef2f5", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(16, 8))
        style.configure(
            "Enrollment.Horizontal.TProgressbar",
            troughcolor="#d7e0e6",
            background="#2f7d89",
            bordercolor="#d7e0e6",
            lightcolor="#2f7d89",
            darkcolor="#2f7d89",
        )

    def _build_layout(self) -> None:
        container = ttk.Frame(self, style="App.TFrame", padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Статична автентикация чрез динамиката на писане", style="Headline.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Алгоритъмът следва теорията: dwell time, flight time, общо време и индивидуален праг.",
            style="Subhead.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self.register_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=8)
        self.login_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=8)
        self.notebook.add(self.register_tab, text="Обучение")
        self.notebook.add(self.login_tab, text="Автентикация")

        self._build_register_tab()
        self._build_login_tab()

    def _build_register_tab(self) -> None:
        card = ttk.Frame(self.register_tab, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True)
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="1. Създай потребителски профил", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w", columnspan=2
        )
        ttk.Label(card, textvariable=self.user_count_var, style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", columnspan=2, pady=(4, 14)
        )

        ttk.Label(card, text="Username", style="Body.TLabel").grid(row=2, column=0, sticky="w")
        self.register_username_entry = ttk.Entry(card, textvariable=self.register_username_var, width=28)
        self.register_username_entry.grid(row=3, column=0, sticky="ew", padx=(0, 10), pady=(4, 10))

        ttk.Label(card, text="Фиксиран низ", style="Body.TLabel").grid(row=2, column=1, sticky="w")
        self.register_password_entry = ttk.Entry(card, textvariable=self.register_password_var, show="*", width=28)
        self.register_password_entry.grid(row=3, column=1, sticky="ew", pady=(4, 10))

        actions = ttk.Frame(card, style="Card.TFrame")
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Button(actions, text="Старт на обучение", style="Accent.TButton", command=self.start_enrollment).pack(
            side="left"
        )
        ttk.Button(actions, text="Нулирай", command=self.reset_enrollment).pack(side="left", padx=(8, 0))

        ttk.Separator(card, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)

        ttk.Label(card, text=f"2. Събери {MIN_ENROLLMENT_SAMPLE_COUNT} проби от фиксирания низ", style="CardTitle.TLabel").grid(
            row=6, column=0, sticky="w", columnspan=2, pady=(6, 0)
        )
        ttk.Label(card, textvariable=self.enrollment_status_var, style="State.TLabel").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(8, 4)
        )
        ttk.Label(card, textvariable=self.enrollment_hint_var, style="Muted.TLabel", wraplength=820).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        self.training_entry = ttk.Entry(card, show="*", width=36, state="disabled")
        self.training_entry.grid(row=9, column=0, sticky="ew", padx=(0, 10))

        training_actions = ttk.Frame(card, style="Card.TFrame")
        training_actions.grid(row=9, column=1, sticky="w")
        self.capture_button = ttk.Button(
            training_actions,
            text="Запази проба",
            style="Accent.TButton",
            command=self.capture_enrollment_sample,
            state="disabled",
        )
        self.capture_button.pack(side="left")
        self.clear_training_button = ttk.Button(
            training_actions,
            text="Изчисти поле",
            command=self.clear_training_field,
            state="disabled",
        )
        self.clear_training_button.pack(side="left", padx=(8, 0))

        self.enrollment_progress = ttk.Progressbar(
            card,
            style="Enrollment.Horizontal.TProgressbar",
            maximum=MIN_ENROLLMENT_SAMPLE_COUNT,
            mode="determinate",
        )
        self.enrollment_progress.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(16, 10))

        self.samples_listbox = tk.Listbox(
            card,
            height=7,
            bd=0,
            highlightthickness=1,
            relief="flat",
            background="#f7fafc",
            foreground="#274050",
            font=("Consolas", 10),
        )
        self.samples_listbox.grid(row=11, column=0, columnspan=2, sticky="nsew")
        card.rowconfigure(11, weight=1)

        ttk.Label(card, textvariable=self.enrollment_summary_var, style="Body.TLabel", wraplength=820).grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(14, 0)
        )

        self.training_recorder = TypingRecorder(self.training_entry, self.enrollment_hint_var.set)

    def _build_login_tab(self) -> None:
        card = ttk.Frame(self.login_tab, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True)
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)
        card.rowconfigure(8, weight=1)

        ttk.Label(card, text="Автентикация с текстова и поведенческа проверка", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            card,
            text="Първо се валидира фиксираният низ, след което пробата се сравнява с потребителския профил.",
            style="Muted.TLabel",
            wraplength=820,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))

        ttk.Label(card, text="Username", style="Body.TLabel").grid(row=2, column=0, sticky="w")
        self.login_username_combo = ttk.Combobox(card, textvariable=self.login_username_var, width=32)
        self.login_username_combo.grid(row=3, column=0, sticky="ew", padx=(0, 10), pady=(4, 10))

        ttk.Label(card, text="Парола / фиксиран низ", style="Body.TLabel").grid(row=2, column=1, sticky="w")
        self.login_password_entry = ttk.Entry(card, textvariable=self.login_password_var, show="*", width=32)
        self.login_password_entry.grid(row=3, column=1, sticky="ew", pady=(4, 10))

        actions = ttk.Frame(card, style="Card.TFrame")
        actions.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 14))
        ttk.Button(actions, text="Автентикация", style="Accent.TButton", command=self.attempt_login).pack(side="left")
        ttk.Button(actions, text="Изчисти", command=self.reset_login_fields).pack(side="left", padx=(8, 0))

        ttk.Label(card, textvariable=self.login_status_var, style="State.TLabel").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(card, textvariable=self.login_hint_var, style="Muted.TLabel", wraplength=820).grid(
            row=6, column=0, columnspan=2, sticky="nw", pady=(6, 4)
        )
        ttk.Label(card, textvariable=self.login_details_var, style="Body.TLabel", wraplength=820).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        self.timeline_canvas = tk.Canvas(
            card,
            width=860,
            height=290,
            bd=0,
            highlightthickness=1,
            highlightbackground="#d6dee5",
            background="#fbfcfd",
        )
        self.timeline_canvas.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(6, 0))

        self.login_recorder = TypingRecorder(self.login_password_entry, self.login_hint_var.set)

    def refresh_user_views(self) -> None:
        user_names = self.service.list_usernames()
        self.user_count_var.set(f"Регистрирани потребители: {len(user_names)}")
        self.login_username_combo["values"] = user_names

    def start_enrollment(self) -> None:
        username = self.register_username_var.get().strip()
        fixed_text = self.register_password_var.get()
        is_valid, error = self.service.validate_registration_inputs(username, fixed_text)

        if not is_valid:
            self.enrollment_status_var.set(error)
            self.enrollment_hint_var.set("Коригирай полетата горе и стартирай обучението отново.")
            return

        if self.service.user_exists(username):
            should_overwrite = messagebox.askyesno(
                "Съществуващ потребител",
                f'Потребител "{username}" вече съществува. Да бъде ли презаписан с нов шаблон?',
            )
            if not should_overwrite:
                return

        self.enrollment_context = {"username": username, "fixed_text": fixed_text, "samples": []}
        self.register_username_entry.configure(state="disabled")
        self.register_password_entry.configure(state="disabled")
        self.training_entry.configure(state="normal")
        self.capture_button.configure(state="normal")
        self.clear_training_button.configure(state="normal")
        self.training_recorder.clear()
        self.samples_listbox.delete(0, tk.END)
        self.enrollment_progress["value"] = 0
        self.enrollment_status_var.set(
            f"Проба 1/{MIN_ENROLLMENT_SAMPLE_COUNT}: въведи фиксирания низ точно както е зададен и натисни 'Запази проба'."
        )
        self.enrollment_hint_var.set("Не използвай Backspace/Delete и не поставяй текст с paste.")
        self.enrollment_summary_var.set("Очаквам първата проба.")
        self.training_entry.focus_set()

    def reset_enrollment(self) -> None:
        self.enrollment_context = None
        self.register_username_entry.configure(state="normal")
        self.register_password_entry.configure(state="normal")
        self.training_entry.configure(state="disabled")
        self.capture_button.configure(state="disabled")
        self.clear_training_button.configure(state="disabled")
        self.register_username_var.set("")
        self.register_password_var.set("")
        self.training_recorder.clear()
        self.samples_listbox.delete(0, tk.END)
        self.enrollment_progress["value"] = 0
        self.enrollment_status_var.set("Създай потребител и започни обучение.")
        self.enrollment_hint_var.set("Фиксираният низ трябва да е поне 10 символа и без интервали.")
        self.enrollment_summary_var.set("Все още няма събрани проби.")
        self.register_username_entry.focus_set()

    def clear_training_field(self) -> None:
        self.training_recorder.clear()
        if self.enrollment_context:
            next_index = len(self.enrollment_context["samples"]) + 1
            self.enrollment_hint_var.set("Полето е изчистено. Въведи пробата отново без корекции.")
            self.enrollment_status_var.set(f"Проба {next_index}/{MIN_ENROLLMENT_SAMPLE_COUNT}: чакам валидна проба.")
            self.training_entry.focus_set()

    # Отрязък 20: Записване на една обучаваща проба и обновяване на профила.
    def capture_enrollment_sample(self) -> None:
        if not self.enrollment_context:
            self.enrollment_status_var.set("Стартирай обучение преди да записваш проби.")
            return

        sample, error = self.training_recorder.build_keystroke_sample(self.enrollment_context["fixed_text"])
        if error:
            self.enrollment_status_var.set(error)
            return

        self.enrollment_context["samples"].append(sample)
        sample_number = len(self.enrollment_context["samples"])
        self.enrollment_progress["value"] = sample_number
        self.samples_listbox.insert(tk.END, f"Проба {sample_number}: {self.service.summarize_sample(sample)}")
        self.training_recorder.clear()

        if sample_number < MIN_ENROLLMENT_SAMPLE_COUNT:
            next_number = sample_number + 1
            self.enrollment_status_var.set(
                f"Проба {next_number}/{MIN_ENROLLMENT_SAMPLE_COUNT}: запазена е валидна проба, въведи следващата."
            )
            self.enrollment_hint_var.set("Опитай се да пишеш със сходно темпо и без паузи.")
            self.enrollment_summary_var.set(
                f"Събрани проби: {sample_number}/{MIN_ENROLLMENT_SAMPLE_COUNT}. "
                f"Последната проба е {self.service.summarize_sample(sample)}."
            )
            self.training_entry.focus_set()
            return

        self.finish_enrollment()

    def finish_enrollment(self) -> None:
        if not self.enrollment_context:
            return

        username = self.enrollment_context["username"]
        fixed_text = self.enrollment_context["fixed_text"]
        samples = self.enrollment_context["samples"]
        user_profile = self.service.enroll_user(username, fixed_text, samples)
        self.refresh_user_views()

        self.enrollment_summary_var.set(
            "Профилът е записан. "
            f"Праг: {user_profile.acceptance_threshold:.2f} | "
            f"Средно dwell: {sum(user_profile.dwell_time_mean_vector_ms) / len(user_profile.dwell_time_mean_vector_ms):.0f} ms | "
            f"Средно flight: {sum(user_profile.flight_time_mean_vector_ms) / len(user_profile.flight_time_mean_vector_ms):.0f} ms."
        )
        self.login_username_var.set(username)
        self.enrollment_status_var.set(
            f'Потребител "{username}" е създаден успешно. Можеш веднага да тестваш автентикация.'
        )
        self.enrollment_hint_var.set("Обучението приключи успешно.")
        messagebox.showinfo(
            "Обучението завърши",
            f'Потребител "{username}" е записан. Превключи към таба за автентикация, за да тестваш системата.',
        )

        self.training_entry.configure(state="disabled")
        self.capture_button.configure(state="disabled")
        self.clear_training_button.configure(state="disabled")
        self.register_username_entry.configure(state="normal")
        self.register_password_entry.configure(state="normal")
        self.training_recorder.clear()
        self.register_username_var.set("")
        self.register_password_var.set("")
        self.enrollment_context = None
        self.notebook.select(self.login_tab)

    def reset_login_fields(self) -> None:
        self.login_password_var.set("")
        self.login_recorder.clear()
        self.login_status_var.set("Въведи потребител и фиксиран низ, за да валидираш опита за автентикация.")
        self.login_hint_var.set("По време на автентикацията не използвай Backspace или paste.")
        self.login_details_var.set("Последният резултат ще се покаже тук.")
        self.render_timeline(None)
        self.login_password_entry.focus_set()

    def fail_login(self, result: AuthenticationResult) -> None:
        self.login_status_var.set(result.status_message)
        self.login_hint_var.set(result.hint_message)
        self.login_details_var.set(result.details_message or "Няма валиден биометричен резултат за тази проба.")
        self.login_password_var.set("")
        self.login_recorder.clear()
        self.render_timeline(None)
        self.login_password_entry.focus_set()

    # Отрязък 22: Автентикация на нова проба спрямо обучен профил.
    def attempt_login(self) -> None:
        username = self.login_username_var.get().strip()
        fixed_text = self.login_password_var.get()

        precheck_result = self.service.validate_login_identity(username, fixed_text)
        if precheck_result is not None:
            self.fail_login(precheck_result)
            return

        sample, error = self.login_recorder.build_keystroke_sample(fixed_text)
        if error:
            self.fail_login(AuthenticationResult(False, "Невалидна биометрична проба.", error, ""))
            return

        result = self.service.authenticate_login_attempt(username, fixed_text, sample)
        self.login_status_var.set(result.status_message)
        self.login_hint_var.set(result.hint_message)
        self.login_details_var.set(result.details_message or "Няма валиден биометричен резултат за тази проба.")
        self.login_password_var.set("")
        self.login_recorder.clear()
        self.render_timeline(result.sample)
        self.login_password_entry.focus_set()

    def render_timeline(self, sample: Optional[KeystrokeSample]) -> None:
        canvas = self.timeline_canvas
        canvas.delete("all")

        width = int(canvas["width"])
        height = int(canvas["height"])
        canvas.create_rectangle(0, 0, width, height, outline="", fill="#fbfcfd")

        if not sample or not sample.dwell_time_vector_ms:
            canvas.create_text(
                width / 2,
                height / 2,
                text="Последната валидна проба за автентикация ще се визуализира тук.",
                fill="#708494",
                font=("Segoe UI", 12),
            )
            return

        left = 88
        top = 30
        row_height = max(18, min(32, int((height - 80) / max(len(sample.dwell_time_vector_ms), 1))))
        usable_width = width - left - 32
        max_time = max(
            offset + dwell_time
            for offset, dwell_time in zip(sample.key_press_offsets_ms, sample.dwell_time_vector_ms)
        )
        max_time = max(max_time, 1.0)

        canvas.create_text(
            18,
            12,
            anchor="w",
            text="Timeline на последната проба",
            fill="#173042",
            font=("Segoe UI", 12, "bold"),
        )
        canvas.create_text(
            18,
            height - 18,
            anchor="w",
            text="Синьо = задържане на клавиш | Червено = пауза между клавиши | Лилаво = overlap",
            fill="#6a7b88",
            font=("Segoe UI", 9),
        )

        for index, (offset, dwell_time) in enumerate(zip(sample.key_press_offsets_ms, sample.dwell_time_vector_ms)):
            y = top + index * row_height
            baseline_y = y + max(8, row_height // 2 - 1)
            start_x = left + (offset / max_time) * usable_width
            end_x = left + ((offset + dwell_time) / max_time) * usable_width

            canvas.create_text(18, baseline_y, anchor="w", text=f"K{index + 1}", fill="#304b59", font=("Consolas", 10))
            canvas.create_rectangle(left, y + 2, width - 18, y + row_height - 10, outline="", fill="#e8eef2")
            canvas.create_rectangle(
                start_x,
                y + 2,
                max(end_x, start_x + 3),
                y + row_height - 10,
                outline="",
                fill="#2f7d89",
            )

            if index < len(sample.flight_time_vector_ms):
                next_offset = sample.key_press_offsets_ms[index + 1]
                next_x = left + (next_offset / max_time) * usable_width
                flight_color = "#b76544" if sample.flight_time_vector_ms[index] >= 0 else "#895e9d"
                canvas.create_line(end_x, baseline_y, next_x, baseline_y, fill=flight_color, width=2)

        axis_y = top + len(sample.dwell_time_vector_ms) * row_height + 8
        canvas.create_line(left, axis_y, width - 18, axis_y, fill="#95a6b2")
        for tick in range(5):
            tick_ratio = tick / 4
            x = left + tick_ratio * usable_width
            label_ms = max_time * tick_ratio
            canvas.create_line(x, axis_y, x, axis_y + 6, fill="#95a6b2")
            canvas.create_text(x, axis_y + 18, text=f"{label_ms:.0f} ms", fill="#5f7280", font=("Segoe UI", 9))


if __name__ == "__main__":
    app = App()
    app.mainloop()
