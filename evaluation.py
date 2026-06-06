# -*- coding: utf-8 -*-
"""鲁东大学学生教务信息网自动评教脚本。

使用方式：
1. 运行 `python evaluation.py`
2. 在打开的浏览器中完成统一身份认证登录
3. 脚本进入评教列表后，会自动选择"课堂教学"页签、展开全部课程、逐项评估

持久化登录（推荐）：
  python evaluation.py --profile C:\Selenium\ChromeProfile_Auto
  首次运行时手动登录一次，之后 Cookie 会保留在该目录，后续运行无需再次登录。

提醒：评教内容会影响教师教学改进，请只在确认评价符合你真实感受时使用。
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass, field
from time import monotonic, sleep

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# ---- URL 配置 ----
DIRECT_BASE = "https://xsjw.ldu.edu.cn"
VPN_BASE = (
    "https://vpn.ldu.edu.cn/https/77726476706e69737468656265737421"
    "e8e44b8b693c6c45300d8db9d6562d"
)
EVALUATION_PATH = "/student/teachingEvaluation/newEvaluation/"

EVALUATION_INDEX_URL_DIRECT = f"{DIRECT_BASE}{EVALUATION_PATH}index"
EVALUATION_INDEX_URL_VPN = f"{VPN_BASE}{EVALUATION_PATH}index"

BROWSER_ORDER = ("chrome", "edge", "firefox")
DEFAULT_PROFILE_DIR = os.path.join(os.environ.get("TEMP", "."), "LDU_Eval_Profile")


@dataclass(frozen=True)
class EvaluationConfig:
    comment: str = "无"
    submit_delay: float = 6.0
    wait_seconds: int = 30
    dry_run: bool = False
    browser: str = "auto"
    headless: bool = False
    no_popup: bool = False
    no_animation: bool = False
    use_vpn: bool = False
    profile_dir: str | None = None
    debug_port: int | None = None


def _get_eval_url(use_vpn: bool) -> str:
    return EVALUATION_INDEX_URL_VPN if use_vpn else EVALUATION_INDEX_URL_DIRECT


def _get_eval_path_base(use_vpn: bool) -> str:
    return VPN_BASE + EVALUATION_PATH if use_vpn else DIRECT_BASE + EVALUATION_PATH


# ---- 浏览器驱动 ----

def build_chrome_driver(
    headless: bool = False,
    profile_dir: str | None = None,
    debug_port: int | None = None,
) -> WebDriver:
    options = ChromeOptions()
    options.add_experimental_option("detach", True)

    # 连接已运行的 Chrome（remote debugging 模式）
    if debug_port:
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        print(f"正在连接到 127.0.0.1:{debug_port} 的 Chrome 实例...")
        return webdriver.Chrome(options=options)

    # 持久化用户数据目录 —— 登录一次，长期有效
    if profile_dir:
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
        print(f"使用持久化用户目录: {profile_dir}")

    if headless:
        options.add_argument("--headless=new")

    return webdriver.Chrome(options=options)


def build_edge_driver(
    headless: bool = False,
    profile_dir: str | None = None,
) -> WebDriver:
    options = EdgeOptions()
    options.add_experimental_option("detach", True)
    if profile_dir:
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Edge(options=options)


def build_firefox_driver(headless: bool = False) -> WebDriver:
    options = FirefoxOptions()
    if headless:
        options.add_argument("-headless")
    return webdriver.Firefox(options=options)


def build_driver(config: EvaluationConfig) -> WebDriver:
    builders: dict[str, object] = {
        "chrome": lambda: build_chrome_driver(
            config.headless, config.profile_dir, config.debug_port
        ),
        "edge": lambda: build_edge_driver(config.headless, config.profile_dir),
        "firefox": lambda: build_firefox_driver(config.headless),
    }
    browser_names = BROWSER_ORDER if config.browser == "auto" else (config.browser,)
    errors: list[str] = []

    for browser_name in browser_names:
        try:
            driver = builders[browser_name]()
            print(f"已启动 {browser_name} 浏览器。")
            return driver
        except WebDriverException as exc:
            msg = exc.msg.splitlines()[0] if exc.msg else str(exc)
            errors.append(f"{browser_name}: {msg}")

    detail = "\n".join(f"- {item}" for item in errors)
    raise RuntimeError(
        "无法启动可用浏览器。请安装 Chrome、Edge 或 Firefox，"
        "或用 `--browser edge` / `--browser firefox` 指定已安装的浏览器。\n"
        f"{detail}"
    )


def launch_chrome_with_profile(config: EvaluationConfig) -> WebDriver | None:
    """用 subprocess 启动带持久化 profile 的 Chrome，再让 Selenium 挂上去。

    这样即使用户关掉 Selenium，Chrome 仍保留登录态，下次启动直接可用。
    仅对 Chrome + profile_dir + 非 headless 生效。
    """
    if config.browser not in ("chrome", "auto"):
        return None
    if not config.profile_dir or config.headless or config.debug_port:
        return None

    os.makedirs(config.profile_dir, exist_ok=True)

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome_exe = None
    for path in chrome_paths:
        if os.path.isfile(path):
            chrome_exe = path
            break

    if not chrome_exe:
        return None  # 退回普通 Selenium 启动

    port = 19222
    url = _get_eval_url(config.use_vpn)

    cmd = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={config.profile_dir}",
        url,
    ]

    try:
        subprocess.Popen(cmd)
        print(f"Chrome 已通过持久化 Profile 启动（端口 {port}）。")
        print("若浏览器中已显示已登录状态，说明上次的 Cookie 仍然有效。")
        sleep(4)

        # 用 debuggerAddress 连接上去
        options = ChromeOptions()
        options.add_experimental_option("detach", True)
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        driver = webdriver.Chrome(options=options)
        print("已连接到 Chrome 实例。")
        return driver
    except Exception as e:
        print(f"通过 Profile 启动失败 ({e})，退回普通模式。")
        return None


# ---- 页面就绪判断 ----

def wait_for_ready(driver: WebDriver, wait: WebDriverWait) -> None:
    wait.until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )


def is_evaluation_index_ready(driver: WebDriver, use_vpn: bool = False) -> bool:
    path_base = _get_eval_path_base(use_vpn)
    try:
        if path_base not in driver.current_url:
            return False
        return bool(
            driver.execute_script(
                """
                const hasAssessmentButton = Array.from(
                    document.querySelectorAll('button')
                ).some((btn) => btn.textContent.trim() === '评估');
                const hasTableBody = Boolean(document.getElementById('codetbody'));
                const hasPageSizeSelect = Boolean(
                    document.getElementById('pagination_pageSize_urppagebar')
                );
                const hasTab = Boolean(document.getElementById('myTab'));
                const hasEvaluationKeyword = /评估|评价|评教|课堂教学|课堂教师/.test(
                    document.body?.innerText || ''
                );
                return (
                    hasAssessmentButton || hasTableBody || hasPageSizeSelect ||
                    hasTab || hasEvaluationKeyword
                );
                """
            )
        )
    except WebDriverException:
        return False


# ---- 用户交互 ----

def wait_for_start_confirmation(config: EvaluationConfig) -> None:
    if config.no_popup or config.headless:
        input("登录完成并进入评教页面后，按回车开始自动评教...")
        return

    try:
        from tkinter import BOTH, Canvas, Frame, Label, Tk

        root = Tk()
        root.title("鲁东大学自动评教")
        root.configure(bg="#0f172a")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        width, height = 560, 380
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")

        canvas = Canvas(root, width=width, height=height, bg="#0f172a", highlightthickness=0)
        canvas.pack(fill=BOTH, expand=True)
        canvas.create_rectangle(28, 28, width - 28, height - 28, fill="#111827", outline="#38bdf8", width=2)
        canvas.create_oval(-80, -100, 180, 160, fill="#1d4ed8", outline="")
        canvas.create_oval(width - 120, height - 140, width + 110, height + 90, fill="#0f766e", outline="")

        card = Frame(root, bg="#111827")
        canvas.create_window(width // 2, height // 2, window=card, width=460, height=280)

        Label(
            card, text="鲁东大学自动评教", fg="#e0f2fe", bg="#111827",
            font=("Microsoft YaHei UI", 24, "bold"),
        ).pack(pady=(24, 8))
        Label(
            card, text="已检测到评教页面，可以开始啦。", fg="#93c5fd", bg="#111827",
            font=("Microsoft YaHei UI", 12),
        ).pack()

        if config.profile_dir:
            Label(
                card,
                text="检测到持久化登录模式，若已登录过则无需再次登录。",
                fg="#fde68a", bg="#111827",
                font=("Microsoft YaHei UI", 10),
            ).pack(pady=(6, 0))

        Label(
            card, text="点击下方按钮或按 Enter，脚本才会开始自动处理。",
            fg="#cbd5e1", bg="#111827", font=("Microsoft YaHei UI", 11),
        ).pack(pady=(18, 24))

        start_button = Label(
            card, text="开始自动评教", fg="#082f49", bg="#67e8f9",
            font=("Microsoft YaHei UI", 16, "bold"), padx=34, pady=12,
        )
        start_button.pack()

        Label(
            card, text="傻瓜模式：点一下，剩下交给我。", fg="#64748b", bg="#111827",
            font=("Microsoft YaHei UI", 10),
        ).pack(pady=(18, 0))

        def close_window(_: object | None = None) -> None:
            root.destroy()

        start_button.bind("<Button-1>", close_window)
        root.bind("<Return>", close_window)
        root.mainloop()
    except Exception:
        input("登录完成并进入评教页面后，按回车开始自动评教...")


def wait_for_manual_login(
    driver: WebDriver, wait: WebDriverWait, config: EvaluationConfig
) -> None:
    eval_url = _get_eval_url(config.use_vpn)
    driver.get(eval_url)

    if config.use_vpn:
        print("已通过 VPN 入口打开评教页面。")
    else:
        print("已打开鲁东大学评教入口。")

    if config.profile_dir:
        print("（持久化模式：若之前登录过，Cookie 可能仍有效，无需再次登录。）")

    print("若跳转到登录页，请先在浏览器中完成登录。")

    last_notice = 0.0
    while True:
        try:
            WebDriverWait(driver, 2).until(
                lambda d: is_evaluation_index_ready(d, config.use_vpn)
            )
            break
        except TimeoutException:
            now = monotonic()
            if now - last_notice >= config.wait_seconds:
                print("等待登录完成中：检测到评教列表后才会弹出开始窗口。")
                last_notice = now

    wait_for_start_confirmation(config)
    wait_for_ready(driver, wait)


# ---- 完成动画 ----

def show_completion_animation(config: EvaluationConfig) -> None:
    if config.no_animation or config.headless:
        return

    try:
        from tkinter import BOTH, Canvas, Tk

        root = Tk()
        root.title("评教完成")
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.configure(bg="#020617")

        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        canvas = Canvas(root, width=width, height=height, bg="#020617", highlightthickness=0)
        canvas.pack(fill=BOTH, expand=True)

        for index in range(34):
            x = (index * 137) % width
            y = (index * 89) % height
            size = 2 + index % 5
            canvas.create_oval(x, y, x + size, y + size, fill="#38bdf8", outline="")

        glow = canvas.create_text(
            width // 2, height // 2 - 10,
            text="鲁东大学评教完成", fill="#38bdf8",
            font=("Microsoft YaHei UI", 58, "bold"),
        )
        main_text = canvas.create_text(
            width // 2, height // 2 - 10,
            text="鲁东大学评教完成", fill="#f8fafc",
            font=("Microsoft YaHei UI", 50, "bold"),
        )
        subtitle = canvas.create_text(
            width // 2, height // 2 + 95,
            text="评教完成，功德 +1", fill="#93c5fd",
            font=("Microsoft YaHei UI", 24),
        )

        colors = ("#f8fafc", "#fde68a", "#67e8f9", "#c4b5fd", "#bbf7d0")

        def animate(frame: int = 0) -> None:
            if frame >= 95:
                root.destroy()
                return
            size = 50 + frame % 16
            canvas.itemconfig(
                main_text, fill=colors[frame % len(colors)],
                font=("Microsoft YaHei UI", size, "bold"),
            )
            canvas.itemconfig(glow, font=("Microsoft YaHei UI", size + 10, "bold"))
            canvas.itemconfig(subtitle, fill=colors[(frame + 2) % len(colors)])
            offset = -1 if frame % 2 == 0 else 1
            canvas.move(main_text, 0, offset)
            canvas.move(glow, 0, offset)
            root.after(45, lambda: animate(frame + 1))

        root.bind("<Escape>", lambda _: root.destroy())
        root.bind("<Return>", lambda _: root.destroy())
        root.after(100, animate)
        root.mainloop()
    except Exception:
        return


# ---- 评教核心逻辑 ----

MAX_TAB_RETRIES = 3


def click_teaching_tab(driver: WebDriver) -> None:
    """点击 '课堂教师' 页签，带重试和激活状态校验。

    优先用精确 XPath 匹配 '课堂教师' 页签（VenenoSix24 方案），
    失败则回退到原始的 JS clickTab / 模糊匹配方案。
    """
    for attempt in range(1, MAX_TAB_RETRIES + 1):
        try:
            # 方案 A：精确 XPath 匹配 "课堂教师" 页签
            tab_xpath = (
                "//ul[@id='myTab']/li/a[contains(normalize-space(), '课堂教师')]"
            )
            tab_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, tab_xpath))
            )
            parent_li = driver.find_element(By.XPATH, f"{tab_xpath}/parent::li")
            is_active = "active" in (parent_li.get_attribute("class") or "")

            if is_active:
                return  # 已经是活动的，无需点击

            clickable = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, tab_xpath))
            )
            driver.execute_script("arguments[0].click();", clickable)
            sleep(2)

            # 校验是否激活
            parent_after = driver.find_element(By.XPATH, f"{tab_xpath}/parent::li")
            if "active" in (parent_after.get_attribute("class") or ""):
                return
            print(f"  课堂教师页签点击后未激活，重试 {attempt}/{MAX_TAB_RETRIES}")
        except TimeoutException:
            pass  # 方案 A 失败，尝试方案 B
        except Exception:
            pass

        # 方案 B：用原始 JS 方案
        try:
            driver.execute_script(
                """
                if (typeof clickTab === 'function') {
                    clickTab('ktjs');
                    return true;
                }
                return false;
                """
            )
            sleep(1)
            return
        except Exception:
            pass

        # 方案 C：模糊文本匹配
        try:
            driver.execute_script(
                """
                const candidates = Array.from(
                    document.querySelectorAll('a,button,li,span')
                );
                const tab = candidates.find(
                    (item) => /课堂|教师|教学/.test(item.textContent || '')
                );
                if (tab) tab.click();
                """
            )
            sleep(1)
        except Exception:
            pass

    # 最终降级：不强制要求页签切换成功
    print("  注意：多次尝试后未能确认课堂教师页签状态，继续执行。")


def show_all_courses(driver: WebDriver) -> None:
    """展开分页，显示所有课程（一页加载全部）。"""
    driver.execute_script(
        """
        const select = document.getElementById('pagination_pageSize_urppagebar');
        if (!select) return;
        const option = Array.from(select.options).find(
            (item) => item.value === '100000000_sl'
        );
        if (!option) return;
        select.value = option.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        """
    )
    sleep(1)


def find_unevaluated_courses(driver: WebDriver) -> list:
    """从课程表格中找出所有未评课程行。

    优先使用 codetbody 表格结构解析（VenenoSix24 方案），
    回退到查找"评估"按钮方案。
    """
    rows_data: list[dict] = []

    # ---- 方案 A：codetbody 表格遍历 ----
    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.ID, "codetbody"))
        )
        sleep(0.5)
        rows = driver.find_elements(By.XPATH, "//tbody[@id='codetbody']/tr")
        if rows:
            for row in rows:
                try:
                    # 最后一列的 span 含状态
                    status_span = row.find_element(
                        By.XPATH, ".//td[last()]//span[contains(@class, 'label')]"
                    )
                    classes = status_span.get_attribute("class") or ""
                    is_evaluated = "label-success" in classes

                    if not is_evaluated:
                        # 提取课程/教师信息
                        try:
                            course_name = row.find_element(By.XPATH, ".//td[5]").text
                        except NoSuchElementException:
                            course_name = "未知课程"
                        try:
                            teacher_name = row.find_element(By.XPATH, ".//td[4]").text
                        except NoSuchElementException:
                            teacher_name = "未知教师"

                        # 第二列的"评估"按钮
                        btn = row.find_element(
                            By.XPATH, ".//td[2]//button[contains(., '评估')]"
                        )
                        rows_data.append({
                            "course": course_name,
                            "teacher": teacher_name,
                            "button": btn,
                        })
                except NoSuchElementException:
                    continue
                except Exception:
                    continue

            if rows_data:
                return rows_data
    except TimeoutException:
        pass
    except Exception:
        pass

    # ---- 方案 B：直接扫描所有"评估"按钮 ----
    all_buttons = driver.find_elements(By.TAG_NAME, "button")
    eval_buttons = [b for b in all_buttons if b.text.strip() == "评估" and b.is_enabled()]
    for btn in eval_buttons:
        rows_data.append({
            "course": "未知课程",
            "teacher": "未知教师",
            "button": btn,
        })

    return rows_data


def open_evaluation_for_course(
    driver: WebDriver, wait: WebDriverWait, course_info: dict
) -> bool:
    """点击某个课程的评估按钮，进入评估页面。"""
    try:
        btn = course_info["button"]
        driver.execute_script("arguments[0].click();", btn)
        sleep(2)

        wait.until(
            lambda browser: "evaluation" in browser.current_url
            or browser.find_elements(By.ID, "savebutton")
        )
        wait_for_ready(driver, wait)
        return True
    except TimeoutException:
        print(f"  进入课程 {course_info.get('course')} 评估页超时。")
        return False
    except Exception as e:
        print(f"  进入评估页失败: {e}")
        return False


def answer_current_evaluation(driver: WebDriver, config: EvaluationConfig) -> int:
    """填写当前评估页：选择最优选项 + 填写评语。"""
    selected_count = driver.execute_script(
        """
        const groups = new Map();
        for (const radio of document.querySelectorAll('input[type="radio"]')) {
            if (!groups.has(radio.name)) groups.set(radio.name, []);
            groups.get(radio.name).push(radio);
        }

        let selected = 0;
        for (const radios of groups.values()) {
            const preferred =
                radios.find((item) => item.value === 'A_优') ||
                radios.find((item) =>
                    /优|优秀|满意|非常/.test(
                        item.value || item.parentElement?.textContent || ''
                    )
                ) ||
                radios[0];

            if (preferred) {
                preferred.checked = true;
                preferred.click();
                preferred.dispatchEvent(new Event('change', { bubbles: true }));
                selected += 1;
            }
        }
        return selected;
        """
    )

    driver.execute_script(
        """
        const comment = arguments[0];
        for (const textarea of document.querySelectorAll('textarea')) {
            textarea.value = comment;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """,
        config.comment,
    )
    return int(selected_count)


def submit_current_evaluation(
    driver: WebDriver, wait: WebDriverWait, config: EvaluationConfig
) -> None:
    """保存并确认提交。"""
    if config.dry_run:
        print("  dry-run：已填写但未提交。")
        return

    sleep(config.submit_delay)
    save_button = wait.until(EC.element_to_be_clickable((By.ID, "savebutton")))
    driver.execute_script("arguments[0].click();", save_button)
    sleep(1)

    # 处理可能的确认弹窗按钮
    driver.execute_script(
        """
        const confirmButtons = Array.from(document.querySelectorAll('button'));
        const confirm = confirmButtons.find(
            (button) => /确定|确认|提交/.test(button.textContent || '')
        );
        if (confirm) confirm.click();
        """
    )
    sleep(2)


# ---- 主流程 ----

def run_auto_evaluation(config: EvaluationConfig) -> None:
    # 1. 启动浏览器
    driver = None

    # 优先尝试 subprocess 方式启动（持久化 Profile 效果最好）
    if config.profile_dir and config.browser in ("chrome", "auto") and not config.debug_port:
        driver = launch_chrome_with_profile(config)

    # 回退到普通 Selenium 启动
    if driver is None:
        driver = build_driver(config)

    wait = WebDriverWait(driver, config.wait_seconds)

    # 2. 等待用户登录
    wait_for_manual_login(driver, wait, config)

    # 3. 循环评估
    completed = 0
    eval_url = _get_eval_url(config.use_vpn)

    while True:
        wait_for_ready(driver, wait)
        click_teaching_tab(driver)
        show_all_courses(driver)

        courses = find_unevaluated_courses(driver)
        if not courses:
            print("未找到可以评估的课程，评教可能已全部完成。")
            break

        course = courses[0]
        print(
            f"开始评教 ({completed + 1}): "
            f"{course.get('course', '?')} - {course.get('teacher', '?')}"
        )

        if not open_evaluation_for_course(driver, wait, course):
            continue

        selected = answer_current_evaluation(driver, config)
        print(f"  已填写选择题 {selected} 项。")
        submit_current_evaluation(driver, wait, config)
        completed += 1

        if config.dry_run:
            break

        # 回到列表页
        driver.get(eval_url)
        wait_for_ready(driver, wait)

    print(f"处理完成，共完成 {completed} 份评教。")
    show_completion_animation(config)


def parse_args() -> EvaluationConfig:
    parser = argparse.ArgumentParser(description="鲁东大学学生教务信息网自动评教")
    parser.add_argument("--comment", default="无", help="文本评价内容，默认：无")
    parser.add_argument("--submit-delay", type=float, default=6.0, help="提交前等待秒数")
    parser.add_argument("--wait", type=int, default=30, help="页面元素最长等待秒数")
    parser.add_argument("--dry-run", action="store_true", help="只自动填写，不点击提交")
    parser.add_argument("--no-popup", action="store_true", help="不用弹窗，改为终端回车开始")
    parser.add_argument("--no-animation", action="store_true", help="完成后不显示大屏动画")
    parser.add_argument(
        "--browser",
        choices=("auto", "chrome", "edge", "firefox"),
        default="auto",
        help="浏览器类型，默认自动尝试 Chrome、Edge、Firefox",
    )
    parser.add_argument("--headless", action="store_true", help="无界面运行，不建议首次使用")
    parser.add_argument(
        "--vpn",
        action="store_true",
        help="通过 VPN 入口访问教务系统（校外访问时使用）",
    )
    parser.add_argument(
        "--profile",
        default=None,
        metavar="DIR",
        help="持久化用户数据目录。登录一次后 Cookie 保留，后续运行无需再次登录。"
        "例如：--profile C:\\Selenium\\ChromeProfile_Auto",
    )
    parser.add_argument(
        "--debug-port",
        type=int,
        default=None,
        metavar="PORT",
        help="连接到指定调试端口的已有 Chrome 实例，例如：--debug-port 9222",
    )
    args = parser.parse_args()
    return EvaluationConfig(
        comment=args.comment,
        submit_delay=args.submit_delay,
        wait_seconds=args.wait,
        dry_run=args.dry_run,
        browser=args.browser,
        headless=args.headless,
        no_popup=args.no_popup,
        no_animation=args.no_animation,
        use_vpn=args.vpn,
        profile_dir=args.profile,
        debug_port=args.debug_port,
    )


if __name__ == "__main__":
    run_auto_evaluation(parse_args())
