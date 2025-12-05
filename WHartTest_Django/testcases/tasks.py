"""
测试用例执行的Celery异步任务
"""
import logging
import asyncio
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import datetime
from typing import Dict, Any
from django.conf import settings
import os
import json
import uuid
import httpx
from rest_framework_simplejwt.tokens import RefreshToken

from .models import TestExecution, TestSuite, TestCaseResult, TestCase
from prompts.models import UserPrompt, PromptType
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='testcases.execute_test_suite')
def execute_test_suite(self, execution_id):
    """
    执行测试套件的异步任务
    
    Args:
        execution_id: TestExecution实例的ID
        
    Returns:
        dict: 执行结果摘要
    """
    try:
        # 获取执行记录
        execution = TestExecution.objects.select_related('suite').get(id=execution_id)
        suite = execution.suite
        
        logger.info(f"开始执行测试套件: {suite.name} (ID: {suite.id})")
        
        # 更新执行状态为运行中
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.celery_task_id = self.request.id
        execution.save(update_fields=['status', 'started_at', 'celery_task_id', 'updated_at'])
        
        # 获取套件中的所有测试用例
        testcases = suite.testcases.all().order_by('level', 'id')  # 按优先级排序
        execution.total_count = testcases.count()
        execution.save(update_fields=['total_count', 'updated_at'])
        
        # 为每个测试用例创建结果记录
        results = []
        for testcase in testcases:
            result = TestCaseResult.objects.create(
                execution=execution,
                testcase=testcase,
                status='pending'
            )
            results.append(result)
        
        # 获取并发配置
        max_concurrent = suite.max_concurrent_tasks
        logger.info(f"并发配置: {max_concurrent} 个测试用例同时执行")
        
        # 使用asyncio执行并发测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _execute_testcases_concurrently(execution, results, max_concurrent)
            )
        finally:
            loop.close()
        
        # 更新执行记录为已完成
        execution.refresh_from_db()
        execution.status = 'completed' if execution.status != 'cancelled' else 'cancelled'
        execution.completed_at = timezone.now()
        execution.save(update_fields=['status', 'completed_at', 'updated_at'])
        
        logger.info(f"测试套件执行完成: {suite.name}, "
                   f"通过: {execution.passed_count}, "
                   f"失败: {execution.failed_count}, "
                   f"错误: {execution.error_count}, "
                   f"跳过: {execution.skipped_count}")
        
        return {
            'execution_id': execution.id,
            'suite_name': suite.name,
            'status': execution.status,
            'total': execution.total_count,
            'passed': execution.passed_count,
            'failed': execution.failed_count,
            'skipped': execution.skipped_count,
            'error': execution.error_count,
            'pass_rate': execution.pass_rate,
            'duration': execution.duration
        }
        
    except TestExecution.DoesNotExist:
        error_msg = f"测试执行记录不存在: {execution_id}"
        logger.error(error_msg)
        return {'error': error_msg}
        
    except Exception as e:
        error_msg = f"执行测试套件时发生错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 尝试更新执行状态为失败
        try:
            execution = TestExecution.objects.get(id=execution_id)
            execution.status = 'failed'
            execution.completed_at = timezone.now()
            execution.save(update_fields=['status', 'completed_at', 'updated_at'])
        except:
            pass
            
        return {'error': error_msg}


def execute_single_testcase(result: TestCaseResult):
    """
    执行单个测试用例 - 通过对话API驱动测试执行
    
    Args:
        result: TestCaseResult实例
    """
    logger.info(f"开始执行测试用例: {result.testcase.name} (ID: {result.testcase.id})")
    
    # 更新状态为执行中
    result.status = 'running'
    result.started_at = timezone.now()
    result.save(update_fields=['status', 'started_at', 'updated_at'])
    
    try:
        # 在新的事件循环中运行异步执行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_execute_testcase_via_chat_api(result))
        finally:
            loop.close()
        
        logger.info(f"测试用例执行成功: {result.testcase.name}")
        
    except Exception as e:
        error_msg = f"执行测试用例失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        result.status = 'error'
        result.error_message = error_msg
        result.completed_at = timezone.now()
        
        if result.started_at and result.completed_at:
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
            
        result.save()
        raise


async def _execute_testcases_concurrently(execution, results, max_concurrent):
    """
    并发执行测试用例
    
    Args:
        execution: TestExecution实例
        results: TestCaseResult列表
        max_concurrent: 最大并发数
    """
    import asyncio
    
    # 使用信号量控制并发数
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_with_semaphore(result):
        """带信号量控制的执行函数"""
        async with semaphore:
            # 检查是否已取消
            current_execution = await sync_to_async(TestExecution.objects.get)(id=execution.id)
            if current_execution.status == 'cancelled':
                logger.info(f"测试执行已取消，跳过用例: {result.testcase.name}")
                return
            
            try:
                # 更新状态为执行中
                result.status = 'running'
                result.started_at = timezone.now()
                await sync_to_async(result.save)(update_fields=['status', 'started_at', 'updated_at'])
                
                # 直接调用异步执行函数（避免嵌套事件循环）
                await _execute_testcase_via_chat_api(result)
                
                logger.info(f"测试用例执行成功: {result.testcase.name}")
                
                # 刷新result状态
                await sync_to_async(result.refresh_from_db)()
                
                # 更新统计（使用原子操作避免竞态）
                await sync_to_async(_update_execution_counts)(execution, result.status)
                
            except Exception as e:
                error_msg = f"并发执行测试用例失败: {str(e)}"
                logger.error(f"{error_msg} - {result.testcase.name}", exc_info=True)
                
                # 更新result状态为错误
                result.status = 'error'
                result.error_message = error_msg
                result.completed_at = timezone.now()
                
                if result.started_at and result.completed_at:
                    result.execution_time = (result.completed_at - result.started_at).total_seconds()
                
                await sync_to_async(result.save)()
                
                # 更新错误计数
                await sync_to_async(_update_execution_counts)(execution, 'error')
    
    # 创建所有任务
    tasks = [execute_with_semaphore(result) for result in results]
    
    # 并发执行所有任务
    await asyncio.gather(*tasks, return_exceptions=True)


def _update_execution_counts(execution, status):
    """
    原子更新执行统计
    使用select_for_update避免并发写入冲突
    """
    with transaction.atomic():
        # 锁定当前执行记录
        exec_obj = TestExecution.objects.select_for_update().get(id=execution.id)
        
        if status == 'pass':
            exec_obj.passed_count += 1
        elif status == 'fail':
            exec_obj.failed_count += 1
        elif status == 'skip':
            exec_obj.skipped_count += 1
        elif status == 'error':
            exec_obj.error_count += 1
        
        exec_obj.save(update_fields=[
            'passed_count', 'failed_count', 'skipped_count',
            'error_count', 'updated_at'
        ])


@sync_to_async
def _get_testcase_steps(testcase):
    """获取测试用例步骤"""
    return list(testcase.steps.all().order_by('step_number'))

@sync_to_async
def _get_test_execution_prompt(executor):
    """获取测试用例执行提示词"""
    return UserPrompt.get_user_prompt_by_type(executor, PromptType.TEST_CASE_EXECUTION)

@sync_to_async
def _save_result(result: TestCaseResult):
    """异步安全地保存测试结果"""
    result.save()

async def _execute_testcase_via_chat_api(result: TestCaseResult):
    """通过 Agent Loop SSE API 执行测试用例"""
    # 使用thread_sensitive=False避免死锁
    execution = await sync_to_async(lambda: result.execution, thread_sensitive=False)()
    testcase = await sync_to_async(lambda: result.testcase, thread_sensitive=False)()
    executor = await sync_to_async(lambda: execution.executor, thread_sensitive=False)()
    project = await sync_to_async(lambda: testcase.project, thread_sensitive=False)()
    
    if not executor or not project:
        raise Exception("无法获取执行人或项目信息")
    
    execution_log = []
    screenshots = []
    
    try:
        # 1. 获取测试用例执行提示词
        prompt = await _get_test_execution_prompt(executor)
        if not prompt:
            raise Exception("未找到测试用例执行提示词，请先初始化系统提示词")
        
        logger.info(f"使用测试执行提示词: {prompt.name}")
        execution_log.append(f"✓ 加载测试执行提示词: {prompt.name}")
        
        # 2. 获取测试步骤
        steps = await _get_testcase_steps(testcase)
        if not steps:
            raise Exception("测试用例没有定义执行步骤")
        
        # 3. 格式化测试步骤信息
        steps_text = ""
        for step in steps:
            steps_text += f"{step.step_number}. {step.description}\n   预期结果: {step.expected_result}\n"
        
        # 4. 格式化提示词，填充测试用例信息
        from string import Template
        prompt_template = Template(prompt.content)
        formatted_prompt = prompt_template.safe_substitute(
            project_id=project.id,
            testcase_id=testcase.id,
            testcase_name=testcase.name,
            precondition=testcase.precondition or "无",
            steps=steps_text.strip()
        )
        
        logger.info(f"格式化后的提示词长度: {len(formatted_prompt)} 字符")
        execution_log.append(f"✓ 准备执行 {len(steps)} 个测试步骤")
        
        # 5. 构造 Agent Loop API 请求
        api_url = f"{settings.BASE_URL}/api/orchestrator/agent-loop/" if hasattr(settings, 'BASE_URL') else "http://localhost:8000/api/orchestrator/agent-loop/"
        
        # 生成唯一的会话ID
        session_id = f"test_exec_{execution.id}_{testcase.id}_{result.id}_{uuid.uuid4().hex[:8]}"
        
        request_data = {
            "message": formatted_prompt,
            "session_id": session_id,
            "project_id": str(project.id),
            "prompt_id": str(prompt.id),
            "use_knowledge_base": False
        }
        
        logger.info(f"调用 Agent Loop API: {api_url}")
        logger.info(f"会话ID: {session_id}")
        execution_log.append(f"✓ 开始与AI测试引擎通信...")
        
        # 6. 生成认证令牌并调用 Agent Loop SSE API
        def generate_token():
            refresh = RefreshToken.for_user(executor)
            return str(refresh.access_token)
        
        access_token = await sync_to_async(generate_token)()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        }
        
        # 收集 SSE 流式响应
        final_response = ""
        step_count = 0
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                'POST',
                api_url,
                json=request_data,
                headers=headers
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith('data: '):
                        continue
                    
                    try:
                        data_str = line[6:]  # 去掉 'data: ' 前缀
                        if data_str == '[DONE]':
                            break
                        
                        data = json.loads(data_str)
                        event_type = data.get('type', '')
                        
                        if event_type == 'step_start':
                            step_count += 1
                            execution_log.append(f"\n🔄 AI执行步骤 {step_count}")
                        
                        elif event_type == 'content':
                            content = data.get('content', '')
                            if content:
                                final_response += content
                        
                        elif event_type == 'message':
                            # Agent Loop 的 message 事件包含 AI 的响应（思考过程）
                            msg_data = data.get('data', '')
                            if msg_data:
                                final_response += msg_data
                                # 显示 AI 的说明（前150字符）
                                short_msg = msg_data[:150].replace('\n', ' ').strip()
                                if len(msg_data) > 150:
                                    short_msg += '...'
                                if short_msg:
                                    execution_log.append(f"   💬 {short_msg}")
                        
                        elif event_type == 'tool_call':
                            tool_name = data.get('name', '')
                            execution_log.append(f"   🔧 {tool_name}")
                        
                        elif event_type == 'tool_result':
                            pass  # 不显示工具结果
                        
                        elif event_type == 'step_end' or event_type == 'step_complete':
                            pass  # 步骤结束信号，不需要输出
                        
                        elif event_type == 'final':
                            final_response = data.get('content', final_response)
                        
                        elif event_type == 'error':
                            error_msg = data.get('message', '未知错误')
                            execution_log.append(f"   ❌ 错误: {error_msg}")
                            raise Exception(error_msg)
                    
                    except json.JSONDecodeError:
                        continue
        
        logger.info(f"Agent Loop 执行完成，共 {step_count} 个步骤")
        
        # 7. 尝试从最终响应中提取JSON格式的测试结果
        test_result_json = None
        try:
            if '```json' in final_response:
                json_start = final_response.find('```json') + 7
                json_end = final_response.find('```', json_start)
                if json_end > json_start:
                    json_str = final_response[json_start:json_end].strip()
                    test_result_json = json.loads(json_str)
            elif '```' in final_response:
                json_start = final_response.find('```') + 3
                json_end = final_response.find('```', json_start)
                if json_end > json_start:
                    json_str = final_response[json_start:json_end].strip()
                    test_result_json = json.loads(json_str)
            else:
                test_result_json = json.loads(final_response)
        except json.JSONDecodeError as e:
            logger.warning(f"无法从AI响应中提取JSON: {e}")
            execution_log.append(f"⚠ AI响应格式不符合预期，分析响应内容")
        
        # 8. 根据解析结果更新TestCaseResult
        if test_result_json:
            final_status = test_result_json.get('status', 'fail')
            summary = test_result_json.get('summary', '')
            step_results = test_result_json.get('steps', [])
            
            result.status = 'pass' if final_status == 'pass' else 'fail'
            
            execution_log.append(f"\n{'='*50}")
            execution_log.append(f"测试结果: {final_status.upper()}")
            execution_log.append(f"总结: {summary}")
            execution_log.append(f"{'='*50}\n")
            
            for step_result in step_results:
                step_num = step_result.get('step_number', 0)
                step_desc = step_result.get('description', '')
                step_status = step_result.get('status', 'unknown')
                step_error = step_result.get('error')
                
                status_icon = "✓" if step_status == 'pass' else "✗"
                execution_log.append(f"[步骤 {step_num}] {status_icon} {step_desc}")
                
                if step_error:
                    execution_log.append(f"  错误: {step_error}")
        else:
            # 没有结构化JSON，分析响应内容判断结果
            has_error = 'error' in final_response.lower() or 'fail' in final_response.lower() or '失败' in final_response
            result.status = 'fail' if has_error else 'pass'
            
            execution_log.append(f"\n{'='*50}")
            execution_log.append(f"测试完成 - 状态: {'失败' if has_error else '通过'}")
            execution_log.append(f"{'='*50}\n")
        
        # 获取测试用例的截图
        try:
            testcase_screenshots = await sync_to_async(
                lambda: list(testcase.screenshots.filter(
                    step_number__isnull=False
                ).order_by('step_number').values_list('screenshot', flat=True))
            )()
            
            if testcase_screenshots:
                screenshots = [f"{settings.MEDIA_URL}{url}" if not url.startswith('http') else url
                             for url in testcase_screenshots]
                logger.info(f"从测试用例获取到 {len(screenshots)} 个截图URL")
        except Exception as e:
            logger.warning(f"获取测试用例截图失败: {e}")
        
        if result.status == 'running':
            result.status = 'pass'
            execution_log.append("\n✓ 所有步骤执行完成")
        
        # 清理MCP会话
        try:
            from mcp_tools.persistent_client import mcp_session_manager
            await mcp_session_manager.cleanup_user_session(
                user_id=str(executor.id),
                project_id=str(project.id),
                session_id=session_id
            )
            logger.info(f"已清理MCP会话: {session_id}")
            execution_log.append(f"✓ 已清理浏览器会话资源")
        except Exception as e:
            logger.warning(f"清理MCP会话失败: {e}")
        
    except httpx.HTTPError as e:
        error_msg = f"调用 Agent Loop API 失败: {str(e)}"
        execution_log.append(f"\n✗ {error_msg}")
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"执行过程异常: {str(e)}"
        execution_log.append(f"\n✗ {error_msg}")
        logger.error(error_msg, exc_info=True)
        raise
    
    finally:
        result.execution_log = "\n".join(execution_log)
        result.screenshots = screenshots
        result.completed_at = timezone.now()
        
        if result.started_at and result.completed_at:
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
        
        await _save_result(result)


@shared_task(name='testcases.cancel_test_execution')
def cancel_test_execution(execution_id):
    """
    取消测试执行
    
    Args:
        execution_id: TestExecution实例的ID
    """
    try:
        execution = TestExecution.objects.get(id=execution_id)
        
        if execution.status in ['pending', 'running']:
            execution.status = 'cancelled'
            execution.completed_at = timezone.now()
            execution.save(update_fields=['status', 'completed_at', 'updated_at'])
            
            # 取消所有pending状态的测试用例结果
            execution.results.filter(status='pending').update(
                status='skip',
                completed_at=timezone.now()
            )
            
            logger.info(f"测试执行已取消: {execution_id}")
            return {'success': True, 'message': '测试执行已取消'}
        else:
            return {'success': False, 'message': f'无法取消状态为 {execution.status} 的执行'}
            
    except TestExecution.DoesNotExist:
        return {'success': False, 'message': '测试执行记录不存在'}
    except Exception as e:
        logger.error(f"取消测试执行失败: {str(e)}", exc_info=True)
        return {'success': False, 'message': str(e)}