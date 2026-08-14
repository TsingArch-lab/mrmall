# LLM Contract — Model-Agnostic Review Core

## 1. 唯一要求

核心 Review 不依赖任何厂商 SDK。目标模型只需要完成一个抽象能力：

```text
generate(messages, response_schema?) -> model_output
```

其中 `response_schema` 可选。若平台不支持原生 Structured Output，则把 JSON Schema 作为 Prompt 的一部分，并在本地做 JSON 校验。

## 2. 模型不得拥有的权限

模型不能：
- 读取 Rules 后自行扩展标准；
- 修改 Registry / Gate；
- 自己决定正式 Gate 结果；
- 将未命中 Rule 的编辑意见加入反馈；
- 因不确定而默认 FAIL。

## 3. Provider Adapter 边界

OpenAI / Anthropic / Gemini / DeepSeek / Qwen / GLM / 本地模型等仅负责把统一请求转换成各自 API。Adapter 不得包含任何审稿标准。

## 4. 最低兼容模式

即使平台完全不支持 JSON Schema，只要能粘贴长文本并返回文本，也可使用 `CHAT_UI_WORKFLOW.md` 手工运行两阶段流程。

## 5. 搜索能力

事实核验是可插拔能力，不属于 LLM 核心接口。没有搜索能力的平台仍能运行 Review Core，但不得伪造核验结果。
