
"""LangGraph智能编排图实现 - 所有Agent都能自主调用MCP工具和知识库"""
import json
import logging
from typing import TypedDict, Annotated, List, Literal, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool

from .prompts import get_agent_prompt
from .context_compression import CompressionSettings, CompressionResult, ConversationCompressor
from knowledge.models import KnowledgeBase

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict):
    """编排状态定义"""
    messages: Annotated[List[AnyMessage], add_messages]
    requirement: str
    project_id: int  # 项目ID,用于数据隔离
    requirement_analysis: dict
    knowledge_docs: list
    testcases: list
    next_agent: str
    instruction: str
    reason: str
    current_step: int
    max_steps: int
    # 上下文压缩相关
    context_summary: Optional[str]
    summarized_message_count: int
    context_token_count: int


def create_knowledge_tool(project_id: int, max_retries: int = 3) -> Tool:
    """
    创建知识库搜索工具，自动重试最多3次
    
    Args:
        project_id: 项目ID
        max_retries: 最大重试次数
    
    Returns:
        LangChain Tool对象
    """
    def search_knowledge_base(query: str) -> str:
        """
        在项目的所有知识库中搜索相关文档，自动重试最多3次
        
        Args:
            query: 搜索查询字符串
        
        Returns:
            搜索结果摘要，如果没找到返回失败信息
        """
        logger.info(f"🔍 知识库工具被调用: query='{query}', max_retries={max_retries}")
        
        for attempt in range(max_retries):
            try:
                # 获取项目下所有激活的知识库
                project_kbs = KnowledgeBase.objects.filter(
                    project_id=project_id,
                    is_active=True
                )
                
                if not project_kbs.exists():
                    msg = f"项目 {project_id} 下没有可用的知识库"
                    logger.warning(msg)
                    return msg
                
                logger.info(f"  📚 第{attempt+1}次尝试: 在 {project_kbs.count()} 个知识库中搜索...")
                
                all_docs = []
                for kb in project_kbs:
                    try:
                        # 使用VectorStoreManager进行搜索
                        from knowledge.services import KnowledgeBaseService
                        kb_service = KnowledgeBaseService(kb)
                        results = kb_service.vector_manager.similarity_search(query, k=3, score_threshold=0.1)
                        if results:
                            all_docs.extend(results)
                            logger.info(f"    └─ {kb.name}: 找到 {len(results)} 个文档")
                    except Exception as e:
                        logger.error(f"    └─ {kb.name}: 搜索失败 {e}")
                
                if all_docs:
                    # 找到文档，返回摘要
                    docs_summary = "\n\n".join([
                        f"【文档{i+1}】来源: {doc.get('metadata', {}).get('source', '未知')}\n内容: {doc.get('content', '')[:300]}..."
                        for i, doc in enumerate(all_docs[:5])
                    ])
                    logger.info(f"  ✅ 第{attempt+1}次尝试成功: 找到 {len(all_docs)} 个文档")
                    return f"找到 {len(all_docs)} 个相关文档:\n\n{docs_summary}"
                else:
                    logger.info(f"  ⚠️ 第{attempt+1}次尝试: 未找到文档")
                    if attempt < max_retries - 1:
                        continue  # 继续重试
                    else:
                        return f"在 {project_kbs.count()} 个知识库中搜索了 {max_retries} 次，未找到与'{query}'相关的文档"
            
            except Exception as e:
                logger.error(f"  ❌ 第{attempt+1}次尝试失败: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    continue
                else:
                    return f"知识库搜索失败（重试{max_retries}次）: {str(e)}"
        
        return f"知识库搜索失败: 达到最大重试次数{max_retries}"
    
    return Tool(
        name="search_knowledge_base",
        description=f"在项目ID={project_id}的所有知识库中搜索相关文档。输入搜索查询，返回相关文档内容。自动重试最多{max_retries}次。适用于查找项目文档、需求、设计等信息。",
        func=search_knowledge_base
    )


class AgentNodes:
    """Agent节点实现 - 所有Agent都能使用MCP工具和知识库"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        user=None,
        mcp_tools=None,
        project_id=None,
        compression_settings: Optional[CompressionSettings] = None,
        model_name: Optional[str] = None
    ):
        self.llm = llm
        self.user = user
        self.project_id = project_id
        
        # 初始化上下文压缩器
        self.context_compressor = ConversationCompressor(
            llm=llm,
            model_name=model_name or getattr(llm, "model_name", "gpt-4o"),
            settings=compression_settings or CompressionSettings(),
        )
        
        # 创建完整的工具列表：MCP工具 + 知识库工具（用于子Agent）
        self.all_tools = list(mcp_tools or [])
        mcp_tool_count = len(mcp_tools or [])
        
        # 🔧 创建Brain专用的工具列表：只有knowledge_base验证工具，没有执行类工具
        self.brain_tools = []
        
        if project_id:
            knowledge_tool = create_knowledge_tool(project_id, max_retries=3)
            self.all_tools.append(knowledge_tool)
            self.brain_tools.append(knowledge_tool)  # Brain只有knowledge工具用于验证
            logger.info(f"✅ AgentNodes初始化: MCP工具={mcp_tool_count}个, 知识库工具=1个, 总计={len(self.all_tools)}个")
            logger.info(f"   Brain工具：只有knowledge_base（用于验证，不是执行）")
            if mcp_tool_count == 0:
                logger.warning(f"⚠️ 注意：没有MCP工具被加载！所有agent将只能使用知识库工具。")
            else:
                # 列出所有MCP工具名称
                mcp_tool_names = [tool.name for tool in mcp_tools] if mcp_tools else []
                logger.info(f"   可用MCP工具: {', '.join(mcp_tool_names)}")
        else:
            logger.info(f"✅ AgentNodes初始化: MCP工具={mcp_tool_count}个, 无知识库工具（未指定project_id）")
            if mcp_tool_count == 0:
                logger.warning(f"⚠️ 注意：没有任何工具被加载！所有agent将直接使用LLM，无工具支持。")
    
    def _create_agent_with_tools(self, system_prompt: str) -> create_react_agent:
        """创建带工具的ReAct Agent（已废弃，直接在各节点中创建Agent）"""
        logger.warning("⚠️ _create_agent_with_tools已废弃，不应被调用")
        if self.all_tools:
            return create_react_agent(self.llm, self.all_tools)
        else:
            # 没有工具时，返回None，调用方会直接使用LLM
            return None
    
    async def _prepare_context(self, state: OrchestratorState) -> CompressionResult:
        """准备上下文：执行Token检查和压缩"""
        try:
            return await self.context_compressor.prepare(
                messages=state.get("messages", []),
                summary_text=state.get("context_summary"),
                summarized_count=state.get("summarized_message_count", 0),
            )
        except Exception as exc:
            logger.error("上下文压缩失败: %s", exc, exc_info=True)
            return CompressionResult(
                messages=list(state.get("messages", [])),
                summary_message=None,
                state_updates={},
                triggered=False,
                token_count=state.get("context_token_count", 0) or 0,
            )
    
    def _render_history(self, messages: List[AnyMessage]) -> str:
        """渲染消息历史为文本（用于Brain状态分析）"""
        history_lines = []
        for msg in messages:
            label = getattr(msg, "additional_kwargs", {}).get("agent", msg.__class__.__name__)
            raw = getattr(msg, "content", "")
            text = raw if isinstance(raw, str) else str(raw)
            if len(text) > 160:
                text = f"{text[:160]}..."
            history_lines.append(f"- [{label}]: {text}")
        return "\n".join(history_lines)
    
    def _get_executed_agents(self, state: OrchestratorState) -> set:
        """获取已执行过的Agent集合"""
        executed = set()
        messages = state.get('messages', [])
        for msg in messages:
            if isinstance(msg, AIMessage):
                agent = msg.additional_kwargs.get('agent')
                if agent in ['chat', 'requirement', 'testcase']:
                    executed.add(agent)
        return executed
    
    def _get_last_agent(self, state: OrchestratorState) -> str:
        """获取最近执行的Agent"""
        messages = state.get('messages', [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                agent = msg.additional_kwargs.get('agent')
                if agent in ['chat', 'requirement', 'testcase']:
                    return agent
        return None
    
    def _is_chat_intent(self, requirement: str) -> bool:
        """判断是否是对话意图（而非测试任务）"""
        chat_keywords = ['你好', '您好', '什么', '介绍', '功能', '帮助', '如何使用']
        requirement_lower = requirement.lower()
        return any(keyword in requirement_lower for keyword in chat_keywords)
    
    def _determine_next_agent(self, state: OrchestratorState) -> tuple:
        """使用状态机逻辑确定下一个Agent
        
        Returns:
            (next_agent, reason): 下一个agent和选择原因
        """
        executed_agents = self._get_executed_agents(state)
        last_agent = self._get_last_agent(state)
        requirement = state.get('requirement', '')
        
        logger.info(f"[状态机决策] 已执行: {executed_agents}, 最近: {last_agent}")
        
        # 规则1：判断意图（对话 vs 测试任务）
        is_chat = self._is_chat_intent(requirement)
        
        if is_chat:
            # 对话流程：chat → END
            if 'chat' not in executed_agents:
                return 'chat', '用户咨询或对话，调用chat回应'
            else:
                return 'END', '对话已完成'
        
        # 规则2：测试任务流程：requirement → testcase → END
        # 优先级：requirement > testcase > END
        
        if 'requirement' not in executed_agents:
            return 'requirement', '首先分析测试需求'
        
        if 'testcase' not in executed_agents and state.get('requirement_analysis'):
            return 'testcase', '需求分析完成，生成测试用例'
        
        # 规则3：所有必要步骤完成
        if state.get('requirement_analysis') and state.get('testcases'):
            return 'END', '测试任务完成'
        
        # 规则4：异常情况 - requirement完成但没有分析结果
        if 'requirement' in executed_agents and not state.get('requirement_analysis'):
            logger.warning("[状态机] requirement已执行但没有分析结果，重新执行")
            executed_agents.discard('requirement')  # 允许重试
            return 'requirement', '重新分析需求（上次执行未产生结果）'
        
        # 默认：结束
        return 'END', '流程完成'
    
    async def _generate_instruction_with_llm(self, state: OrchestratorState, next_agent: str) -> str:
        """使用LLM生成给子Agent的指令"""
        requirement = state.get('requirement', '')
        
        # 为不同Agent生成不同的指令提示
        if next_agent == 'chat':
            prompt = f"用户说：{requirement}\n请生成友好的回应指令。"
        elif next_agent == 'requirement':
            prompt = f"测试需求：{requirement}\n请生成详细的需求分析指令，包括要分析的测试点和业务规则。"
        elif next_agent == 'testcase':
            analysis = state.get('requirement_analysis', {})
            prompt = f"需求分析结果：{json.dumps(analysis, ensure_ascii=False)}\n请生成测试用例生成指令，明确测试场景和覆盖范围。"
        else:
            return requirement
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是测试编排助手，负责生成清晰的执行指令。"),
                HumanMessage(content=prompt)
            ])
            instruction = response.content.strip()
            logger.info(f"[LLM指令生成] {next_agent}: {instruction[:100]}...")
            return instruction
        except Exception as e:
            logger.error(f"[LLM指令生成失败] {e}, 使用默认指令")
            return requirement
    
    async def brain_node(self, state: OrchestratorState) -> dict:
        """Brain Agent - ReAct Agent模式 + 状态机约束（异步版本）
        
        决策策略：
        1. Brain作为ReAct Agent，能使用工具（特别是search_knowledge_base）进行验证
        2. 使用状态机逻辑对决策结果进行约束和验证
        3. 防止重复调度和无效循环
        """
        logger.info("=== Brain Agent决策（ReAct + 状态机）===")
        
        # 执行上下文压缩
        compression = await self._prepare_context(state)
        
        current_step = state.get("current_step", 0)
        max_steps = state.get("max_steps", 10)
        
        if current_step >= max_steps:
            logger.warning(f"[Brain] 达到最大步骤限制 {max_steps}")
            return {"next_agent": "END", "reason": f"达到最大步骤{max_steps}", "current_step": current_step}
        
        # 获取状态信息
        executed_agents = self._get_executed_agents(state)
        last_agent = self._get_last_agent(state)
        requirement = state.get('requirement', '')
        
        # 构造Brain的状态上下文（帮助LLM理解当前状态）
        # 🔧 关键：包含完整的对话历史，让Brain LLM自己判断是否需要继续
        brain_prompt = await get_agent_prompt('brain', self.user)
        
        # 构建对话历史摘要（使用压缩后的消息）
        messages = state.get('messages', [])
        conversation_history = self._render_history(compression.messages)
        
        state_context = f"""当前任务状态分析：

📋 用户需求: {requirement}

📊 执行状态:
- 已执行的Agent: {', '.join(executed_agents) if executed_agents else '无'}
- 最近执行: {last_agent or '无'}
- 需求分析: {'✅ 已完成' if state.get('requirement_analysis') else '❌ 未完成'}
- 测试用例: {'✅ 已完成' if state.get('testcases') else '❌ 未完成'}
- 当前步骤: {current_step + 1}/{max_steps}
- 上下文Token: {compression.token_count}/{self.context_compressor.settings.max_context_tokens}

📜 对话上下文（已自动压缩）:
{conversation_history}

⚠️ 重要规则（状态机约束）:
1. **用户只和你对话**：子Agent的回复是给你看的，不是给用户看的。你需要基于子Agent的结果向用户回复
2. 测试Agent（requirement/testcase）只能调用一次，但chat可以多次调用（已执行: {executed_agents}）
3. 执行顺序: chat(对话) 或 requirement → testcase → END
4. **关键判断**：查看对话历史，如果chat已经回复了，你需要基于chat的结果向用户回复（返回END）；如果是新的用户问题，则调用chat获取信息
5. 测试任务：按requirement→testcase顺序执行，每个只调用一次
6. **工具使用规则**：
   - ✅ 你有knowledge_base工具，可以用来验证信息
   - ❌ 你没有get_project_name_and_id等执行类工具
   - ❌ 需要查询项目、数据等时，必须指派chat Agent去做
   - ✅ 你只负责验证和决策，不负责执行查询

请分析当前状态和对话历史，决定下一步行动。必须返回JSON格式:
{{"next_agent": "requirement|testcase|chat|END", "instruction": "给子Agent的具体指令", "reason": "选择理由（说明你的判断过程，包括是否检查了对话历史）"}}"""

        try:
            # 🔧 重要：Brain只使用knowledge_base验证工具，不使用执行类工具
            # Brain可以验证信息，但不应该自己动手查询项目数据等
            if self.brain_tools:
                logger.info(f"Brain使用ReAct模式（只有knowledge_base验证工具）")
                messages_with_prompt = [SystemMessage(content=brain_prompt), HumanMessage(content=state_context)]
                agent = create_react_agent(self.llm, self.brain_tools)
                result = await agent.ainvoke({"messages": messages_with_prompt})
                
                # 提取最终的AI响应
                ai_messages = [msg for msg in result['messages'] if isinstance(msg, AIMessage)]
                decision_text = ai_messages[-1].content if ai_messages else ""
            else:
                logger.info("Brain使用纯LLM决策（没有验证工具）")
                response = await self.llm.ainvoke([
                    SystemMessage(content=brain_prompt),
                    HumanMessage(content=state_context)
                ])
                decision_text = response.content
            
            logger.info(f"[Brain] ReAct响应:\n{decision_text}")
            
            # 解析JSON决策
            next_agent = "END"
            instruction = ""
            reason = ""
            
            if "{" in decision_text:
                json_str = decision_text[decision_text.find("{"):decision_text.rfind("}")+1]
                decision = json.loads(json_str)
                next_agent = decision.get("next_agent", "END")
                instruction = decision.get("instruction", "")
                reason = decision.get("reason", "")
            
            # 🔧 状态机验证和修正（防止LLM违反规则）
            original_next_agent = next_agent
            
            # 验证1：防止重复调用（但chat Agent例外，允许多轮对话）
            if next_agent in executed_agents and next_agent not in ['chat', 'END']:
                logger.warning(f"[状态机约束] LLM尝试重复调用 {next_agent}，自动修正")
                # 根据状态机确定正确的next_agent
                corrected_next, corrected_reason = self._determine_next_agent(state)
                next_agent = corrected_next
                reason = f"⚠️ 状态机修正：{original_next_agent}已执行。{corrected_reason}"
            elif next_agent == 'chat' and 'chat' in executed_agents:
                # chat允许重复调用，但记录日志
                logger.info(f"[状态机] 允许chat Agent重复调用（多轮对话）")
            
            # 验证2：确保执行顺序（requirement必须在testcase之前）
            if next_agent == 'testcase' and 'requirement' not in executed_agents:
                logger.warning(f"[状态机约束] 必须先执行requirement再执行testcase")
                next_agent = 'requirement'
                reason = f"⚠️ 状态机修正：必须先分析需求才能生成测试用例"
            
            # 验证3：任务完成判断
            if 'requirement' in executed_agents and 'testcase' in executed_agents:
                if next_agent not in ['END', 'chat']:
                    logger.info(f"[状态机约束] requirement和testcase都已完成，自动结束")
                    next_agent = 'END'
                    reason = f"✅ 测试任务已完成（需求分析和测试用例都已生成）"
            
            # 构造决策消息
            mode_label = "智能协调决策"
            if original_next_agent != next_agent:
                mode_label += f" [已修正: {original_next_agent}→{next_agent}]"
            
            formatted_decision = f"""🧠 Brain决策（{mode_label}）: {next_agent}

💡 指令: {instruction if instruction else '无'}

📝 推理: {reason}

📊 当前状态:
- 已执行: {', '.join(executed_agents) if executed_agents else '无'}
- 需求分析: {'✅' if state.get('requirement_analysis') else '⏳'}
- 测试用例: {'✅' if state.get('testcases') else '⏳'}
- 执行步骤: {current_step + 1}/{max_steps}"""
            
            brain_decision = AIMessage(
                content=formatted_decision,
                additional_kwargs={
                    "agent": "brain",
                    "agent_type": "orchestrator_brain_decision",
                    "next_agent": next_agent,
                    "instruction": instruction,
                    "reason": reason,
                    "decision_mode": "react_with_state_machine",
                    "was_corrected": original_next_agent != next_agent,
                    "original_decision": original_next_agent,
                    "is_thinking_process": True  # 🎨 标记为思考过程，前端默认折叠
                }
            )
            
            messages_to_add = [brain_decision]
            
            # 🔧 关键：当next_agent为END时，生成最终用户回复
            if next_agent == "END":
                logger.info("[Brain] 生成最终用户回复")
                
                # 收集子Agent的报告
                agent_reports = []
                for msg in messages:
                    if isinstance(msg, AIMessage) and msg.additional_kwargs.get('agent') in ['chat', 'requirement', 'testcase']:
                        agent_name = msg.additional_kwargs.get('agent')
                        agent_reports.append(f"[{agent_name}]:\n{msg.content}\n")
                
                reports_summary = "\n".join(agent_reports) if agent_reports else "无子Agent报告"
                
                # 让Brain基于子Agent报告生成最终用户回复
                final_response_prompt = f"""你现在需要生成最终的用户回复。

子Agent的内部报告：
{reports_summary}

用户需求：{requirement}

请基于子Agent的报告，生成一个清晰、友好、专业的回复给用户。
- 如果是对话任务，使用chat Agent建议的回复内容
- 如果是测试任务，总结需求分析和测试用例结果
- 回复要直接面向用户，不要提及"Brain"、"子Agent"等内部概念
- 保持友好、简洁、专业的语气"""

                final_response = await self.llm.ainvoke([
                    SystemMessage(content="你是测试助手，负责向用户提供友好、专业的回复"),
                    HumanMessage(content=final_response_prompt)
                ])
                
                # 创建最终用户回复消息
                user_response_message = AIMessage(
                    content=final_response.content,
                    additional_kwargs={
                        "agent": "brain",
                        "agent_type": "orchestrator_final_response",
                        "is_final_response": True
                    }
                )
                
                messages_to_add.append(user_response_message)
                logger.info(f"[Brain] 最终用户回复:\n{final_response.content}")
            
            result_payload = {
                "next_agent": next_agent,
                "instruction": instruction,
                "reason": reason,
                "messages": messages_to_add,
                "current_step": current_step + 1,
                "executed_agents": executed_agents,
                "requirement_analysis": state.get('requirement_analysis'),
                "testcases": state.get('testcases'),
                "max_steps": max_steps
            }
            # 合并压缩状态更新
            result_payload.update(compression.state_updates)
            return result_payload
            
        except Exception as e:
            logger.error(f"[Brain] 决策失败: {e}", exc_info=True)
            # fallback到状态机决策
            next_agent, reason = self._determine_next_agent(state)
            instruction = state.get('requirement', '')
            
            brain_decision = AIMessage(
                content=f"🧠 Brain决策（fallback状态机）: {next_agent}\n\n📝 推理: {reason}\n\n⚠️ 注意：LLM决策失败，使用状态机fallback",
                additional_kwargs={
                    "agent": "brain",
                    "agent_type": "orchestrator_brain_decision",
                    "next_agent": next_agent,
                    "instruction": instruction,
                    "reason": reason,
                    "decision_mode": "fallback_state_machine",
                    "is_thinking_process": True  # 🎨 标记为思考过程，前端默认折叠
                }
            )
            
            fallback_result = {
                "next_agent": next_agent,
                "instruction": instruction,
                "reason": reason,
                "messages": [brain_decision],
                "current_step": current_step + 1,
                "executed_agents": state.get('executed_agents', []),
                "requirement_analysis": state.get('requirement_analysis'),
                "testcases": state.get('testcases'),
                "max_steps": state.get('max_steps', 10)
            }
            fallback_result.update(compression.state_updates)
            return fallback_result
    
    async def chat_node(self, state: OrchestratorState) -> dict:
        """Chat Agent - 支持MCP工具和知识库（异步版本）"""
        logger.info("=== Chat Agent处理对话 ===")
        
        compression = await self._prepare_context(state)
        prompt = await get_agent_prompt('chat')
        instruction = state.get('instruction') or state.get('requirement')
        
        try:
            if self.all_tools:
                logger.info(f"Chat Agent使用 {len(self.all_tools)} 个工具")
                messages_with_prompt = [SystemMessage(content=prompt)] + compression.messages
                agent = create_react_agent(self.llm, self.all_tools)
                result = await agent.ainvoke({"messages": messages_with_prompt})
                
                ai_messages = [msg for msg in result['messages'] if isinstance(msg, AIMessage)]
                response_content = ai_messages[-1].content if ai_messages else "Chat Agent未返回有效响应"
            else:
                logger.info("Chat Agent直接使用LLM")
                response = await self.llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=instruction)])
                response_content = response.content
            
            chat_message = AIMessage(
                content=response_content,
                additional_kwargs={
                    "agent": "chat",
                    "agent_type": "orchestrator_agent",
                    "is_thinking_process": True
                }
            )
            
            result = dict(compression.state_updates)
            result["messages"] = [chat_message]
            return result
        except Exception as e:
            logger.error(f"对话处理失败: {e}", exc_info=True)
            result = dict(compression.state_updates)
            result["messages"] = [AIMessage(content=f"对话失败: {e}")]
            return result
    
    async def requirement_node(self, state: OrchestratorState) -> dict:
        """Requirement Agent - 支持MCP工具和知识库（异步版本）"""
        logger.info("=== Requirement Agent分析需求 ===")
        
        compression = await self._prepare_context(state)
        prompt = await get_agent_prompt('requirement')
        instruction = state.get('instruction') or state.get('requirement')
        
        try:
            if self.all_tools:
                logger.info(f"Requirement Agent使用 {len(self.all_tools)} 个工具")
                messages_with_prompt = [SystemMessage(content=prompt)] + compression.messages
                agent = create_react_agent(self.llm, self.all_tools)
                result = await agent.ainvoke({"messages": messages_with_prompt})
                
                ai_messages = [msg for msg in result['messages'] if isinstance(msg, AIMessage)]
                analysis_text = ai_messages[-1].content if ai_messages else "Requirement Agent未返回有效响应"
            else:
                logger.info("Requirement Agent直接使用LLM")
                response = await self.llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=f"分析需求:\n{instruction}")])
                analysis_text = response.content
            
            # 解析分析结果
            if "{" in analysis_text:
                json_str = analysis_text[analysis_text.find("{"):analysis_text.rfind("}")+1]
                analysis = json.loads(json_str)
            else:
                analysis = {"功能描述": instruction, "分析结果": analysis_text}
            
            requirement_message = AIMessage(
                content=analysis_text,
                additional_kwargs={
                    "agent": "requirement",
                    "agent_type": "orchestrator_agent",
                    "is_thinking_process": True
                }
            )
            
            result = dict(compression.state_updates)
            result.update({"requirement_analysis": analysis, "messages": [requirement_message]})
            return result
        except Exception as e:
            logger.error(f"需求分析失败: {e}", exc_info=True)
            result = dict(compression.state_updates)
            result.update({"requirement_analysis": {"error": str(e)}, "messages": [AIMessage(content=f"分析失败: {e}")]})
            return result
    

    
    async def testcase_node(self, state: OrchestratorState) -> dict:
        """TestCase Agent - 支持MCP工具和知识库（异步版本）"""
        logger.info("=== TestCase Agent生成测试用例 ===")
        
        compression = await self._prepare_context(state)
        prompt = await get_agent_prompt('testcase')
        requirement_analysis = state.get('requirement_analysis', {})
        knowledge_docs = state.get('knowledge_docs', [])
        
        # 添加用户信息到上下文
        user_info = ""
        if self.user:
            user_info = f"""
当前用户信息：
- 用户ID: {self.user.id}
- 用户名: {self.user.username}
- 姓名: {self.user.last_name or self.user.username}
"""
        
        context = f"""需求分析:
{json.dumps(requirement_analysis, ensure_ascii=False, indent=2)}

知识文档: {len(knowledge_docs)}个
{user_info}
请生成测试用例(JSON格式)。
"""
        
        try:
            if self.all_tools:
                logger.info(f"TestCase Agent使用 {len(self.all_tools)} 个工具")
                messages_with_prompt = [SystemMessage(content=prompt)] + compression.messages
                agent = create_react_agent(self.llm, self.all_tools)
                result = await agent.ainvoke({"messages": messages_with_prompt})
                
                ai_messages = [msg for msg in result['messages'] if isinstance(msg, AIMessage)]
                testcase_text = ai_messages[-1].content if ai_messages else "TestCase Agent未返回有效响应"
            else:
                logger.info("TestCase Agent直接使用LLM")
                response = await self.llm.ainvoke([SystemMessage(content=prompt), HumanMessage(content=context)])
                testcase_text = response.content
            
            # 解析测试用例
            if "{" in testcase_text:
                json_str = testcase_text[testcase_text.find("{"):testcase_text.rfind("}")+1]
                testcases_data = json.loads(json_str)
                testcases = testcases_data.get("测试用例", [])
            else:
                testcases = [{"内容": testcase_text}]
            
            testcase_message = AIMessage(
                content=testcase_text,
                additional_kwargs={
                    "agent": "testcase",
                    "agent_type": "orchestrator_agent",
                    "is_thinking_process": True
                }
            )
            
            result = dict(compression.state_updates)
            result.update({"testcases": testcases, "messages": [testcase_message]})
            return result
        except Exception as e:
            logger.error(f"测试用例生成失败: {e}", exc_info=True)
            result = dict(compression.state_updates)
            result.update({"testcases": [], "messages": [AIMessage(content=f"生成失败: {e}")]})
            return result


def create_orchestrator_graph(
    llm: ChatOpenAI,
    checkpointer=None,
    user=None,
    mcp_tools=None,
    project_id=None,
    compression_settings: Optional[CompressionSettings] = None,
    model_name: Optional[str] = None
) -> StateGraph:
    """创建智能编排图
    
    Args:
        llm: LLM实例
        checkpointer: 可选的checkpointer,用于保存对话历史
        user: 可选的用户对象,用于获取用户自定义提示词
        mcp_tools: 可选的MCP工具列表
        project_id: 项目ID，用于创建知识库工具
        compression_settings: 上下文压缩配置
        model_name: 模型名称（用于Token计数）
    """
    
    nodes = AgentNodes(
        llm,
        user,
        mcp_tools,
        project_id,
        compression_settings=compression_settings,
        model_name=model_name
    )
    workflow = StateGraph(OrchestratorState)
    
    # 添加节点
    workflow.add_node("brain_agent", nodes.brain_node)
    workflow.add_node("chat_agent", nodes.chat_node)
    workflow.add_node("requirement_agent", nodes.requirement_node)
    workflow.add_node("testcase_agent", nodes.testcase_node)
    
    # 路由函数
    def router(state: OrchestratorState) -> Literal["chat_agent", "requirement_agent", "testcase_agent", "__end__"]:
        next_agent = state.get("next_agent", "END")
        if next_agent == "chat":
            return "chat_agent"
        elif next_agent == "requirement":
            return "requirement_agent"
        elif next_agent == "testcase":
            return "testcase_agent"
        else:
            return "__end__"
    
    # 条件边
    workflow.add_conditional_edges(
        "brain_agent",
        router,
        {
            "chat_agent": "chat_agent",
            "requirement_agent": "requirement_agent",
            "testcase_agent": "testcase_agent",
            "__end__": END
        }
    )
    
    # 所有子Agent返回Brain继续决策（让Brain协调整个流程）
    workflow.add_edge("chat_agent", "brain_agent")
    workflow.add_edge("requirement_agent", "brain_agent")
    workflow.add_edge("testcase_agent", "brain_agent")
    
    # 入口点
    workflow.set_entry_point("brain_agent")
    
    # 编译时传入checkpointer
    return workflow.compile(checkpointer=checkpointer)
