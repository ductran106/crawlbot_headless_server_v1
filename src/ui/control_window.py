import threading

from ..utils.logger import log, logging
from ..utils.signals import request_graceful_shutdown, is_terminating

_control_thread = None
_control_stop_event = None
_control_state = {
    "root": None,
    "button": None,
    "status_var": None,
}


def _run_window(stop_event):
    try:
        import tkinter as tk
    except Exception as e:
        log(f"Không thể khởi tạo Crawlbot Control UI (tkinter unavailable): {str(e)}", level=logging.WARNING)
        return

    root = tk.Tk()
    root.title("Crawlbot Control")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.geometry("260x110+20+20")

    status_var = tk.StringVar(value="Crawler đang chạy")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    title = tk.Label(frame, text="Crawlbot Control", font=("Arial", 11, "bold"))
    title.pack(anchor="w")

    status = tk.Label(frame, textvariable=status_var, fg="#555")
    status.pack(anchor="w", pady=(6, 10))

    def on_stop():
        requested = request_graceful_shutdown(reason="crawlbot_control_button")
        status_var.set("Đang dừng an toàn...")
        try:
            stop_btn.config(state="disabled")
        except Exception:
            pass
        if requested:
            log("Người dùng bấm Crawlbot Control -> yêu cầu dừng an toàn.", level=logging.WARNING)

    stop_btn = tk.Button(
        frame,
        text="Dừng an toàn & đóng Chrome",
        command=on_stop,
        bg="#c62828",
        fg="white",
        activebackground="#b71c1c",
        activeforeground="white",
        relief="raised",
        padx=10,
        pady=8,
    )
    stop_btn.pack(fill="x")

    _control_state["root"] = root
    _control_state["button"] = stop_btn
    _control_state["status_var"] = status_var

    def pump():
        if stop_event.is_set():
            try:
                root.destroy()
            except Exception:
                pass
            return
        if is_terminating():
            status_var.set("Đang dừng an toàn...")
            try:
                stop_btn.config(state="disabled")
            except Exception:
                pass
        root.after(250, pump)

    def on_close():
        # Đóng cửa sổ control không đồng nghĩa stop crawler.
        stop_event.set()
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(250, pump)
    root.mainloop()


def start_control_window():
    global _control_thread, _control_stop_event
    if _control_thread and _control_thread.is_alive():
        return False
    _control_stop_event = threading.Event()
    _control_thread = threading.Thread(
        target=_run_window,
        args=(_control_stop_event,),
        name="crawlbot-control-window",
        daemon=True,
    )
    _control_thread.start()
    log("Đã khởi động Crawlbot Control window", level=logging.INFO)
    return True


def stop_control_window(wait=False, timeout=2.0):
    global _control_thread, _control_stop_event
    if _control_stop_event:
        _control_stop_event.set()
    if wait and _control_thread and _control_thread.is_alive():
        _control_thread.join(timeout=timeout)
    return True
