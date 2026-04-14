
"""Orchestrator流式对话接口"""
import json
import logging
import uuid
import asyncio
import os
from django.views import View
from django.http import StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from asgiref.sync import sync_to_async

from langgraph_integration.models import LLMConfig, ChatSession
from projects.models import Project, ProjectMember
from prompts.models import UserPrompt, PromptType
from .models import OrchestratorTask
from .serializers import OrchestratorTaskSerializer
from .graph import create_orchestrator_graph, OrchestratorState
from .context_compression import CompressionSettings
from langgraph_integration.views import create_llm_instance, create_sse_data
from wharttest_django.checkpointer import get_async_checkpointer

logger = logging.getLogger(__name__)


class OrchestratorTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """只读视图 - 用于查看历史任务记录"""
    permission_classes = [IsAuthenticated]
    queryset = OrchestratorTask.objects.all()
    serializer_class = OrchestratorTaskSerializer
    
    def get_queryset(self):
        """只返回当前用户的任务"""
        return OrchestratorTask.objects.filter(user=self.request.user)


@method_decorator(csrf_exempt, name='dispatch')
class OrchestratorStreamAPIView(View):
    """
    Orchestrator流式对话接口
    
    Brain通过StateGraph调用各个Agent,所有交互以SSE流式返回:
    - Brain的决策过程
    - Requirement Agent的需求分析
    - Knowledge Agent的文档检索
    - TestCase Agent的用例生成
    
    对话历史自动保存到chat_history.sqlite,可通过langgraph的历史接口查询
    """
    
    async def authenticate_request(self, request):
        """手动进行JWT认证（异步版本）"""
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise AuthenticationFailed('Authentication credentials were not provided.')
        
        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()
        
        try:
            validated_token = await sync_to_async(jwt_auth.get_validated_token)(token)
            user = await sync_to_async(jwt_auth.get_user)(validated_token)
            return user
        except Exception as e:
            raise AuthenticationFailed(f'Invalid token: {str(e)}')
    
    def _check_project_permission(self, user, project_id):
        """检查用户是否有访问指定项目的权限"""
        try:
            project = Project.objects.get(id=project_id)
            if user.is_superuser:
                return project
            if ProjectMember.objects.filter(project=project, user=user).exists():
                return project
            return None
        except Project.DoesNotExist:
            return None
    
    async def _create_sse_generator(self, request, user_message_content, session_id, 
                                   project_id, project, prompt_id=None, auth_user_info=None):
        """创建SSE数据生成器,集成StateGraph with checkpointer"""
        try:
            # 1. 获取活跃的LLM配置
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            logger.info(f"OrchestratorStream: Using LLM: {active_config.name}")
        except LLMConfig.DoesNotExist:
            yield create_sse_data({'type': 'error', 'message': 'No active LLM configuration found'})
            return
        except LLMConfig.MultipleObjectsReturned:
            yield create_sse_data({'type': 'error', 'message': 'Multiple active LLM configurations found'})
            return
        
        try:
            # 2. 创建LLM实例
            llm = create_llm_instance(active_config, temperature=0.7)
            logger.info(f"OrchestratorStream: LLM initialized")
            
            # 2.1 创建上下文压缩配置
            compression_settings = CompressionSettings(
                max_context_tokens=active_config.context_limit,
                trigger_ratio=getattr(settings, "ORCHESTRATOR_CONTEXT_TRIGGER_RATIO", 0.6),
                preserve_recent_messages=getattr(settings, "ORCHESTRATOR_PRESERVE_RECENT_MESSAGES", 8),
            )
            logger.info(f"OrchestratorStream: Context compression configured (limit={active_config.context_limit})")
            
            # 2.5 加载MCP工具（与ChatStreamAPIView一致）
            mcp_tools_list = []
            try:
                from mcp_tools.models import RemoteMCPConfig
                from mcp_tools.persistent_client import mcp_session_manager
                
                # 诊断：检查RemoteMCPConfig配置
                total_configs = await sync_to_async(RemoteMCPConfig.objects.count)()
                logger.info(f"OrchestratorStream: 数据库中共有 {total_configs} 个MCP配置")
                
                active_remote_mcp_configs_qs = RemoteMCPConfig.objects.filter(is_active=True)
                active_remote_mcp_configs = await sync_to_async(list)(active_remote_mcp_configs_qs)
                logger.info(f"OrchestratorStream: 激活的MCP配置数量: {len(active_remote_mcp_configs)}")
                
                if active_remote_mcp_configs:
                    client_mcp_config = {}
                    for r_config in active_remote_mcp_configs:
                        config_key = r_config.name or f"remote_config_{r_config.id}"
                        client_mcp_config[config_key] = {
                            "url": r_config.url,
                            "transport": (r_config.transport or "streamable-http").replace('-', '_'),
                        }
                        if r_config.headers and isinstance(r_config.headers, dict) and r_config.headers:
                            client_mcp_config[config_key]["headers"] = r_config.headers.copy()
                        else:
                            client_mcp_config[config_key]["headers"] = {}
                        
                        # 将 auth_user_info 添加到 headers 中
                        if auth_user_info:
                            import json
                            client_mcp_config[config_key]["headers"]["X-Auth-User"] = json.dumps(auth_user_info)
                            logger.info(f"OrchestratorStream: Added X-Auth-User header to MCP config: {config_key}")
                    
                    if client_mcp_config:
                        logger.info(f"OrchestratorStream: 加载MCP配置: {list(client_mcp_config.keys())}")
                        mcp_tools_list = await mcp_session_manager.get_tools_for_config(
                            client_mcp_config,
                            user_id=str(request.user.id),
                            project_id=str(project_id),
                            session_id=session_id
                        )
                        logger.info(f"✅ OrchestratorStream: 成功加载 {len(mcp_tools_list)} 个MCP工具")
                    else:
                        logger.warning("⚠️ OrchestratorStream: 无可用的MCP配置 - 所有agent将无法使用MCP工具")
                else:
                    logger.warning(f"⚠️ OrchestratorStream: 未找到激活的RemoteMCPConfig（共{len(active_remote_mcp_configs)}个配置，但无激活状态）")
            except Exception as e:
                logger.error(f"❌ OrchestratorStream: 加载MCP工具失败: {e}", exc_info=True)
                logger.error("   建议检查：1) RemoteMCPConfig配置 2) MCP服务连接 3) mcp_session_manager状态")
                # mcp_tools_list保持为空，继续执行
            
            # 3. 获取Brain的系统提示词
            brain_prompt = None
            try:
                if prompt_id:
                    user_prompt = await sync_to_async(UserPrompt.objects.get)(
                        id=prompt_id,
                        user=request.user,
                        prompt_type=PromptType.BRAIN_ORCHESTRATOR,
                        is_active=True
                    )
                    brain_prompt = user_prompt.content
                    logger.info(f"OrchestratorStream: Using user-specified Brain prompt")
                else:
                    user_prompt = await sync_to_async(
                        lambda: UserPrompt.objects.filter(
                            user=request.user,
                            prompt_type=PromptType.BRAIN_ORCHESTRATOR,
                            is_active=True
                        ).first()
                    )()
                    if user_prompt:
                        brain_prompt = user_prompt.content
                        logger.info(f"OrchestratorStream: Using user's Brain prompt")
            except Exception as e:
                logger.warning(f"OrchestratorStream: Failed to get user Brain prompt: {e}")
            
            if not brain_prompt:
                from .prompts import BRAIN_AGENT_PROMPT
                brain_prompt = BRAIN_AGENT_PROMPT
                logger.info(f"OrchestratorStream: Using default Brain prompt")
            
            # 4. 创建checkpointer和StateGraph（传递MCP工具和project_id）
            async with get_async_checkpointer() as checkpointer:
                graph = create_orchestrator_graph(
                    llm,
                    checkpointer,
                    user=request.user,
                    mcp_tools=mcp_tools_list,
                    project_id=project_id,
                    compression_settings=compression_settings,
                    model_name=active_config.name
                )
                logger.info(f"OrchestratorStream: StateGraph created with {len(mcp_tools_list)} MCP tools, project_id={project_id}, user={request.user.username}")
                if len(mcp_tools_list) == 0:
                    logger.warning("⚠️ 警告：当前没有可用的MCP工具！所有agent将只能使用知识库工具。")
                    logger.warning("   请检查RemoteMCPConfig表中是否有is_active=True的记录。")
                
                # 5. 构建thread_id（包含项目ID实现项目隔离）
                thread_id_parts = [str(request.user.id), str(project_id)]
                if session_id:
                    thread_id_parts.append(str(session_id))
                thread_id = "_".join(thread_id_parts)
                logger.info(f"OrchestratorStream: Using thread_id: {thread_id}")
                
                # 6. 构建输入状态（只包含新消息，checkpointer会自动合并历史）
                from langchain_core.messages import HumanMessage
                
                # 关键：只传入新消息和必要的初始字段
                # checkpointer会自动加载历史messages并追加新消息
                input_state: OrchestratorState = {
                    "messages": [HumanMessage(content=user_message_content)],
                    "requirement": user_message_content,
                    "project_id": project_id,
                    "requirement_analysis": None,
                    "knowledge_docs": [],
                    "testcases": [],
                    "next_agent": "",
                    "instruction": "",
                    "reason": "",
                    "current_step": 0,
                    "max_steps": 10,
                    "context_summary": None,
                    "summarized_message_count": 0,
                    "context_token_count": 0
                }
                
                # 7. 发送开始信号
                yield create_sse_data({
                    'type': 'start',
                    'session_id': session_id,
                    'project_id': project_id,
                    'project_name': project.name,
                    'requirement': user_message_content,
                    'context_limit': compression_settings.max_context_tokens if compression_settings else 128000
                })
                
                # 8. 流式执行StateGraph
                step_count = 0
                invoke_config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 1000  # 支持约500次工具调用
                }
                
                # 🔍 DEBUG: 检查checkpointer中的历史状态
                try:
                    checkpoint_tuple = await checkpointer.aget(invoke_config)
                    if checkpoint_tuple:
                        # checkpoint_tuple是一个tuple: (checkpoint_dict, metadata)
                        checkpoint_dict = checkpoint_tuple[0] if isinstance(checkpoint_tuple, tuple) else checkpoint_tuple
                        if checkpoint_dict and isinstance(checkpoint_dict, dict):
                            channel_values = checkpoint_dict.get("channel_values", {})
                            history_messages = channel_values.get("messages", [])
                            logger.info(f"🔍 DEBUG: Found {len(history_messages)} history messages in checkpointer for thread_id={thread_id}")
                        else:
                            logger.info(f"🔍 DEBUG: Checkpoint structure: {type(checkpoint_tuple)}")
                    else:
                        logger.info(f"🔍 DEBUG: No checkpoint found for thread_id={thread_id}, starting new conversation")
                except Exception as e:
                    logger.warning(f"🔍 DEBUG: Failed to check history: {e}")
                
                # 使用astream_events进行流式处理,捕获工具调用等所有事件(v2版本支持嵌套Agent)
                final_state = None
                # 6. 准备流式事件捕获
                current_node_name = None  # 跟踪当前执行的节点
                
                try:
                    # checkpointer会自动：
                    # 1. 加载thread_id对应的历史状态
                    # 2. 将input_state中的messages追加到历史messages
                    # 3. 更新其他字段（覆盖方式）
                    async for event in graph.astream_events(
                        input_state,
                        config=invoke_config,
                        version="v2"  # v2版本支持捕获嵌套Runnable的事件
                    ):
                        event_type = event.get("event")
                        event_name = event.get("name", "")
                        event_data = event.get("data", {})
                        
                        # 🔍 DEBUG: 打印所有事件类型以便诊断（可选）
                        # if "tool" in event_name.lower() or "tool" in event_type:
                        #     logger.info(f"🔍 Event: {event_type}, Name: {event_name}, Data keys: {event_data.keys() if isinstance(event_data, dict) else type(event_data)}")
                        
                        # 1. LLM令牌流式传输 (on_chat_model_stream) - 逐字/逐词流式输出
                        if event_type == "on_chat_model_stream":
                            chunk = event_data.get("chunk", {})
                            metadata = event_data.get("metadata", {})
                            content = ""
                            if hasattr(chunk, 'content'):
                                content = chunk.content  # 提取content属性
                            elif isinstance(chunk, dict) and 'content' in chunk:
                                content = chunk['content']
                            
                            # 🔧 过滤Brain的原始JSON输出（只显示格式化决策）
                            # current_node_name在on_chain_start时设置为顶层节点名称（如"brain_agent"）
                            if content and not (current_node_name and "brain" in current_node_name.lower()):
                                # 不是Brain节点，正常发送（chat/requirement/testcase等agent的输出）
                                # 提取agent名称用于显示
                                agent_name = current_node_name.replace('_agent', '').title() if current_node_name else 'Unknown'
                                
                                yield create_sse_data({
                                    'type': 'message', 
                                    'data': {
                                        'content': content,
                                        'additional_kwargs': {
                                            'agent': agent_name.lower(),
                                            'agent_type': 'orchestrator_agent',
                                            'node_name': current_node_name
                                        },
                                        'response_metadata': metadata,
                                        'id': metadata.get('run_id', 'unknown')
                                    }
                                })
                                
                                # 🔧 日志：显示流式输出的详细信息
                                if len(content) > 0:
                                    logger.debug(f"[{agent_name} Stream] Token: '{content}' (length={len(content)})")
                            # Brain节点的on_chat_model_stream令牌被跳过
                            # 格式化决策消息在on_chain_end事件中发送
                        
                        # 2. 工具调用开始 (on_tool_start)
                        elif event_type == "on_tool_start":
                            tool_name = event_name
                            tool_input = event_data.get("input", {})
                            logger.info(f"OrchestratorStream: Tool {tool_name} started with input: {tool_input}")
                            
                            # 优化工具参数显示
                            if not tool_input or tool_input == {}:
                                tool_input_display = "无需参数"
                                tool_input_detail = "该工具不需要输入参数"
                            else:
                                tool_input_display = tool_input
                                # 格式化参数详情
                                param_details = [f"{k}: {v}" for k, v in tool_input.items()]
                                tool_input_detail = ", ".join(param_details)
                            
                            yield create_sse_data({
                                'type': 'tool_start',
                                'tool_name': tool_name,
                                'tool_input': tool_input_display,
                                'tool_input_detail': tool_input_detail
                            })
                        
                        # 3. 工具调用结束 (on_tool_end)
                        elif event_type == "on_tool_end":
                            tool_name = event_name
                            tool_output = event_data.get("output")
                            
                            # 提取工具输出的实际内容
                            if hasattr(tool_output, 'content'):
                                actual_content = tool_output.content
                            else:
                                actual_content = str(tool_output)
                            
                            logger.info(f"OrchestratorStream: Tool {tool_name} completed with output: {str(actual_content)[:200]}")
                            
                            # 完整发送工具输出,前端可以自行截断显示
                            output_length = len(actual_content)
                            
                            yield create_sse_data({
                                'type': 'tool_end',
                                'tool_name': tool_name,
                                'tool_output': actual_content,  # 完整输出
                                'output_length': output_length
                            })
                        
                        # 3.5. 工具调用出错 (on_tool_error)
                        elif event_type == "on_tool_error":
                            tool_name = event_name
                            error_info = event_data.get("error") or str(event_data)
                            logger.error(f"OrchestratorStream: Tool {tool_name} failed with error: {error_info}")
                            yield create_sse_data({
                                'type': 'tool_error',
                                'tool_name': tool_name,
                                'error': str(error_info)
                            })
                        
                        # 4. 节点开始执行 (on_chain_start)
                        # 🔧 修复：只在顶层节点（_agent结尾）时设置current_node_name，忽略内部Runnable
                        elif event_type == "on_chain_start" and event_name.endswith("_agent"):
                            current_node_name = event_name
                            logger.info(f"OrchestratorStream: Node {current_node_name} started")
                            
                            # 🔧 新增：节点开始时发送分隔标记，让前端知道新的agent开始了
                            if "brain" not in event_name.lower():
                                yield create_sse_data({
                                    'type': 'agent_start',
                                    'agent': event_name.replace('_agent', '').title()
                                })
                        
                        # 5. 节点执行结束 (on_chain_end) - 处理各Agent的输出
                        elif event_type == "on_chain_end" and "agent" in event_name:
                            node_name = event_name
                            node_output = event_data.get("output", {})
                            logger.info(f"OrchestratorStream: Node {node_name} completed")
                            
                            # 🔧 修复：节点结束时清空current_node_name，避免影响下一个节点的流式输出
                            if current_node_name == node_name:
                                current_node_name = None
                            
                            if "brain" in node_name and isinstance(node_output, dict):
                                # Brain节点完成
                                next_agent = node_output.get("next_agent", "")
                                instruction = node_output.get("instruction", "")
                                reason = node_output.get("reason", "")
                                current_step = node_output.get("current_step", 0)
                                
                                # 获取Token使用信息
                                context_token_count = node_output.get("context_token_count", 0)
                                context_limit = compression_settings.max_context_tokens if compression_settings else 128000
                                logger.info(f"[Context Update] Sending token info: {context_token_count}/{context_limit}")
                                
                                # 获取状态信息以匹配历史格式
                                executed_agents = node_output.get("executed_agents", [])
                                has_requirement_analysis = bool(node_output.get("requirement_analysis"))
                                has_testcases = bool(node_output.get("testcases"))
                                max_steps = node_output.get("max_steps", 10)
                                
                                # 发送上下文Token更新事件
                                yield create_sse_data({
                                    'type': 'context_update',
                                    'context_token_count': context_token_count,
                                    'context_limit': context_limit
                                })
                                
                                # 🔧 关键：Brain可能返回多条消息（decision + final_response）
                                messages_from_brain = node_output.get("messages", [])
                                
                                # 遍历所有消息并发送
                                for msg in messages_from_brain:
                                    from langchain_core.messages import AIMessage
                                    if isinstance(msg, AIMessage):
                                        agent_type = msg.additional_kwargs.get("agent_type", "")
                                        
                                        if agent_type == "orchestrator_brain_decision":
                                            # Brain决策消息
                                            # 先发送格式化文本消息（与历史存储一致）
                                            yield create_sse_data({
                                                'type': 'message',
                                                'data': {
                                                    'content': msg.content,
                                                    'additional_kwargs': msg.additional_kwargs,
                                                    'response_metadata': {},
                                                    'id': 'brain_decision'
                                                }
                                            })
                                            
                                            # 再发送结构化决策数据（供前端特殊处理）
                                            yield create_sse_data({
                                                'type': 'brain_decision',
                                                'agent': 'Brain',
                                                'next_agent': next_agent,
                                                'instruction': instruction,
                                                'reason': reason,
                                                'step': current_step
                                            })
                                        
                                        elif agent_type == "orchestrator_final_response":
                                            # 最终用户回复消息
                                            logger.info(f"OrchestratorStream: Sending final response to user")
                                            yield create_sse_data({
                                                'type': 'message',
                                                'data': {
                                                    'content': msg.content,
                                                    'additional_kwargs': msg.additional_kwargs,
                                                    'response_metadata': {},
                                                    'id': 'final_response'
                                                }
                                            })
                                
                                if next_agent == "END":
                                    logger.info(f"OrchestratorStream: Brain decided to END")
                            
                            elif "chat" in node_name and isinstance(node_output, dict):
                                # Chat Agent完成
                                yield create_sse_data({
                                    'type': 'chat_response',
                                    'agent': 'Chat'
                                })
                            
                            elif "requirement" in node_name and isinstance(node_output, dict):
                                # Requirement Agent完成
                                analysis = node_output.get("requirement_analysis", {})
                                yield create_sse_data({
                                    'type': 'requirement_analysis',
                                    'agent': 'Requirement',
                                    'analysis': analysis
                                })
                            
                            elif "testcase" in node_name and isinstance(node_output, dict):
                                # TestCase Agent完成
                                testcases = node_output.get("testcases", [])
                                yield create_sse_data({
                                    'type': 'testcase_generation',
                                    'agent': 'TestCase',
                                    'testcase_count': len(testcases),
                                    'testcases': testcases
                                })
                            
                            # 保存最终状态
                            if final_state is None:
                                final_state = {}
                            # 🔧 修复：检查node_output是否为None或dict
                            if node_output and isinstance(node_output, dict):
                                final_state.update(node_output)
                        
                        # 添加小延迟以确保流式传输效果
                        await asyncio.sleep(0.01)
                
                except Exception as e:
                    logger.error(f"OrchestratorStream: Error during streaming: {e}", exc_info=True)
                    yield create_sse_data({'type': 'error', 'message': f'Streaming error: {str(e)}'})
                
                # 9. 构建最终结果摘要
                final_values = final_state or {}
                
                # 10. 发送最终摘要
                if final_values:
                    yield create_sse_data({
                        'type': 'final_summary',
                        'requirement_analysis': final_values.get('requirement_analysis'),
                        'knowledge_doc_count': len(final_values.get('knowledge_docs', [])),
                        'testcase_count': len(final_values.get('testcases', [])),
                        'total_steps': final_values.get('current_step', 0)
                    })
                
                # 11. 保存任务记录到数据库
                try:
                    task_data = {
                        'user': request.user,
                        'project_id': project_id,
                        'requirement': user_message_content,
                        'status': 'completed',
                        'requirement_analysis': final_values.get('requirement_analysis'),
                        'knowledge_docs': final_values.get('knowledge_docs', []),
                        'testcases': final_values.get('testcases', []),
                    }
                    
                    try:
                        chat_session = await sync_to_async(ChatSession.objects.get)(
                            session_id=session_id,
                            user=request.user
                        )
                        task_data['chat_session'] = chat_session
                    except ChatSession.DoesNotExist:
                        pass
                    
                    await sync_to_async(OrchestratorTask.objects.create)(**task_data)
                    logger.info(f"OrchestratorStream: Task record saved")
                except Exception as e:
                    logger.error(f"OrchestratorStream: Failed to save task record: {e}")
                
                # 12. 发送完成信号
                yield create_sse_data({'type': 'complete'})
                yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"OrchestratorStream: Error in stream generator: {e}", exc_info=True)
            yield create_sse_data({'type': 'error', 'message': f'Stream error: {str(e)}'})
    
    async def post(self, request, *args, **kwargs):
        """处理流式编排请求"""
        try:
            user = await self.authenticate_request(request)
            request.user = user
            logger.info(f"OrchestratorStream: Request from user {user.id}")
        except AuthenticationFailed as e:
            error_data = create_sse_data({
                'type': 'error',
                'message': str(e),
                'code': 401
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=401
            )
        
        try:
            body_data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            error_data = create_sse_data({
                'type': 'error',
                'message': f'Invalid JSON data: {str(e)}',
                'code': 400
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=400
            )
        
        user_message_content = body_data.get('message')
        session_id = body_data.get('session_id')
        project_id = body_data.get('project_id')
        prompt_id = body_data.get('prompt_id')
        
        # 从 X-Auth-User 头中提取用户信息
        auth_user_header = request.META.get('HTTP_X_AUTH_USER')
        auth_user_info = None
        if auth_user_header:
            try:
                import json
                auth_user_info = json.loads(auth_user_header)
                logger.info(f"OrchestratorStream: Received auth-user info: id={auth_user_info.get('id')}, username={auth_user_info.get('username')}")
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"OrchestratorStream: Failed to parse X-Auth-User header: {e}")
        
        if not project_id:
            error_data = create_sse_data({
                'type': 'error',
                'message': 'project_id is required',
                'code': 400
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=400
            )
        
        if not user_message_content:
            error_data = create_sse_data({
                'type': 'error',
                'message': 'message is required',
                'code': 400
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=400
            )
        
        project = await sync_to_async(self._check_project_permission)(request.user, project_id)
        if not project:
            error_data = create_sse_data({
                'type': 'error',
                'message': "You don't have permission to access this project",
                'code': 403
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=403
            )
        
        if not session_id:
            session_id = uuid.uuid4().hex
            logger.info(f"OrchestratorStream: Generated session_id: {session_id}")
        
        async def async_generator():
            async for chunk in self._create_sse_generator(
                request, user_message_content, session_id,
                project_id, project, prompt_id, auth_user_info
            ):
                yield chunk
        
        response = StreamingHttpResponse(
            async_generator(),
            content_type='text/event-stream; charset=utf-8'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Access-Control-Allow-Origin'] = '*'
        
        return response
