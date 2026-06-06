# 鲁东大学学生教务信息网自动评教

使用 Selenium 控制浏览器完成鲁东大学评教页面的自动填写和提交。

## 入口来源

- 教务系统直连：`https://xsjw.ldu.edu.cn/`
- VPN 入口（校外）：`https://vpn.ldu.edu.cn/`
- 评教页面：`/student/teachingEvaluation/newEvaluation/index`

## 安装依赖

```powershell
pip install -r requirements.txt
```

如果仍使用原文件名：

```powershell
pip install -r requriements.txt
```

## 快速开始

### 普通模式（每次需登录）

```powershell
python evaluation.py
```

### 持久化登录模式（推荐，只需登录一次）

```powershell
python evaluation.py --profile C:\Selenium\ChromeProfile_Auto
```

首次运行时手动登录一次，之后 Chrome 的 Cookie 会保留在指定目录中，后续运行**无需再次登录**，浏览器打开即是已登录状态。

## 校外访问

```powershell
python evaluation.py --vpn
```

通过鲁东大学 VPN 入口访问教务系统。

配合持久化 Profile：

```powershell
python evaluation.py --vpn --profile C:\Selenium\ChromeProfile_Auto
```

## 指定浏览器

```powershell
python evaluation.py --browser edge
python evaluation.py --browser firefox
python evaluation.py --browser chrome
```

脚本自动尝试 Chrome → Edge → Firefox，不需手动指定。

## 连接已有 Chrome

```powershell
python evaluation.py --debug-port 9222
```

连接到已在调试模式下运行的 Chrome 实例（例如用 `chrome.exe --remote-debugging-port=9222` 启动的）。

## 完整参数列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--profile DIR` | 持久化用户数据目录，保留登录 Cookie | 无（每次全新会话） |
| `--vpn` | 通过 VPN 入口访问（校外） | 关闭 |
| `--debug-port PORT` | 连接已有 Chrome 调试端口 | 无 |
| `--browser` | 浏览器：auto / chrome / edge / firefox | auto |
| `--dry-run` | 只填写不提交，测试用 | 关闭 |
| `--comment TEXT` | 文本评价内容 | 无 |
| `--submit-delay SEC` | 提交前等待秒数 | 6 |
| `--wait SEC` | 页面元素最长等待秒数 | 30 |
| `--no-popup` | 不用弹窗，终端回车开始 | 关闭 |
| `--no-animation` | 完成后不显示全屏动画 | 关闭 |
| `--headless` | 无界面运行（不建议首次使用） | 关闭 |

## 运行流程

1. 脚本自动启动 Chrome（或 Edge/Firefox）
2. 导航到评教入口，若未登录请手动完成统一身份认证
3. 检测到评教列表后弹出确认窗口
4. 点击"开始自动评教"后自动执行：
   - 切换到「课堂教师」页签
   - 展开全部课程
   - 逐课程填写：全部选"优" + 填写评语 + 保存提交
5. 全部完成后显示全屏动画

## 说明

- **持久化 Profile 是最推荐的用法**：一次登录，长期有效，接近全自动体验
- 持久化 Profile 仅 Chrome 支持最佳（Edge 次之）
- 若页面元素变化导致脚本卡住，先 `--dry-run` 观察具体在哪一步
- 鲁东大学评教页面是前端动态渲染，接口和元素名可能随学校系统升级变化
- 评教会影响教学反馈，请只在确认评价符合真实感受时使用
