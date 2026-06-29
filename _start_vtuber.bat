@echo off
cd /d "D:\项目\控制电脑\Open-LLM-VTuber-v1.2.1-zh"
"D:\项目\控制电脑\.venv\Scripts\python.exe" run_server.py > "D:\项目\控制电脑\vtuber_stdout.log" 2> "D:\项目\控制电脑\vtuber_stderr.log"