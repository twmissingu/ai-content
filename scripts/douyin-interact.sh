#!/bin/bash
# 抖音互动脚本 - 点赞+收藏+评论
# 用法: bash scripts/douyin-interact.sh "评论内容"

COMMENT_TEXT="${1:-干货满满，学到了！}"

# base64编码评论内容
COMMENT_B64=$(echo -n "$COMMENT_TEXT" | base64)

# 使用AppleScript直接执行JS，用双引号包裹，内部JS用单引号
run_js() {
    osascript -e "tell application \"Google Chrome\" to execute active tab of front window javascript \"$1\""
}

echo "[1/5] 点赞..."
run_js "document.querySelector('[data-e2e=video-player-digg]').click()'ok'"
sleep 1

echo "[2/5] 收藏..."
run_js "document.querySelector('[data-e2e=video-player-collect]').click()'ok'"
sleep 1

echo "[3/5] 展开评论区..."
run_js "document.querySelector('[data-e2e=feed-comment-icon]').click()'ok'"
sleep 2

echo "[4/5] 激活评论框..."
run_js "document.querySelector('.comment-input-inner-container').click()'ok'"
sleep 2

echo "[5/5] 输入评论并提交..."
run_js "var e=document.querySelector('.public-DraftEditor-content');if(e){e.focus();document.execCommand('insertText',false,atob('$COMMENT_B64'));'typed'}else{'no editor'}"
sleep 1

# 使用AppleScript原生keystroke提交，但先确保焦点在编辑器上
osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "document.querySelector(\".public-DraftEditor-content\").focus()"focused""'
sleep 0.5
osascript -e 'tell application "System Events" to tell process "Google Chrome" to keystroke return'
sleep 3

# 验证
echo "=== 验证 ==="
URL=$(osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "window.location.href"')
echo "当前URL: $URL"
echo "完成！评论内容: $COMMENT_TEXT"
