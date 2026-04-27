"""
.govdoc-agent 功能测试脚本

启动后会按照以下流程调用接口并输出返回结果：
1. 调用 POST /api/agentloop/conversations/run 创建会话并运行
2. 调用返回的 streamUrl 获取流式响应，输出到 response.txt
"""

import json
import os
import sys

import requests

BASE_URL = "http://127.0.0.1:8000"

# 请求头（根据实际认证方式调整）
HEADERS = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer your-token-here",
    "Cookie": "SESSION=5603c739-698f-4a18-b644-451c41cb2dca",
}


def step1_create_and_run():
    """步骤1：创建会话并运行"""
    print("=" * 60)
    print("步骤 1：调用 POST /api/agentloop/conversations/run")
    print("=" * 60)

    url = f"{BASE_URL}/api/agentloop/conversations/run"

    payload = {
        "content": "请帮我生成一篇五一放假的通知",
        "title": "五一放假通知",
        "model": "Qwen3-235B-A22B-FP8",
        "skill": "",
        "attachments": []
    }

    print(f"请求 URL: {url}")
    print(f"请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print()

    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        result = response.json()

        print("响应状态码:", response.status_code)
        print("响应内容:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if result.get("code") != 0:
            print(f"\n错误: {result.get('message')}")
            sys.exit(1)

        data = result.get("data", {})
        conversation_id = data.get("conversationId")
        run_id = data.get("runId")
        stream_url = data.get("streamUrl")

        if not stream_url:
            print("\n错误: 未返回 streamUrl")
            sys.exit(1)

        print(f"\nconversationId: {conversation_id}")
        print(f"runId: {run_id}")
        print(f"streamUrl: {stream_url}")

        return stream_url

    except requests.exceptions.RequestException as e:
        print(f"\n请求失败: {e}")
        sys.exit(1)


def step2_stream_events(stream_url: str):
    """步骤2：获取流式响应"""
    print()
    print("=" * 60)
    print("步骤 2：调用流式接口获取事件")
    print("=" * 60)

    url = f"{BASE_URL}{stream_url}"
    output_file = os.path.join(os.path.dirname(__file__), "response.txt")

    # 清空 response.txt 文件
    with open(output_file, "w", encoding="utf-8") as f:
        pass

    print(f"请求 URL: {url}")
    print(f"输出文件: {output_file}")
    print()

    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=300)
        response.raise_for_status()

        event_count = 0
        with open(output_file, "a", encoding="utf-8") as f:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        print("[DONE] 流式响应结束")
                        f.write("[DONE]\n")
                        break
                    try:
                        event = json.loads(data)
                        event_count += 1
                        event_type = event.get("type", "unknown")
                        print(f"[事件 {event_count}] type={event_type}")
                        f.write(json.dumps(event, ensure_ascii=False) + "\n\n")
                    except json.JSONDecodeError:
                        f.write(data + "\n")

        print(f"\n共接收 {event_count} 个事件")
        print(f"结果已保存到: {output_file}")

    except requests.exceptions.RequestException as e:
        print(f"\n请求失败: {e}")
        sys.exit(1)


def main():
    print("开始测试 .govdoc-agent")
    print(f"接口域名: {BASE_URL}")
    print()

    stream_url = step1_create_and_run()
    step2_stream_events(stream_url)

    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
