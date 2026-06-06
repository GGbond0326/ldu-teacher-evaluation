# 鲁东大学学生教务信息网自动评教

使用 Selenium 控制浏览器完成鲁东大学评教页面的自动填写和提交。

## 入口来源

- 鲁东大学官网"学生入口"中的本科生教务系统入口：`https://xsjw.ldu.edu.cn/`
- 评教页面：`https://xsjw.ldu.edu.cn/student/teachingEvaluation/newEvaluation/index`

## 安装依赖

```powershell
pip install -r requirements.txt
```

如果仍使用原文件名：

```powershell
pip install -r requriements.txt
```

## 运行

```powershell
python evaluation.py
```

脚本会自动尝试启动 `Chrome`、`Edge`、`Firefox`。如果电脑没有安装谷歌浏览器，通常会自动使用 Windows 自带的 `Edge`。

若页面跳转到统一身份认证或 VPN 登录页，请先手动登录；进入评教页面后，屏幕中间会弹出确认窗口，点击"开始自动评教"或按 `Enter` 后开始自动处理。

如果密码输错或登录比较慢，不用关闭程序；脚本会一直等待，只有检测到评教列表页面后才会弹出开始窗口。

全部处理完成后会显示全屏文字动画：`鲁东大学评教完成`。按 `Esc` 或 `Enter` 可以提前关闭。

## 指定浏览器

```powershell
python evaluation.py --browser edge
python evaluation.py --browser firefox
python evaluation.py --browser chrome
```

## 可选参数

```powershell
python evaluation.py --dry-run
python evaluation.py --comment "无" --submit-delay 8
python evaluation.py --no-popup
python evaluation.py --no-animation
```

- `--dry-run`：只填写不提交，适合先测试页面是否适配。
- `--comment`：文本评价内容，默认 `无`。
- `--submit-delay`：提交前等待秒数，默认 `6`。
- `--browser`：浏览器类型，可选 `auto`、`chrome`、`edge`、`firefox`。
- `--no-popup`：不用弹窗，改为终端按回车开始。
- `--no-animation`：完成后不显示全屏文字动画。

## 说明

鲁东大学评教页面是前端动态页面，接口和元素名可能随学校系统升级变化。若脚本卡住，优先用 `--dry-run` 观察具体卡在哪一步，再根据页面元素调整选择器。

评教会影响教学反馈，请只在确认评价符合真实感受时使用。
