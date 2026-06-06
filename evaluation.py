# -*- coding: utf-8 -*-
"""鲁东大学学生教务信息网自动评教脚本。

使用方式：
1. 运行 `python evaluation.py`
2. 在打开的浏览器中完成统一身份认证登录
3. 脚本进入评教列表后，会自动选择"课堂教学"页签、展开全部课程、逐项评估

提醒：评教内容会影响教师教学改进，请只在确认评价符合你真实感受时使用。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from time import monotonic, sleep

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


EVALUATION_INDEX_URL = (
    "https://xsjw.ldu.edu.cn/student/teachingEvaluation/newEvaluation/index"
)
EVALUATION_PATH = "/student/teachingEvaluation/newEvaluation/"
BROWSER_ORDER = ("chrome", "edge", "firefox")


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


def build_chrome_driver(headless: bool) -> WebDriver:
    options = ChromeOptions()
    options.add_experimental_option("detach", True)
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


def build_edge_driver(headless: bool) -> WebDriver:
    options = EdgeOptions()
    options.add_experimental_option("detach", True)
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Edge(options=options)


def build_firefox_driver(headless: bool) -> WebDriver:
    options = FirefoxOptions()
    if headless:
        options.add_argument("-headless")
    return webdriver.Firefox(options=options)


def build_driver(browser: str = "auto", headless: bool = False) -> WebDriver:
    builders = {
        "chrome": build_chrome_driver,
        "edge": build_edge_driver,
        "firefox": build_firefox_driver,
    }
    browser_names = BROWSER_ORDER if browser == "auto" else (browser,)
    errors: list[str] = []

    for browser_name in browser_names:
        try:
            driver = builders[browser_name](headless)
            print(f"已启动 {browser_name} 浏览器。")
            return driver
        except WebDriverException as exc:
            errors.append(f"{browser_name}: {exc.msg.splitlines()[0] if exc.msg else exc}")

    detail = "\n".join(f"- {item}" for item in errors)
    raise RuntimeError(
        "无法启动可用浏览器。请安装 Chrome、Edge 或 Firefox，"
        "或用 `--browser edge` / `--browser firefox` 指定已安装的浏览器。\n"
        f"{detail}"
    )


def wait_for_ready(driver: WebDriver, wait: WebDriverWait) -> None:
    wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")


def is_evaluation_index_ready(driver: WebDriver) -> bool:
    try:
        if EVALUATION_PATH not in driver.current_url:
            return False

        return bool(
            driver.execute_script(
                """
                const hasAssessmentButton = Array.from(document.querySelectorAll('button'))
                    .some((button) => button.textContent.trim() === '评估');
                const hasPageSizeSelect = Boolean(document.getElementById('pagination_pageSize_urppagebar'));
                const hasTeachingTabFunction = typeof clickTab === 'function';
                const hasEvaluationKeyword = /评估|评价|评教|课堂教学/.test(document.body?.innerText || '');
                return hasAssessmentButton || hasPageSizeSelect || hasTeachingTabFunction || hasEvaluationKeyword;
                """
            )
        )
    except WebDriverException:
        return False


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

        width, height = 560, 360
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
        canvas.create_window(width // 2, height // 2, window=card, width=460, height=260)

        Label(card, text="鲁东大学自动评教", fg="#e0f2fe", bg="#111827", font=("Microsoft YaHei UI", 24, "bold")).pack(pady=(24, 8))
        Label(card, text="已检测到评教页面，可以开始啦。", fg="#93c5fd", bg="#111827", font=("Microsoft YaHei UI", 12)).pack()
        Label(card, text="点击下方按钮或按 Enter，脚本才会开始自动处理。", fg="#cbd5e1", bg="#111827", font=("Microsoft YaHei UI", 11)).pack(pady=(18, 24))

        start_button = Label(
            card,
            text="开始自动评教",
            fg="#082f49",
            bg="#67e8f9",
            font=("Microsoft YaHei UI", 16, "bold"),
            padx=34,
            pady=12,
        )
        start_button.pack()

        Label(card, text="傻瓜模式：点一下，剩下交给我。", fg="#64748b", bg="#111827", font=("Microsoft YaHei UI", 10)).pack(pady=(18, 0))

        def close_window(_: object | None = None) -> None:
            root.destroy()

        start_button.bind("<Button-1>", close_window)
        root.bind("<Return>", close_window)
        root.mainloop()
    except Exception:
        input("登录完成并进入评教页面后，按回车开始自动评教...")


def wait_for_manual_login(driver: WebDriver, wait: WebDriverWait, config: EvaluationConfig) -> None:
    driver.get(EVALUATION_INDEX_URL)
    print("已打开鲁东大学评教入口。若跳转到登录页，请先在浏览器中完成登录。")

    last_notice = 0.0
    while True:
        try:
            WebDriverWait(driver, 2).until(is_evaluation_index_ready)
            break
        except TimeoutException:
            now = monotonic()
            if now - last_notice >= config.wait_seconds:
                print("等待登录完成中：检测到评教列表后才会弹出开始窗口。")
                last_notice = now

    wait_for_start_confirmation(config)
    wait_for_ready(driver, wait)


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
            width // 2,
            height // 2 - 10,
            text="鲁东大学评教完成",
            fill="#38bdf8",
            font=("Microsoft YaHei UI", 58, "bold"),
        )
        main_text = canvas.create_text(
            width // 2,
            height // 2 - 10,
            text="周哥的恩情还不完！",
            fill="#f8fafc",
            font=("Microsoft YaHei UI", 50, "bold"),
        )
        subtitle = canvas.create_text(
            width // 2,
            height // 2 + 95,
            text="评教完成，功德 +1",
            fill="#93c5fd",
            font=("Microsoft YaHei UI", 24),
        )

        colors = ("#f8fafc", "#fde68a", "#67e8f9", "#c4b5fd", "#bbf7d0")

        def animate(frame: int = 0) -> None:
            if frame >= 95:
                root.destroy()
                return

            size = 50 + frame % 16
            canvas.itemconfig(main_text, fill=colors[frame % len(colors)], font=("Microsoft YaHei UI", size, "bold"))
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


def click_teaching_tab(driver: WebDriver) -> None:
    driver.execute_script(
        """
        if (typeof clickTab === 'function') {
            clickTab('ktjs');
        } else {
            const candidates = Array.from(document.querySelectorAll('a,button,li,span'));
            const tab = candidates.find((item) => /课堂|教师|教学/.test(item.textContent || ''));
            if (tab) tab.click();
        }
        """
    )
    sleep(1)


def show_all_courses(driver: WebDriver) -> None:
    driver.execute_script(
        """
        const select = document.getElementById('pagination_pageSize_urppagebar');
        if (!select) return;
        const option = Array.from(select.options).find((item) => item.value === '100000000_sl');
        if (!option) return;
        select.value = option.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        """
    )
    sleep(1)


def find_evaluation_buttons(driver: WebDriver) -> list:
    buttons = driver.find_elements(By.TAG_NAME, "button")
    return [button for button in buttons if button.text.strip() == "评估" and button.is_enabled()]


def open_next_evaluation(driver: WebDriver, wait: WebDriverWait) -> bool:
    wait_for_ready(driver, wait)
    click_teaching_tab(driver)
    show_all_courses(driver)
    buttons = find_evaluation_buttons(driver)
    if not buttons:
        return False
    buttons[0].click()
    wait.until(lambda browser: "evaluation" in browser.current_url or browser.find_elements(By.ID, "savebutton"))
    wait_for_ready(driver, wait)
    return True


def answer_current_evaluation(driver: WebDriver, config: EvaluationConfig) -> int:
    selected_count = driver.execute_script(
        """
        const groups = new Map();
        for (const radio of document.querySelectorAll('input[type="radio"]')) {
            if (!groups.has(radio.name)) groups.set(radio.name, []);
            groups.get(radio.name).push(radio);
        }

        let selected = 0;
        for (const radios of groups.values()) {
            const preferred = radios.find((item) => item.value === 'A_优')
                || radios.find((item) => /优|优秀|满意|非常/.test(item.value || item.parentElement?.textContent || ''))
                || radios[0];
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


def submit_current_evaluation(driver: WebDriver, wait: WebDriverWait, config: EvaluationConfig) -> None:
    if config.dry_run:
        print("dry-run：已填写但未提交。")
        return

    sleep(config.submit_delay)
    save_button = wait.until(EC.element_to_be_clickable((By.ID, "savebutton")))
    save_button.click()
    sleep(1)

    driver.execute_script(
        """
        const confirmButtons = Array.from(document.querySelectorAll('button'));
        const confirm = confirmButtons.find((button) => /确定|确认|提交/.test(button.textContent || ''));
        if (confirm) confirm.click();
        """
    )
    sleep(2)


def run_auto_evaluation(config: EvaluationConfig) -> None:
    driver = build_driver(config.browser, config.headless)
    wait = WebDriverWait(driver, config.wait_seconds)

    wait_for_manual_login(driver, wait, config)

    completed = 0
    while open_next_evaluation(driver, wait):
        selected = answer_current_evaluation(driver, config)
        print(f"已填写第 {completed + 1} 份评教，选择题 {selected} 项。")
        submit_current_evaluation(driver, wait, config)
        completed += 1

        if config.dry_run:
            break

        driver.get(EVALUATION_INDEX_URL)
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
    )


if __name__ == "__main__":
    run_auto_evaluation(parse_args())
