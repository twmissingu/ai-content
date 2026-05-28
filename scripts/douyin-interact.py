#!/usr/bin/env python3
"""抖音互动脚本 - 点赞+收藏+评论 (base64方案)"""
import subprocess, sys, time, base64

COMMENT_TEXT = sys.argv[1] if len(sys.argv) > 1 else "干货满满，学到了！"

def run_js(js_code):
    """通过AppleScript在Chrome中执行JS，使用base64编码"""
    b64 = base64.b64encode(js_code.encode()).decode()
    script = f'tell application "Google Chrome" to tell active tab of front window to execute javascript "eval(atob(\'{b64}\'))"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    return r.stdout.strip()

comment_b64 = base64.b64encode(COMMENT_TEXT.encode()).decode()

print("[1/5] 点赞...", run_js('document.querySelector("[data-e2e=video-player-digg]").click()"ok"'))
time.sleep(1)

print("[2/5] 收藏...", run_js('document.querySelector("[data-e2e=video-player-collect]").click()"ok"'))
time.sleep(1)

print("[3/5] 展开评论区...", run_js('document.querySelector("[data-e2e=feed-comment-icon]").click()"ok"'))
time.sleep(2)

print("[4/5] 激活评论框...", run_js('document.querySelector(".comment-input-inner-container").click()"ok"'))
time.sleep(2)

# 检查编辑器
editor = run_js('document.querySelector(".public-DraftEditor-content")?"exists":"nf"')
print(f"[5/5] 编辑器状态: {editor}")

if editor == "exists":
    # 输入评论
    result = run_js(f"var e=document.querySelector('.public-DraftEditor-content');if(e){{e.focus();document.execCommand('insertText',false,atob('{comment_b64}'));'typed'}}else{{'no editor'}}")
    print(f"  输入结果: {result}")
    time.sleep(1)

    # 提交评论 - 使用Enter键事件
    submit = run_js("var e=document.querySelector('.public-DraftEditor-content');if(e){e.focus();var evt=new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true});e.dispatchEvent(evt);'submitted'}else{'no editor'}")
    print(f"  提交结果: {submit}")
else:
    print("  编辑器未找到，跳过评论")

time.sleep(3)

# 验证
print("\n=== 验证 ===")
url = run_js("window.location.href")
print(f"URL: {url}")
print(f"评论内容: {COMMENT_TEXT}")
