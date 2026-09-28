# -*- coding: utf-8 -*-
"""공통 헬퍼: 콘솔 로그 창(왼쪽)과 브라우저 창(오른쪽)으로 화면을 분할 배치한다.

오로지 창 위치/크기 조정 기능만 담당하며, 실패하더라도 예외를 던지지 않고
status 값으로만 결과를 알려준다(자동화 본 로직에 영향을 주지 않기 위함).
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Optional

LEFT_WIDTH_RATIO = 0.34
CHROME_WINDOW_CLASS = "Chrome_WidgetWin_1"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SPI_GETWORKAREA = 0x0030
GW_OWNER = 4
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# DPI 인식을 선언하지 않으면(기본값 Unaware) Windows가 배율(125%/150% 등)이 걸린
# 화면에서 SystemParametersInfo/MoveWindow 좌표를 가상화해서 실제 물리 좌표와
# 어긋나게 만든다 - 로그는 "MOVED"로 성공 처리되지만 실제 화면에서는 창이 엉뚱한
# 위치/크기로 가거나 거의 안 움직인 것처럼 보이는 원인이 된다. 프로세스 시작 시
# 한 번만 Per-Monitor DPI Aware로 선언해서 항상 실제 물리 픽셀 좌표로 동작하게 한다.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _work_area() -> RECT:
    rect = RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect


def _move(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.MoveWindow(hwnd, x, y, width, height, True))


def _visible_window_of_process(process_name: str):
    result = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _process_name(pid.value) != process_name:
            return True
        result.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else 0


def _find_console_like_window() -> tuple[int, str]:
    """현재 프로세스의 콘솔(로그) 창 핸들을 찾는다.

    Windows 11 기본 터미널인 Windows Terminal에서 실행하면 GetConsoleWindow()가
    반환하는 hwnd는 ConPTY용으로 내부적으로 떠 있는 "보이지 않는" conhost 창이다
    (Windows Terminal 자신은 별도의 최상위 창으로 렌더링됨). 이 경우 MoveWindow를
    호출하면 성공(0이 아닌 값)을 반환하지만 화면에는 아무 변화가 없다 - "로그는
    정상 출력, 실제로는 기능 안 함" 증상의 원인이다. GetConsoleWindow() 결과가
    보이지 않으면 WindowsTerminal.exe의 실제 보이는 창으로 대체한다.
    """
    hwnd = kernel32.GetConsoleWindow()
    if hwnd and user32.IsWindowVisible(hwnd):
        return hwnd, "console_window"
    terminal_hwnd = _visible_window_of_process("windowsterminal.exe")
    if terminal_hwnd:
        return terminal_hwnd, "windows_terminal"
    return hwnd, "console_window_not_visible"


def apply_console_left_layout(left_ratio: float = LEFT_WIDTH_RATIO) -> dict:
    """현재 프로세스의 콘솔(로그) 창을 화면 왼쪽 전체 높이로 이동/리사이즈한다."""
    try:
        hwnd, source = _find_console_like_window()
        if not hwnd:
            return {"status": "NO_CONSOLE_WINDOW"}
        wa = _work_area()
        width = wa.right - wa.left
        height = wa.bottom - wa.top
        left_width = int(width * left_ratio)
        ok = _move(hwnd, wa.left, wa.top, left_width, height)
        return {
            "status": "MOVED" if ok else "MOVE_FAILED",
            "source": source,
            "hwnd": hwnd,
            "x": wa.left,
            "y": wa.top,
            "width": left_width,
            "height": height,
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


def _process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _chrome_main_windows() -> set:
    result: list[int] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if class_buf.value != CHROME_WINDOW_CLASS:
            return True
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _process_name(pid.value) != "chrome.exe":
            return True
        result.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return set(result)


def snapshot_chrome_windows() -> set:
    """브라우저를 실행하기 직전에 호출해서 기존 크롬 창 목록을 저장해둔다."""
    try:
        return _chrome_main_windows()
    except Exception:
        return set()


def apply_browser_right_layout(
    before_hwnds: Optional[set] = None,
    left_ratio: float = LEFT_WIDTH_RATIO,
    timeout: float = 15.0,
) -> dict:
    """새로 뜬 크롬(Chromium) 창을 찾아 화면 오른쪽 영역으로 이동/리사이즈한다."""
    try:
        deadline = time.monotonic() + timeout
        hwnd = 0
        while time.monotonic() < deadline:
            current = _chrome_main_windows()
            candidates = (current - before_hwnds) if before_hwnds else current
            if candidates:
                hwnd = next(iter(candidates))
                break
            time.sleep(0.2)

        if not hwnd:
            return {"status": "CHROME_WINDOW_NOT_FOUND"}

        wa = _work_area()
        width = wa.right - wa.left
        height = wa.bottom - wa.top
        left_width = int(width * left_ratio)
        right_x = wa.left + left_width
        right_width = width - left_width
        ok = _move(hwnd, right_x, wa.top, right_width, height)
        return {
            "status": "MOVED" if ok else "MOVE_FAILED",
            "hwnd": hwnd,
            "x": right_x,
            "y": wa.top,
            "width": right_width,
            "height": height,
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}
