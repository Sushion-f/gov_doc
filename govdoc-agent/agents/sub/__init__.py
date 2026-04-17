from ..registry import AgentDefinition, AgentRegistry


def register_builtin_sub_agents() -> None:
    if AgentRegistry._registered:
        return

    AgentRegistry.register(
        AgentDefinition(
            name="retrieval",
            display_name="检索",
            description="从知识库、历史公文、法规库中检索相关内容。",
            system_prompt_path="prompts/sub/retrieval.md",
            tools=["knowledge_base_search", "law_search", "doc_history_query"],
            when_to_use="用户询问格式依据、法规依据、历史案例，或写作前需要补资料时。",
            when_not_to_use="用户已提供完整素材，不需要补充资料时。",
            metadata={
                "scope": "围绕主题检索资料、法规依据和历史案例，并提炼结构化信息。",
            },
            aliases=("search", "retrieve"),
            examples=["检索安全生产相关法规", "帮我找近三年的类似通知"],
            prompt_key="retrieval",
            default_objective="从现有知识库或参考资料中补充与当前任务相关的信息。",
        )
    )
    AgentRegistry.register(
        AgentDefinition(
            name="writing",
            display_name="写作",
            description="根据用户需求起草、续写、改写公文正文。",
            system_prompt_path="prompts/sub/writing.md",
            tools=["template_render", "doc_write", "outline_generate"],
            when_to_use="用户需要生成、续写、改写公文正文时。",
            when_not_to_use="用户只是咨询规则或查看资料，不需要生成正文时。",
            metadata={
                "scope": "基于用户要求与上下文起草、续写或改写公文正文。",
            },
            aliases=("write",),
            examples=["起草一份通知", "把这份通报改得更正式"],
            prompt_key="writing",
            default_objective="根据用户需求起草、续写或改写公文正文。",
        )
    )
    AgentRegistry.register(
        AgentDefinition(
            name="review",
            display_name="审核",
            description="对公文进行合规性、语义准确性、措辞规范性审核并标注问题。",
            system_prompt_path="prompts/sub/review.md",
            tools=["compliance_check", "semantic_check", "highlight_issues"],
            when_to_use="用户需要对已有公文进行审查、校对、风险评估时。",
            when_not_to_use="公文尚未起草或没有待审核文本时。",
            metadata={
                "scope": "围绕规范性、语义、错别字和逻辑问题输出审核意见。",
            },
            examples=["审核这份讲话稿", "帮我查一下有没有不规范表述"],
            prompt_key="review",
            default_objective="审核当前稿件并输出可执行的修改意见。",
        )
    )
    AgentRegistry.register(
        AgentDefinition(
            name="dedup",
            display_name="查重",
            description="检测公文内容与历史文档的相似度，并标注重复片段。",
            system_prompt_path="prompts/sub/dedup.md",
            tools=["similarity_search", "source_trace", "highlight_duplicate"],
            when_to_use="用户需要确认文本原创性或排查与已有文件重复时。",
            when_not_to_use="用户明确说明内容以引用汇编为主，不需要查重时。",
            metadata={
                "scope": "分析重复风险、相似来源和改写建议。",
            },
            aliases=("duplicate", "dup"),
            examples=["检查这份文件有没有和历史文档重复", "给这篇材料做查重"],
            prompt_key="dedup",
            default_objective="分析当前文本的重复风险并输出改写建议。",
        )
    )
    AgentRegistry.register(
        AgentDefinition(
            name="layout",
            display_name="排版",
            description="按照党政机关公文格式标准对公文进行排版建议或输出。",
            system_prompt_path="prompts/sub/layout.md",
            tools=["format_apply", "doc_export", "style_check"],
            when_to_use="用户需要将内容转换为标准公文格式、套用模板或导出时。",
            when_not_to_use="用户只需要内容建议，不需要格式处理时。",
            metadata={
                "scope": "推荐模板并给出符合党政机关标准的排版结果或建议。",
            },
            aliases=("format", "typeset"),
            examples=["按机关标准排版", "给这篇通知套个正式模板"],
            prompt_key="layout",
            default_objective="为当前稿件输出模板推荐与排版建议。",
        )
    )
    AgentRegistry._registered = True
