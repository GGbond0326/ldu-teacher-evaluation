# -*- coding: utf-8 -*-
"""兼容旧入口。

历史版本使用 `python evaluate.py` 运行北航脚本。现在项目已改为鲁东大学版本，
保留这个文件只是为了让旧命令继续可用。
"""

from evaluation import parse_args, run_auto_evaluation


if __name__ == "__main__":
    run_auto_evaluation(parse_args())
