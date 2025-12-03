"""
Agent Loop 编排器

实现分步执行 + Blackboard 状态管理，解决 Token 累积问题。

核心思路：
- 将长对话拆分为多个独立的 AI 调用（每次独立上下文）
- 通过 Blackboard 传递历史摘要（而非完整工具输出）
- AI 自主决策下一步操作
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .models import AgentTask, AgentStep, AgentBlackboard
from langgraph_integration.models import ChatSession

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Agent Loop 编排器"""
    
    DEFAULT_MAX_STEPS = 500
    DEFAULT_HISTORY_WINDOW = 10  # 传给 AI 的历史条数
    
    # AI 决策提示词
    STEP_SYSTEM_PROMPT = """你是一个智能助手，正在执行用户的任务。

## 任务目标
{goal}

## 最近对话上下文
{conversation_history}

## 当前任务步骤记录
{history}

## 当前状态
{current_state}

## 指令
根据以上信息，决定下一步操作：
1. 如果需要使用工具，请调用相应工具
2. 如果任务已完成，直接给出最终回答
3. 如果遇到问题无法继续，说明原因

注意：每次只执行一个操作，执行后会收到结果再决定下一步。
"""

    def __init__(self, llm, tools=None, max_steps: int = None):
        """
        初始化编排器
        
        Args:
            llm: LangChain LLM 实例
            tools: 可用的工具列表
            max_steps: 最大步骤数
        """
        self.llm = llm
        self.tools = tools or []
        self.max_steps = max_steps or self.DEFAULT_MAX_STEPS
        
        # 如果有工具，绑定到 LLM
        if self.tools:
            self.llm_with_tools = llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = llm
    
    async def execute(
        self,
        goal: str,
        session: ChatSession,
        initial_context: Dict = None
    ) -> Dict[str, Any]:
        """
        执行 Agent 任务
        
        Args:
            goal: 用户目标/请求
            session: 对话会话
            initial_context: 初始上下文（可选）
            
        Returns:
            执行结果字典
        """
        # 1. 创建任务和 Blackboard
        task = await self._create_task(goal, session)
        blackboard = await self._create_blackboard(task, initial_context)
        
        logger.info(f"AgentOrchestrator: 开始执行任务 {task.id}, 目标: {goal[:100]}")
        
        try:
            # 2. Agent Loop
            while task.current_step < self.max_steps:
                task.current_step += 1
                task.status = 'running'
                await self._save_task(task)
                
                # 2.1 构建本步骤的上下文
                step_context = self._build_step_context(blackboard, goal)
                
                # 2.2 执行单步
                step_result = await self._execute_step(task, step_context)
                
                # 2.3 更新 Blackboard
                await self._update_blackboard(blackboard, step_result)
                
                # 2.4 检查是否完成
                if step_result.get('is_final'):
                    task.status = 'completed'
                    task.final_response = step_result.get('response', '')
                    task.completed_at = timezone.now()
                    await self._save_task(task)
                    
                    logger.info(f"AgentOrchestrator: 任务 {task.id} 完成，共 {task.current_step} 步")
                    
                    return {
                        'status': 'completed',
                        'response': task.final_response,
                        'steps': task.current_step,
                        'history': blackboard.history_summary,
                        'task_id': task.id
                    }
                
                # 2.5 检查是否有错误需要停止
                if step_result.get('error'):
                    task.status = 'failed'
                    task.error_message = step_result['error']
                    await self._save_task(task)
                    
                    return {
                        'status': 'failed',
                        'error': step_result['error'],
                        'steps': task.current_step,
                        'task_id': task.id
                    }
            
            # 超过最大步骤
            task.status = 'failed'
            task.error_message = f'超过最大步骤数 {self.max_steps}'
            await self._save_task(task)
            
            return {
                'status': 'failed',
                'error': task.error_message,
                'steps': task.current_step,
                'partial_response': blackboard.history_summary,
                'task_id': task.id
            }
            
        except Exception as e:
            logger.error(f"AgentOrchestrator: 任务 {task.id} 执行失败: {e}", exc_info=True)
            task.status = 'failed'
            task.error_message = str(e)
            await self._save_task(task)
            
            return {
                'status': 'failed',
                'error': str(e),
                'steps': task.current_step,
                'task_id': task.id
            }
    
    async def _create_task(self, goal: str, session: ChatSession) -> AgentTask:
        """创建任务"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def create():
            return AgentTask.objects.create(
                session=session,
                goal=goal,
                max_steps=self.max_steps,
                status='pending'
            )
        
        return await create()
    
    async def _create_blackboard(
        self,
        task: AgentTask,
        initial_context: Dict = None
    ) -> AgentBlackboard:
        """创建 Blackboard"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def create():
            return AgentBlackboard.objects.create(
                task=task,
                history_summary=[],
                current_state=initial_context or {},
                context_variables={}
            )
        
        return await create()
    
    async def _save_task(self, task: AgentTask):
        """保存任务状态"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def save():
            task.save()
        
        await save()
    
    def _build_step_context(self, blackboard: AgentBlackboard, goal: str) -> Dict:
        """
        构建单步执行的上下文（精简版）
        
        不包含完整的工具输出，只包含历史摘要
        """
        history = blackboard.get_recent_history(self.DEFAULT_HISTORY_WINDOW)
        history_text = '\n'.join([f"- {h}" for h in history]) if history else '（无历史）'
        
        current_state = blackboard.current_state or {}
        
        # 提取跨对话历史（从 initial_context 传入）
        conversation_history = current_state.get('conversation_history', '')
        conversation_history_text = conversation_history if conversation_history else '（无对话历史）'
        
        # ⚠️ 修复：从 current_state 中排除 conversation_history，避免重复传递给 LLM
        state_for_prompt = {k: v for k, v in current_state.items() if k != 'conversation_history'}
        state_text = json.dumps(state_for_prompt, ensure_ascii=False, indent=2) if state_for_prompt else '（无）'
        
        return {
            'goal': goal,
            'conversation_history': conversation_history_text,
            'history': history_text,
            'current_state': state_text,
            'context_variables': blackboard.context_variables
        }
    
    async def _execute_step(self, task: AgentTask, context: Dict) -> Dict[str, Any]:
        """
        执行单步
        
        这是一次独立的 AI 调用，上下文不累积
        """
        start_time = time.time()
        
        # 构建消息（独立上下文）
        system_prompt = self.STEP_SYSTEM_PROMPT.format(**context)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="请执行下一步操作。")
        ]
        
        try:
            # 调用 AI
            response = await self._invoke_llm(messages)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 解析响应
            result = await self._parse_ai_response(response)
            
            # 如果有工具调用，执行工具
            if result.get('tool_calls'):
                tool_results = await self._execute_tools(result['tool_calls'])
                result['tool_results'] = tool_results
                
                # 生成工具结果摘要
                result['tool_summary'] = self._summarize_tool_results(tool_results)
                
                # 检测是否全部工具调用都失败
                failures = [r.get('error') for r in tool_results if r.get('error')]
                if tool_results and len(failures) == len(tool_results):
                    result['error'] = '; '.join(failures)
            
            # 记录步骤
            await self._record_step(task, context, result, duration_ms)
            
            return result
            
        except Exception as e:
            logger.error(f"步骤执行失败: {e}", exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            # 异常时也记录步骤
            try:
                await self._record_step(
                    task, context,
                    {'response': f'Error: {e}', 'is_final': False},
                    duration_ms
                )
            except Exception:
                logger.exception("记录步骤失败")
            return {'error': str(e)}
    
    async def _invoke_llm(self, messages: List) -> Any:
        """调用 LLM"""
        return await asyncio.to_thread(self.llm_with_tools.invoke, messages)
    
    async def _parse_ai_response(self, response) -> Dict[str, Any]:
        """解析 AI 响应"""
        result = {
            'response': '',
            'tool_calls': [],
            'is_final': False
        }
        
        if hasattr(response, 'content') and response.content:
            result['response'] = response.content
        
        # 检查工具调用
        if hasattr(response, 'tool_calls') and response.tool_calls:
            result['tool_calls'] = response.tool_calls
        else:
            # 没有工具调用，说明是最终响应
            result['is_final'] = True
        
        return result
    
    async def _execute_tools(self, tool_calls: List) -> List[Dict]:
        """执行工具调用"""
        results = []
        
        for tool_call in tool_calls:
            tool_name, tool_args = self._extract_tool_call_payload(tool_call)
            
            if not tool_name:
                results.append({
                    'tool_name': '',
                    'input': tool_args,
                    'error': '工具名称缺失'
                })
                continue
            
            # 查找工具
            tool = self._find_tool(tool_name)
            if not tool:
                results.append({
                    'tool_name': tool_name,
                    'error': f'工具 {tool_name} 不存在'
                })
                continue
            
            try:
                # 执行工具（支持同步/异步）
                output = await self._invoke_tool(tool, tool_args)
                results.append({
                    'tool_name': tool_name,
                    'input': tool_args,
                    'output': output
                })
            except Exception as e:
                logger.error(f"工具 {tool_name} 调用失败: {e}", exc_info=True)
                results.append({
                    'tool_name': tool_name,
                    'input': tool_args,
                    'error': str(e)
                })
        
        return results
    
    def _find_tool(self, tool_name: str):
        """查找工具"""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None
    
    def _extract_tool_call_payload(self, tool_call: Any) -> Tuple[str, Dict[str, Any]]:
        """
        兼容不同格式的工具调用负载
        
        支持 dict 和 object 两种格式
        """
        if isinstance(tool_call, dict):
            name = tool_call.get('name') or tool_call.get('tool_name') or tool_call.get('tool')
            args = tool_call.get('args') or tool_call.get('input')
        else:
            name = getattr(tool_call, 'name', None) or getattr(tool_call, 'tool_name', None) or getattr(tool_call, 'tool', None)
            args = getattr(tool_call, 'args', None) or getattr(tool_call, 'input', None)
        
        # 如果 args 是字符串，尝试解析为 JSON
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                pass
        
        return (name or ''), (args or {})
    
    async def _invoke_tool(self, tool, tool_args: Dict[str, Any]) -> Any:
        """
        统一处理同步与异步工具
        """
        # 优先使用异步方法
        if hasattr(tool, 'ainvoke'):
            return await tool.ainvoke(tool_args)
        
        # 同步方法
        invoke_callable = getattr(tool, 'invoke', None)
        if not invoke_callable and callable(tool):
            invoke_callable = tool
        if not invoke_callable:
            raise AttributeError(f'工具 {getattr(tool, "name", str(tool))} 缺少 invoke/ainvoke 实现')
        
        return await asyncio.to_thread(invoke_callable, tool_args)
    
    def _summarize_tool_results(self, tool_results: List[Dict]) -> str:
        """
        生成工具结果摘要
        
        这是关键：不把完整结果放入上下文，只保留摘要
        """
        summaries = []
        
        for result in tool_results:
            tool_name = result.get('tool_name', 'unknown')
            
            if result.get('error'):
                summaries.append(f"{tool_name}: 失败 - {result['error']}")
            else:
                output = result.get('output', '')
                
                # 完整保留所有工具结果，不做截断
                if isinstance(output, str):
                    summary = output
                elif isinstance(output, (dict, list)):
                    summary = json.dumps(output, ensure_ascii=False, indent=2)
                else:
                    summary = str(output)
                
                summaries.append(f"{tool_name}:\n{summary}")
        
        return '\n\n'.join(summaries)
    
    async def _update_blackboard(self, blackboard: AgentBlackboard, step_result: Dict):
        """更新 Blackboard"""
        from asgiref.sync import sync_to_async
        
        # 生成本步骤的摘要
        summary_parts = []
        
        if step_result.get('tool_summary'):
            summary_parts.append(step_result['tool_summary'])
        
        if step_result.get('response') and not step_result.get('is_final'):
            response_content = step_result['response']
            if not isinstance(response_content, str):
                try:
                    response_content = json.dumps(response_content, ensure_ascii=False)
                except (TypeError, ValueError):
                    response_content = str(response_content)
            summary_parts.append(f"AI: {response_content}")
        
        if summary_parts:
            step_summary = ' | '.join(summary_parts)
            
            @sync_to_async
            def update():
                blackboard.add_history(step_summary)
            
            await update()
    
    async def _record_step(
        self,
        task: AgentTask,
        context: Dict,
        result: Dict,
        duration_ms: int
    ):
        """记录步骤"""
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def create_step():
            # 安全提取工具信息
            tool_name = ''
            tool_input = None
            tool_calls = result.get('tool_calls') or []
            if tool_calls:
                tool_name, tool_input = self._extract_tool_call_payload(tool_calls[0])
            
            return AgentStep.objects.create(
                task=task,
                step_number=task.current_step,
                input_context={
                    'goal': context.get('goal', ''),
                    'history_length': len(context.get('history', '').split('\n'))
                },
                ai_response=result.get('response', ''),
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output_summary=result.get('tool_summary', ''),
                is_final=result.get('is_final', False),
                duration_ms=duration_ms
            )
        
        await create_step()


class AgentLoopIntegration:
    """
    Agent Loop 与现有 LangGraph 集成
    
    提供简单的接口，根据请求复杂度决定使用传统方式还是 Agent Loop
    """
    
    @staticmethod
    def should_use_agent_loop(tools: List, message: str) -> bool:
        """
        判断是否应该使用 Agent Loop
        
        规则：
        - 如果有 Playwright 等会产生大量 Token 的工具，使用 Agent Loop
        - 如果消息暗示需要多步操作，使用 Agent Loop
        - 简单对话使用传统方式
        """
        # 检查工具列表
        heavy_tools = ['playwright', 'browser', 'page', 'snapshot']
        for tool in tools:
            tool_name = getattr(tool, 'name', '').lower()
            if any(heavy in tool_name for heavy in heavy_tools):
                return True
        
        # 检查消息内容
        multi_step_keywords = ['测试', '执行', '自动化', '步骤', '流程']
        if any(kw in message for kw in multi_step_keywords):
            return True
        
        return False
    
    @staticmethod
    async def create_orchestrator(llm, tools: List) -> AgentOrchestrator:
        """创建编排器实例"""
        return AgentOrchestrator(llm=llm, tools=tools)
