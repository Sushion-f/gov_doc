# 警务大脑 API 接口文档

## 概述

本文档定义了警务大脑模块的所有API接口规范，包括对话、Claw专家调用、数据源管理、心跳任务、文档生成和数据分析等功能。

## 基础信息

- **Base URL**: `/api/chat`
- **认证方式**: Bearer Token (JWT)
- **请求格式**: JSON
- **响应格式**: JSON / SSE (流式响应)

## 通用响应格式

### 普通响应

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 流式响应 (SSE)

```
data: {"type": "step", "data": {...}}

data: {"type": "document", "data": {...}}

data: [DONE]
```

### 错误码说明

| 错误码 | 说明           |
| ------ | -------------- |
| 0      | 成功           |
| 1001   | 参数错误       |
| 1002   | 认证失败       |
| 1003   | 权限不足       |
| 1004   | 资源不存在     |
| 2001   | Claw调用失败   |
| 2002   | 数据源连接失败 |
| 2003   | 文档生成失败   |
| 2004   | 分析任务失败   |

---

## 1. 对话接口 (Chat)

### 1.1 流式消息 (推荐)

**接口**: `POST /chat/stream`

**描述**: 发送消息并获取流式响应（SSE），支持实时展示处理进度和结果

**请求参数**:

| 参数名      | 类型   | 必填 | 说明                              |
| ----------- | ------ | ---- | --------------------------------- |
| sessionId   | string | 否   | 会话ID，不传则创建新会话          |
| content     | string | 是   | 用户输入内容                      |
| model       | string | 否   | 模型选择: minimax, qwen, deepseek |
| clawId      | string | 否   | 指定调用的Claw ID                 |
| attachments | array  | 否   | 附件列表                          |

**请求示例**:

```json
{
  "sessionId": "session_123",
  "content": "帮我写一篇警务公文",
  "model": "qwen",
  "clawId": "document_expert",
  "attachments": []
}
```

**响应格式**: Server-Sent Events (SSE)

**事件类型说明**:

| 事件类型  | 说明     | 数据结构                          |
| --------- | -------- | --------------------------------- |
| step      | 步骤更新 | Step对象                          |
| document  | 文档输出 | Document对象                      |
| analysis  | 分析结果 | Analysis对象                      |
| heartbeat | 心跳任务 | HeartbeatTask对象                 |
| text      | 文本消息 | string                            |
| done      | 流结束   | { messageId: string }             |
| error     | 错误信息 | { code: number, message: string } |

**响应示例**:

```
data: {"type": "step", "data": {"type": "think", "label": "Lead Agent 分析任务中"}}

data: {"type": "step", "data": {"type": "tool", "label": "工具调用 · to_do_list", "contentType": "pre", "content": "✓ 文章摘要与文章框架构思\n✓ 参考资料检索\n✓ 文章生成", "open": true}}

data: {"type": "step", "data": {"type": "claw", "label": "Claw 调用 · <strong>公文专家</strong>", "contentType": "html", "content": "调用公文专家 Claw，依据 GB/T 9704-2012 标准生成党政机关公文。<br>文种识别：通知 &nbsp;·&nbsp; 发文机关：XX市人民政府办公室 &nbsp;·&nbsp; 语言风格：正式", "open": true}}

data: {"type": "step", "data": {"type": "skill", "label": "Skills 调用 · doc_format + compliance_check", "contentType": "skills", "content": {"summary": "共调用 <strong>2</strong> 个 Skills", "skills": ["doc_format", "compliance_check"]}, "open": true}}

data: {"type": "step", "data": {"type": "tool", "label": "工具调用 · search", "contentType": "html", "content": "<div class=\"search-result-summary\">共找到 <strong>12</strong> 条相关资料，已引用 <strong>3</strong> 条</div>...", "open": true}}

data: {"type": "step", "data": {"type": "cli", "label": "CLI 工具 · read_file", "contentType": "pre", "content": "read_file(\"templates/gov_notice_template.docx\")\n→ 读取标准公文模板，提取格式要素", "open": true}}

data: {"type": "document", "data": {"title": "关于推进政务数字化转型工作的通知.docx", "org": "XX 市人民政府办公室", "issueNo": "XX 政办发〔2025〕12 号", "mainTitle": "关于推进政务数字化转型工作的通知", "recipients": "各部门、各单位：", "body": "<p>为深入贯彻落实...</p>", "footerOrg": "XX市人民政府办公室", "footerDate": "2025年3月22日"}}

data: {"type": "done", "data": {"messageId": "msg_456"}}

data: [DONE]
```

**前端调用示例**:

```javascript
import { streamMessage } from '@/api';

const abort = streamMessage(
  { content: '帮我写一篇警务公文' },
  (message) => {
    switch (message.type) {
      case 'step':
        // 添加步骤到列表
        steps.value.push(message.data);
        break;
      case 'document':
        // 显示文档
        document.value = message.data;
        break;
      case 'analysis':
        // 显示分析结果
        analysis.value = message.data;
        break;
      case 'heartbeat':
        // 显示心跳任务
        heartbeatTask.value = message.data;
        break;
      case 'text':
        // 显示文本消息
        text.value = message.data;
        break;
      case 'done':
        // 流结束
        console.log('Stream completed:', message.data.messageId);
        break;
    }
  },
  (error) => {
    console.error('Stream error:', error);
  },
  () => {
    console.log('Stream completed');
  },
);

// 取消请求
// abort();
```

### 1.2 发送消息 (非流式)

**接口**: `POST /chat/send`

**描述**: 发送消息并获取完整响应（不推荐，建议使用流式接口）

**请求参数**: 同 1.1

**响应示例**:

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sessionId": "session_123",
    "messageId": "msg_456",
    "role": "assistant",
    "steps": [
      {
        "type": "think",
        "label": "Lead Agent 分析任务中"
      }
    ],
    "document": {
      "title": "关于推进政务数字化转型工作的通知.docx",
      "content": "..."
    }
  }
}
```

### 1.3 获取聊天历史

**接口**: `GET /chat/history/{sessionId}`

**请求参数**:

| 参数名    | 类型   | 必填 | 说明             |
| --------- | ------ | ---- | ---------------- |
| sessionId | string | 是   | 会话ID           |
| page      | number | 否   | 页码，默认1      |
| pageSize  | number | 否   | 每页数量，默认20 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 50,
    "list": [
      {
        "id": "msg_001",
        "role": "user",
        "content": "帮我写一篇警务公文",
        "createdAt": "2025-04-05T10:00:00Z"
      },
      {
        "id": "msg_002",
        "role": "assistant",
        "steps": [...],
        "document": {...},
        "createdAt": "2025-04-05T10:00:05Z"
      }
    ]
  }
}
```

### 1.4 创建新对话

**接口**: `POST /chat/new`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "sessionId": "session_new_123",
    "createdAt": "2025-04-05T10:00:00Z"
  }
}
```

### 1.5 删除对话

**接口**: `DELETE /chat/{sessionId}`

### 1.6 重命名对话

**接口**: `PUT /chat/{sessionId}/rename`

**请求参数**:

| 参数名 | 类型   | 必填 | 说明   |
| ------ | ------ | ---- | ------ |
| title  | string | 是   | 新标题 |

### 1.7 置顶对话

**接口**: `PUT /chat/{sessionId}/pin`

**请求参数**:

| 参数名 | 类型    | 必填 | 说明     |
| ------ | ------- | ---- | -------- |
| pinned | boolean | 是   | 是否置顶 |

---

## 2. Claw专家接口

### 2.1 获取Claw列表

**接口**: `GET /claw/list`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "document_expert",
        "name": "公文写作专家",
        "description": "依据GB/T 9704-2012标准生成党政机关公文",
        "icon": "document",
        "status": "online"
      },
      {
        "id": "report_expert",
        "name": "工单报告专家",
        "description": "生成各类工单分析报告和周报",
        "icon": "report",
        "status": "online"
      }
    ]
  }
}
```

### 2.2 获取Claw详情

**接口**: `GET /claw/{clawId}`

### 2.3 调用Claw

**接口**: `POST /claw/{clawId}/invoke`

**请求参数**:

| 参数名    | 类型   | 必填 | 说明     |
| --------- | ------ | ---- | -------- |
| sessionId | string | 否   | 会话ID   |
| input     | object | 是   | 输入参数 |
| options   | object | 否   | 调用选项 |

### 2.4 获取Claw提示词

**接口**: `GET /claw/{clawId}/prompts`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "prompts": ["帮我写一份通知", "起草一份会议纪要", "撰写工作汇报"]
  }
}
```

### 2.5 申请Claw

**接口**: `POST /claw/apply`

**请求参数**:

| 参数名   | 类型   | 必填 | 说明     |
| -------- | ------ | ---- | -------- |
| clawType | string | 是   | Claw类型 |
| reason   | string | 是   | 申请原因 |
| useCase  | string | 否   | 使用场景 |

---

## 3. 数据源接口

### 3.1 获取数据源列表

**接口**: `GET /datasource/list`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "ds_001",
        "name": "mysql_test",
        "type": "MySQL 8.0.32",
        "host": "192.168.1.100",
        "tables": 10,
        "records": 1200,
        "status": "online",
        "lastSync": "2025-04-05T09:00:00Z"
      }
    ]
  }
}
```

### 3.2 添加数据源

**接口**: `POST /datasource/add`

**请求参数**:

| 参数名   | 类型   | 必填 | 说明                                   |
| -------- | ------ | ---- | -------------------------------------- |
| type     | string | 是   | 数据源类型: mysql, postgresql, mongodb |
| name     | string | 是   | 数据源名称                             |
| host     | string | 是   | 主机地址                               |
| port     | number | 是   | 端口                                   |
| username | string | 是   | 用户名                                 |
| password | string | 是   | 密码                                   |
| database | string | 是   | 数据库名                               |

### 3.3 删除数据源

**接口**: `DELETE /datasource/{sourceId}`

### 3.4 测试数据源连接

**接口**: `POST /datasource/test`

**请求参数**: 同 3.2

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "connected": true,
    "version": "MySQL 8.0.32",
    "tables": 10
  }
}
```

### 3.5 同步数据源

**接口**: `POST /datasource/{sourceId}/sync`

---

## 4. 心跳任务接口

### 4.1 获取心跳任务列表

**接口**: `GET /heartbeat/list`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "ht_001",
        "summary": "截至3/27 15:00，刚才已新增了20条标签",
        "status": "pending",
        "createdAt": "2025-04-05T15:00:00Z"
      }
    ]
  }
}
```

### 4.2 获取心跳任务详情

**接口**: `GET /heartbeat/{taskId}`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "ht_001",
    "summary": "截至3/27 15:00，刚才已新增了20条标签，具体明细如下:",
    "items": [
      {
        "id": "item_001",
        "level1": "",
        "level2": "",
        "level3": "",
        "level4": "违规停车举报",
        "description": ""
      }
    ],
    "levelOptions": {
      "level1": ["治安管理", "交通管理", "城市管理"],
      "level2": ["警情处置", "案件办理", "巡逻防控"],
      "level3": ["一般警情", "重大警情", "紧急警情"]
    }
  }
}
```

### 4.3 保存心跳任务

**接口**: `POST /heartbeat/save`

**请求参数**:

| 参数名              | 类型   | 必填 | 说明       |
| ------------------- | ------ | ---- | ---------- |
| items               | array  | 是   | 任务项列表 |
| items[].id          | string | 否   | 项目ID     |
| items[].level1      | string | 否   | 一级热点   |
| items[].level2      | string | 否   | 二级热点   |
| items[].level3      | string | 否   | 三级热点   |
| items[].level4      | string | 是   | 四级热点   |
| items[].description | string | 否   | 说明       |

### 4.4 更新心跳任务

**接口**: `PUT /heartbeat/{taskId}`

### 4.5 删除心跳任务

**接口**: `DELETE /heartbeat/{taskId}`

---

## 5. 文档接口

### 5.1 生成文档

**接口**: `POST /document/generate`

**请求参数**:

| 参数名   | 类型   | 必填 | 说明                              |
| -------- | ------ | ---- | --------------------------------- |
| type     | string | 是   | 文档类型: notice, report, summary |
| title    | string | 否   | 文档标题                          |
| content  | string | 否   | 内容描述                          |
| template | string | 否   | 模板ID                            |
| format   | string | 否   | 输出格式: docx, pdf               |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "docId": "doc_001",
    "title": "关于推进政务数字化转型工作的通知.docx",
    "org": "XX 市人民政府办公室",
    "issueNo": "XX 政办发〔2025〕12 号",
    "content": "...",
    "downloadUrl": "/api/chat/document/doc_001/download"
  }
}
```

### 5.2 获取文档详情

**接口**: `GET /document/{docId}`

### 5.3 下载文档

**接口**: `GET /document/{docId}/download`

**响应**: 文件流 (application/octet-stream)

### 5.4 编辑文档

**接口**: `PUT /document/{docId}`

### 5.5 删除文档

**接口**: `DELETE /document/{docId}`

### 5.6 获取文档模板

**接口**: `GET /document/templates`

---

## 6. 分析接口

### 6.1 执行数据分析

**接口**: `POST /analysis/analyze`

**请求参数**:

| 参数名       | 类型   | 必填 | 说明                                |
| ------------ | ------ | ---- | ----------------------------------- |
| dataSourceId | string | 是   | 数据源ID                            |
| analysisType | string | 是   | 分析类型: complaint, crime, traffic |
| dateRange    | object | 否   | 日期范围                            |
| filters      | object | 否   | 过滤条件                            |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "analysisId": "ana_001",
    "title": "典型问题分析报告 · 2025Q1",
    "summary": "共分析 1,248 条工单，识别出 5 类典型投诉问题",
    "chartData": [
      { "label": "交通违规", "value": 342, "percent": 82 },
      { "label": "噪音扰民", "value": 218, "percent": 52 }
    ]
  }
}
```

### 6.2 获取分析结果

**接口**: `GET /analysis/{analysisId}`

### 6.3 导出分析报告

**接口**: `GET /analysis/{analysisId}/export`

**请求参数**:

| 参数名 | 类型   | 必填 | 说明                       |
| ------ | ------ | ---- | -------------------------- |
| format | string | 是   | 导出格式: pdf, excel, word |

### 6.4 获取分析历史

**接口**: `GET /analysis/history`

---

## 附录

### A. 数据类型定义

#### StreamMessage 流式消息对象

```typescript
interface StreamMessage {
  type: 'step' | 'document' | 'analysis' | 'heartbeat' | 'text' | 'done' | 'error';
  data: Step | Document | Analysis | HeartbeatTask | string | { messageId: string } | { code: number; message: string };
}
```

#### Step 步骤对象

```typescript
interface Step {
  type: 'think' | 'tool' | 'claw' | 'skill' | 'cli';
  label: string;
  contentType?: 'pre' | 'html' | 'skills';
  content?: string | StepContent;
  open?: boolean;
}

interface StepContent {
  summary?: string;
  skills?: string[];
}
```

#### Document 文档对象

```typescript
interface Document {
  title: string;
  org: string;
  issueNo: string;
  mainTitle: string;
  recipients: string;
  body: string;
  footerOrg: string;
  footerDate: string;
}
```

#### Analysis 分析对象

```typescript
interface Analysis {
  title: string;
  summary: string;
  chartTitle: string;
  chartData: ChartDataItem[];
}

interface ChartDataItem {
  label: string;
  value: number;
  percent: number;
}
```

#### DataSource 数据源对象

```typescript
interface DataSource {
  id: string;
  name: string;
  type: string;
  host: string;
  tables: number;
  records: number;
  status: 'online' | 'offline';
  lastSync: string;
}
```

#### HeartbeatTask 心跳任务对象

```typescript
interface HeartbeatTask {
  id: string;
  summary: string;
  items: HeartbeatTaskItem[];
  levelOptions: LevelOptions;
}

interface HeartbeatTaskItem {
  id: string;
  level1: string;
  level2: string;
  level3: string;
  level4: string;
  description: string;
}

interface LevelOptions {
  level1: string[];
  level2: string[];
  level3: string[];
}
```

### B. 错误响应示例

```json
{
  "code": 1001,
  "message": "参数错误：content 不能为空",
  "data": null
}
```

### C. 流式响应错误示例

```
data: {"type": "error", "data": {"code": 1001, "message": "参数错误：content 不能为空"}}

data: [DONE]
```
