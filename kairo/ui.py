"""Small optional Tk desktop UI for text commands and API-key entry."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .engine import Engine
from .models import verify_models
from .secrets import set_secret


def launch() -> None:
    window = tk.Tk()
    window.title("Kairo · Prototype")
    window.geometry("720x560")
    workers = ThreadPoolExecutor(max_workers=1)
    engine = Engine()
    tabs = ttk.Notebook(window)
    tabs.pack(fill="both", expand=True, padx=12, pady=12)

    home = ttk.Frame(tabs, padding=14)
    tabs.add(home, text="Assistant")
    output = scrolledtext.ScrolledText(home, height=18, wrap="word", state="disabled")
    output.pack(fill="both", expand=True)
    request = ttk.Entry(home)
    request.pack(fill="x", pady=8)
    remote = tk.BooleanVar(value=False)
    chat = tk.BooleanVar(value=False)
    ttk.Checkbutton(home, text="Use paired desktop", variable=remote).pack(anchor="w")
    ttk.Checkbutton(home, text="Ask local Qwen directly", variable=chat).pack(anchor="w")

    def append(message: str) -> None:
        output.configure(state="normal")
        output.insert("end", message + "\n\n")
        output.configure(state="disabled")
        output.see("end")

    def submit(event=None) -> None:
        prompt = request.get().strip()
        if not prompt:
            return
        request.delete(0, "end")
        append("You: " + prompt)
        is_remote, is_chat = remote.get(), chat.get()
        def work() -> None:
            try:
                engine.remote = is_remote
                result = engine.ask(prompt, chat=is_chat)
                message = f"Kairo: {result.text}\n[{result.route}; {result.location}]"
            except Exception as exc:
                message = f"Kairo: {exc}"
            window.after(0, append, message)
        workers.submit(work)

    ttk.Button(home, text="Send", command=submit).pack(anchor="e", pady=8)
    request.bind("<Return>", submit)

    voice_state = {"service": None, "thread": None}

    def start_voice() -> None:
        if voice_state["thread"] and voice_state["thread"].is_alive():
            return
        from .voice import VoiceService
        service = VoiceService(remote=remote.get(), on_output=lambda msg: window.after(0, append, msg))
        voice_state["service"] = service
        def run() -> None:
            try:
                service.listen()
            except Exception as exc:
                window.after(0, append, f"Voice: {exc}")
        voice_state["thread"] = threading.Thread(target=run, daemon=True)
        voice_state["thread"].start()

    voice_buttons = ttk.Frame(home)
    voice_buttons.pack(anchor="w")
    ttk.Button(voice_buttons, text="Start voice", command=start_voice).pack(side="left", padx=3)
    ttk.Button(voice_buttons, text="Stop voice", command=lambda: voice_state["service"].stop_event.set()
               if voice_state["service"] else None).pack(side="left", padx=3)

    browser = ttk.Frame(tabs, padding=14)
    tabs.add(browser, text="Browser")
    ttk.Label(browser, text="Kairo uses its own browser profile. Use paired desktop above to control that computer.",
              wraplength=620).pack(anchor="w")
    url = ttk.Entry(browser)
    url.pack(fill="x", pady=8)
    browser_output = scrolledtext.ScrolledText(browser, height=11, wrap="word", state="disabled")
    browser_output.pack(fill="both", expand=True)

    def show_browser(message: str) -> None:
        browser_output.configure(state="normal")
        browser_output.insert("end", message + "\n\n")
        browser_output.configure(state="disabled")
        browser_output.see("end")

    def browse(action: str, args: dict, risky: bool = False) -> bool:
        if risky and not messagebox.askyesno("Confirm browser action", f"Run {action} on the current page?"):
            return False
        is_remote = remote.get()
        def work() -> None:
            try:
                engine.remote = is_remote
                response = engine.tool(action, args, confirmed=risky).text
            except Exception as exc:
                response = str(exc)
            window.after(0, show_browser, response)
        workers.submit(work)
        return True

    ttk.Button(browser, text="Open URL", command=lambda: browse("browser_navigate", {"url": url.get()})).pack(anchor="w")
    ttk.Button(browser, text="Read page", command=lambda: browse("browser_read", {})).pack(anchor="w", pady=6)
    role = ttk.Combobox(browser, values=["button", "link", "tab", "checkbox", "radio", "menuitem"], state="readonly")
    role.set("button")
    role.pack(fill="x")
    element_name = ttk.Entry(browser)
    element_name.pack(fill="x", pady=4)
    ttk.Button(browser, text="Click named element", command=lambda: browse(
        "browser_click", {"role": role.get(), "name": element_name.get()}, risky=True)).pack(anchor="w")
    label = ttk.Entry(browser)
    label.pack(fill="x", pady=4)
    value = ttk.Entry(browser, show="•")
    value.pack(fill="x", pady=4)
    def fill() -> None:
        arguments = {"label": label.get(), "text": value.get()}
        if browse("browser_fill", arguments, risky=True):
            value.delete(0, "end")
    ttk.Button(browser, text="Fill labeled field", command=fill).pack(anchor="w")

    settings = ttk.Frame(tabs, padding=18)
    tabs.add(settings, text="Models & settings")
    try:
        status = verify_models()
    except Exception as exc:
        status = {"error": str(exc)}
    ttk.Label(settings, text=f"Local model files: {status}", wraplength=620).pack(anchor="w", pady=8)
    ttk.Label(settings, text="Jev API key (only used when explicitly allowed)").pack(anchor="w", pady=8)
    secret = ttk.Entry(settings, show="•", width=52)
    secret.pack(anchor="w", fill="x")

    def save_key() -> None:
        if not secret.get():
            return
        try:
            set_secret("jev", secret.get())
            secret.delete(0, "end")
            messagebox.showinfo("Kairo", "Key saved in your operating system keyring.")
        except Exception as exc:
            messagebox.showerror("Kairo", str(exc))

    ttk.Button(settings, text="Save key", command=save_key).pack(anchor="e", pady=10)
    ttk.Label(settings, text="Use 'kairo models install-laya', 'install-qwen', and 'install-voice' for local weights.\n"
              "Cloud requests are disabled by default.", wraplength=620).pack(anchor="w", pady=12)

    def close() -> None:
        if voice_state["service"]:
            voice_state["service"].stop_event.set()
        engine.close()
        workers.shutdown(wait=False, cancel_futures=True)
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.mainloop()
