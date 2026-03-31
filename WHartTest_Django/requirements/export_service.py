"""
评审报告导出服务
支持导出为Excel、Word、PDF格式
"""
import io
import os
from datetime import datetime
from typing import Optional
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .models import ReviewReport, ReviewIssue, ModuleReviewResult


class ReportExportService:
    """评审报告导出服务"""
    
    # 中文字体路径（需要确保系统中安装了中文字体）
    # 对于Docker环境，通常在 /usr/share/fonts/ 下
    CHINESE_FONT_PATHS = [
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',  # 文泉驿
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',  # Noto Sans CJK
        'C:\\Windows\\Fonts\\simhei.ttf',  # Windows黑体
        'C:\\Windows\\Fonts\\msyh.ttc',  # Windows微软雅黑
        '/System/Library/Fonts/PingFang.ttc',  # macOS
    ]
    
    @classmethod
    def find_chinese_font(cls):
        """查找可用的中文字体"""
        for font_path in cls.CHINESE_FONT_PATHS:
            if os.path.exists(font_path):
                return font_path
        return None
    
    @classmethod
    def export_to_excel(cls, report: ReviewReport) -> HttpResponse:
        """导出报告为Excel格式"""
        workbook = Workbook()
        
        # 删除默认sheet
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        
        # 创建概览sheet
        cls._create_overview_sheet(workbook, report)
        
        # 创建问题列表sheet
        cls._create_issues_sheet(workbook, report)
        
        # 创建模块评审结果sheet
        cls._create_modules_sheet(workbook, report)
        
        # 创建专项分析sheet
        cls._create_specialized_sheet(workbook, report)
        
        # 保存到字节流
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        
        # 创建响应
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'评审报告_{report.document.title}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    @classmethod
    def export_to_word(cls, report: ReviewReport) -> HttpResponse:
        """导出报告为Word格式"""
        document = Document()
        
        # 标题
        title = document.add_heading(f'{report.document.title} - 评审报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 基本信息
        document.add_heading('一、评审基本信息', level=1)
        info_table = document.add_table(rows=6, cols=2)
        info_table.style = 'Light Grid Accent 1'
        
        info_data = [
            ('文档标题', report.document.title),
            ('评审时间', report.review_date.strftime('%Y-%m-%d %H:%M')),
            ('评审人', report.reviewer),
            ('总体评价', report.get_overall_rating_display() or '未评级'),
            ('完整度评分', f'{report.completion_score}分'),
            ('问题总数', f'{report.total_issues}个'),
        ]
        
        for i, (label, value) in enumerate(info_data):
            info_table.rows[i].cells[0].text = label
            info_table.rows[i].cells[1].text = str(value)
        
        # 评审总结
        document.add_heading('二、评审总结', level=1)
        document.add_paragraph(report.summary or '无')
        
        if report.recommendations:
            document.add_heading('改进建议', level=2)
            document.add_paragraph(report.recommendations)
        
        # 问题统计
        document.add_heading('三、问题统计', level=1)
        stats_table = document.add_table(rows=4, cols=2)
        stats_table.style = 'Light Grid Accent 1'
        
        stats_data = [
            ('高优先级问题', f'{report.high_priority_issues}个'),
            ('中优先级问题', f'{report.medium_priority_issues}个'),
            ('低优先级问题', f'{report.low_priority_issues}个'),
            ('问题总数', f'{report.total_issues}个'),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            stats_table.rows[i].cells[0].text = label
            stats_table.rows[i].cells[1].text = value
        
        # 详细问题列表
        issues = report.issues.all()
        if issues:
            document.add_heading('四、详细问题列表', level=1)
            
            for idx, issue in enumerate(issues, 1):
                # 问题标题
                issue_title = document.add_heading(
                    f'{idx}. {issue.title}',
                    level=2
                )
                
                # 问题信息表格
                issue_table = document.add_table(rows=5, cols=2)
                issue_table.style = 'Light Grid Accent 1'
                
                issue_data = [
                    ('问题类型', issue.get_issue_type_display()),
                    ('优先级', issue.get_priority_display()),
                    ('位置', issue.location or '未指定'),
                    ('状态', '已解决' if issue.is_resolved else '未解决'),
                    ('问题描述', issue.description),
                ]
                
                for i, (label, value) in enumerate(issue_data):
                    issue_table.rows[i].cells[0].text = label
                    issue_table.rows[i].cells[1].text = value
                
                if issue.suggestion:
                    document.add_paragraph(f'改进建议：{issue.suggestion}')
                
                document.add_paragraph()  # 空行
        
        # 模块评审结果
        module_results = report.module_results.all()
        if module_results:
            document.add_heading('五、模块评审结果', level=1)
            
            for result in module_results:
                module_title = document.add_heading(result.module.title, level=2)
                
                result_table = document.add_table(rows=4, cols=2)
                result_table.style = 'Light Grid Accent 1'
                
                result_data = [
                    ('模块评价', result.get_module_rating_display() or '未评级'),
                    ('问题数量', f'{result.issues_count}个'),
                    ('严重程度', f'{result.severity_score}分'),
                ]
                
                for i, (label, value) in enumerate(result_data):
                    result_table.rows[i].cells[0].text = label
                    result_table.rows[i].cells[1].text = value
                
                if result.strengths:
                    document.add_paragraph(f'优点：{result.strengths}')
                if result.weaknesses:
                    document.add_paragraph(f'不足：{result.weaknesses}')
                if result.recommendations:
                    document.add_paragraph(f'改进建议：{result.recommendations}')
                
                document.add_paragraph()
        
        # 评分详情
        document.add_heading('六、评分详情', level=1)
        scores_table = document.add_table(rows=7, cols=2)
        scores_table.style = 'Light Grid Accent 1'
        
        scores_data = [
            ('完整性评分', f'{report.completeness_score}分'),
            ('一致性评分', f'{report.consistency_score}分'),
            ('可测性评分', f'{report.testability_score}分'),
            ('可行性评分', f'{report.feasibility_score}分'),
            ('清晰度评分', f'{report.clarity_score}分'),
            ('逻辑分析评分', f'{report.logic_score}分'),
            ('完整度评分', f'{report.completion_score}分'),
        ]
        
        for i, (label, value) in enumerate(scores_data):
            scores_table.rows[i].cells[0].text = label
            scores_table.rows[i].cells[1].text = value
        
        # 保存到字节流
        output = io.BytesIO()
        document.save(output)
        output.seek(0)
        
        # 创建响应
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        filename = f'评审报告_{report.document.title}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    @classmethod
    def export_to_pdf(cls, report: ReviewReport) -> HttpResponse:
        """导出报告为PDF格式"""
        output = io.BytesIO()
        
        # 创建PDF文档
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # 查找并注册中文字体
        font_path = cls.find_chinese_font()
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont('Chinese', font_path))
                chinese_font = 'Chinese'
            except Exception:
                chinese_font = 'Helvetica'
        else:
            chinese_font = 'Helvetica'
        
        # 创建样式
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=chinese_font,
            fontSize=24,
            alignment=1,  # 居中
            spaceAfter=30,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=chinese_font,
            fontSize=16,
            spaceBefore=12,
            spaceAfter=6,
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=chinese_font,
            fontSize=10,
        )
        
        # 构建内容
        story = []
        
        # 标题
        story.append(Paragraph(f'{report.document.title} - 评审报告', title_style))
        story.append(Spacer(1, 12))
        
        # 基本信息
        story.append(Paragraph('一、评审基本信息', heading_style))
        info_data = [
            ['文档标题', report.document.title],
            ['评审时间', report.review_date.strftime('%Y-%m-%d %H:%M')],
            ['评审人', report.reviewer],
            ['总体评价', report.get_overall_rating_display() or '未评级'],
            ['完整度评分', f'{report.completion_score}分'],
            ['问题总数', f'{report.total_issues}个'],
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 12))
        
        # 评审总结
        story.append(Paragraph('二、评审总结', heading_style))
        story.append(Paragraph(report.summary or '无', normal_style))
        story.append(Spacer(1, 12))
        
        # 问题统计
        story.append(Paragraph('三、问题统计', heading_style))
        stats_data = [
            ['高优先级', f'{report.high_priority_issues}个'],
            ['中优先级', f'{report.medium_priority_issues}个'],
            ['低优先级', f'{report.low_priority_issues}个'],
            ['总数', f'{report.total_issues}个'],
        ]
        
        stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 12))
        
        # 详细问题列表
        issues = report.issues.all()
        if issues:
            story.append(Paragraph('四、详细问题列表', heading_style))
            
            for idx, issue in enumerate(issues, 1):
                issue_info = f"{idx}. {issue.title} [{issue.get_priority_display()}] [{issue.get_issue_type_display()}]"
                story.append(Paragraph(issue_info, normal_style))
                story.append(Paragraph(f"描述：{issue.description}", normal_style))
                if issue.suggestion:
                    story.append(Paragraph(f"建议：{issue.suggestion}", normal_style))
                story.append(Spacer(1, 6))
        
        # 评分详情
        story.append(Paragraph('五、评分详情', heading_style))
        scores_data = [
            ['评分项', '分数'],
            ['完整性', f'{report.completeness_score}分'],
            ['一致性', f'{report.consistency_score}分'],
            ['可测性', f'{report.testability_score}分'],
            ['可行性', f'{report.feasibility_score}分'],
            ['清晰度', f'{report.clarity_score}分'],
            ['逻辑分析', f'{report.logic_score}分'],
            ['完整度', f'{report.completion_score}分'],
        ]
        
        scores_table = Table(scores_data, colWidths=[2*inch, 2*inch])
        scores_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(scores_table)
        
        # 生成PDF
        doc.build(story)
        output.seek(0)
        
        # 创建响应
        response = HttpResponse(
            output.getvalue(),
            content_type='application/pdf'
        )
        filename = f'评审报告_{report.document.title}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    @classmethod
    def _create_overview_sheet(cls, workbook: Workbook, report: ReviewReport):
        """创建概览sheet"""
        sheet = workbook.create_sheet('评审概览', 0)
        
        # 标题样式
        title_font = Font(name='微软雅黑', size=16, bold=True, color='FFFFFF')
        title_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        title_alignment = Alignment(horizontal='center', vertical='center')
        
        # 内容样式
        header_font = Font(name='微软雅黑', size=11, bold=True)
        header_fill = PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid')
        content_font = Font(name='微软雅黑', size=11)
        content_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        
        # 边框样式
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 标题
        sheet.merge_cells('A1:F1')
        cell = sheet['A1']
        cell.value = f'{report.document.title} - 评审报告'
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = title_alignment
        sheet.row_dimensions[1].height = 30
        
        # 基本信息
        info_data = [
            ['评审时间', report.review_date.strftime('%Y-%m-%d %H:%M'), '', '评审人', report.reviewer, ''],
            ['总体评价', report.get_overall_rating_display() or '未评级', '', '完整度评分', f'{report.completion_score}分', ''],
            ['问题总数', f'{report.total_issues}个', '', '高优先级', f'{report.high_priority_issues}个', ''],
            ['中优先级', f'{report.medium_priority_issues}个', '', '低优先级', f'{report.low_priority_issues}个', ''],
        ]
        
        start_row = 3
        for i, row_data in enumerate(info_data):
            row_num = start_row + i
            for j, value in enumerate(row_data):
                cell = sheet.cell(row=row_num, column=j+1, value=value)
                cell.font = header_font if j % 2 == 0 else content_font
                cell.fill = header_fill if j % 2 == 0 else PatternFill()
                cell.alignment = content_alignment
                cell.border = thin_border
        
        # 调整列宽
        sheet.column_dimensions['A'].width = 15
        sheet.column_dimensions['B'].width = 20
        sheet.column_dimensions['C'].width = 5
        sheet.column_dimensions['D'].width = 15
        sheet.column_dimensions['E'].width = 20
        sheet.column_dimensions['F'].width = 5
        
        # 评审总结
        start_row = 8
        sheet.merge_cells(f'A{start_row}:F{start_row}')
        cell = sheet[f'A{start_row}']
        cell.value = '评审总结'
        cell.font = Font(name='微软雅黑', size=14, bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        cell.alignment = Alignment(horizontal='left', vertical='center')
        sheet.row_dimensions[start_row].height = 25
        
        sheet.merge_cells(f'A{start_row+1}:F{start_row+1}')
        cell = sheet[f'A{start_row+1}']
        cell.value = report.summary or '无'
        cell.font = content_font
        cell.alignment = content_alignment
        cell.border = thin_border
        sheet.row_dimensions[start_row+1].height = 60
        
        # 改进建议
        if report.recommendations:
            start_row = 11
            sheet.merge_cells(f'A{start_row}:F{start_row}')
            cell = sheet[f'A{start_row}']
            cell.value = '改进建议'
            cell.font = Font(name='微软雅黑', size=14, bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.alignment = Alignment(horizontal='left', vertical='center')
            
            sheet.merge_cells(f'A{start_row+1}:F{start_row+1}')
            cell = sheet[f'A{start_row+1}']
            cell.value = report.recommendations
            cell.font = content_font
            cell.alignment = content_alignment
            cell.border = thin_border
            sheet.row_dimensions[start_row+1].height = 60
    
    @classmethod
    def _create_issues_sheet(cls, workbook: Workbook, report: ReviewReport):
        """创建问题列表sheet"""
        sheet = workbook.create_sheet('问题列表', 1)
        
        # 样式定义
        header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        content_font = Font(name='微软雅黑', size=10)
        content_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 表头
        headers = ['序号', '问题标题', '问题类型', '优先级', '位置', '状态', '问题描述', '改进建议']
        for i, header in enumerate(headers):
            cell = sheet.cell(row=1, column=i+1, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        sheet.row_dimensions[1].height = 25
        
        # 数据行
        issues = report.issues.all().order_by('priority', '-created_at')
        for idx, issue in enumerate(issues, 1):
            row_num = idx + 1
            
            row_data = [
                idx,
                issue.title,
                issue.get_issue_type_display(),
                issue.get_priority_display(),
                issue.location or '未指定',
                '已解决' if issue.is_resolved else '未解决',
                issue.description,
                issue.suggestion or '',
            ]
            
            for j, value in enumerate(row_data):
                cell = sheet.cell(row=row_num, column=j+1, value=value)
                cell.font = content_font
                cell.alignment = content_alignment
                cell.border = thin_border
                
                # 根据优先级设置颜色
                if j == 3:  # 优先级列
                    if issue.priority == 'high':
                        cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
                    elif issue.priority == 'medium':
                        cell.fill = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')
                    else:
                        cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
            
            sheet.row_dimensions[row_num].height = 40
        
        # 调整列宽
        column_widths = [6, 25, 12, 10, 20, 10, 40, 40]
        for i, width in enumerate(column_widths):
            sheet.column_dimensions[get_column_letter(i+1)].width = width
    
    @classmethod
    def _create_modules_sheet(cls, workbook: Workbook, report: ReviewReport):
        """创建模块评审结果sheet"""
        sheet = workbook.create_sheet('模块评审结果', 2)
        
        # 样式定义
        header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        content_font = Font(name='微软雅黑', size=10)
        content_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 表头
        headers = ['序号', '模块名称', '评价', '问题数', '严重度', '优点', '不足', '改进建议']
        for i, header in enumerate(headers):
            cell = sheet.cell(row=1, column=i+1, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        sheet.row_dimensions[1].height = 25
        
        # 数据行
        module_results = report.module_results.all().order_by('module__order')
        for idx, result in enumerate(module_results, 1):
            row_num = idx + 1
            
            row_data = [
                idx,
                result.module.title,
                result.get_module_rating_display() or '未评级',
                result.issues_count,
                f'{result.severity_score}分',
                result.strengths or '',
                result.weaknesses or '',
                result.recommendations or '',
            ]
            
            for j, value in enumerate(row_data):
                cell = sheet.cell(row=row_num, column=j+1, value=value)
                cell.font = content_font
                cell.alignment = content_alignment
                cell.border = thin_border
            
            sheet.row_dimensions[row_num].height = 60
        
        # 调整列宽
        column_widths = [6, 20, 12, 10, 10, 30, 30, 30]
        for i, width in enumerate(column_widths):
            sheet.column_dimensions[get_column_letter(i+1)].width = width
    
    @classmethod
    def _create_specialized_sheet(cls, workbook: Workbook, report: ReviewReport):
        """创建专项分析sheet"""
        sheet = workbook.create_sheet('专项分析评分', 3)
        
        # 样式定义
        title_font = Font(name='微软雅黑', size=14, bold=True, color='FFFFFF')
        title_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        
        header_font = Font(name='微软雅黑', size=11, bold=True)
        header_fill = PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid')
        
        content_font = Font(name='微软雅黑', size=11)
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 标题
        sheet.merge_cells('A1:D1')
        cell = sheet['A1']
        cell.value = '专项分析评分'
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        sheet.row_dimensions[1].height = 30
        
        # 评分数据
        scores = [
            ('完整性评分', report.completeness_score),
            ('一致性评分', report.consistency_score),
            ('可测性评分', report.testability_score),
            ('可行性评分', report.feasibility_score),
            ('清晰度评分', report.clarity_score),
            ('逻辑分析评分', report.logic_score),
            ('完整度评分', report.completion_score),
        ]
        
        # 表头
        headers = ['评分项', '分数', '满分', '百分比']
        for i, header in enumerate(headers):
            cell = sheet.cell(row=2, column=i+1, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border
        
        # 数据行
        for idx, (name, score) in enumerate(scores, 3):
            sheet.cell(row=idx, column=1, value=name).font = content_font
            sheet.cell(row=idx, column=2, value=score).font = content_font
            sheet.cell(row=idx, column=3, value=100).font = content_font
            percentage = f'{score}%'
            sheet.cell(row=idx, column=4, value=percentage).font = content_font
            
            for j in range(1, 5):
                cell = sheet.cell(row=idx, column=j)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 调整列宽
        sheet.column_dimensions['A'].width = 20
        sheet.column_dimensions['B'].width = 12
        sheet.column_dimensions['C'].width = 12
        sheet.column_dimensions['D'].width = 12
