"""
Report Generator - Generates PDF and JSON reports for analysis results
"""
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from io import BytesIO


class ReportGenerator:
    """Generates analysis reports in PDF and JSON formats"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_json_report(self, result: Dict[str, Any]) -> str:
        """Generate JSON report and return the content"""
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "tool": "AI Repository Analyser",
                "version": "1.0.0"
            },
            "repository": {
                "url": result.get("repo_url", ""),
                "team_name": result.get("team_name", ""),
                "team_leader": result.get("team_leader_name", ""),
                "branch_created": result.get("branch_name", ""),
                "branch_url": result.get("branch_url"),
                "commit_sha": result.get("commit_sha")
            },
            "analysis_summary": {
                "status": result.get("status", ""),
                "total_issues_detected": result.get("total_failures_detected", 0),
                "total_fixes_applied": result.get("total_fixes_applied", 0),
                "total_time_seconds": result.get("total_time_taken", 0),
                "start_time": result.get("start_time"),
                "end_time": result.get("end_time")
            },
            "iteration_details": result.get("summary", {}),
            "fixes": [
                {
                    "file": fix.get("file_path", ""),
                    "line": fix.get("line_number", 0),
                    "bug_type": fix.get("bug_type", ""),
                    "status": fix.get("status", ""),
                    "commit_message": fix.get("commit_message", ""),
                    "description": fix.get("description", ""),
                    "original_code": fix.get("original_code", ""),
                    "fixed_code": fix.get("fixed_code", "")
                }
                for fix in result.get("fixes", [])
            ],
            "test_results": [
                {
                    "name": test.get("test_name", ""),
                    "passed": test.get("passed", False),
                    "error": test.get("error_message"),
                    "duration": test.get("duration")
                }
                for test in result.get("test_results", [])
            ],
            "generated_tests": result.get("generated_tests", [])
        }
        
        return json.dumps(report, indent=2, default=str)
    
    def save_json_report(self, result: Dict[str, Any], filename: str = None) -> str:
        """Save JSON report to file and return path"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            team_slug = result.get("team_name", "unknown").replace(" ", "_")
            filename = f"report_{team_slug}_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.generate_json_report(result))
        
        return filepath
    
    def generate_pdf_report(self, result: Dict[str, Any]) -> bytes:
        """Generate PDF report and return bytes"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, Image
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
        except ImportError:
            # Return error message as PDF-like content if reportlab not installed
            return self._generate_simple_pdf(result)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=72)
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a365d')
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#2d3748')
        )
        
        normal_style = styles['Normal']
        
        story = []
        
        # Title
        story.append(Paragraph("AI Repository Analysis Report", title_style))
        story.append(Spacer(1, 20))
        
        # Report metadata
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
        story.append(Spacer(1, 20))
        
        # Repository Info
        story.append(Paragraph("Repository Information", heading_style))
        repo_data = [
            ["Repository URL:", result.get("repo_url", "N/A")],
            ["Team Name:", result.get("team_name", "N/A")],
            ["Team Leader:", result.get("team_leader_name", "N/A")],
            ["Branch Created:", result.get("branch_name", "N/A")]
        ]
        
        if result.get("commit_sha"):
            repo_data.append(["Commit SHA:", result.get("commit_sha")])
        
        repo_table = Table(repo_data, colWidths=[2*inch, 4*inch])
        repo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#edf2f7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2d3748')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        story.append(repo_table)
        story.append(Spacer(1, 20))
        
        # Analysis Summary
        story.append(Paragraph("Analysis Summary", heading_style))
        
        summary = result.get("summary", {})
        resolution_status = summary.get("resolution_status", result.get("status", ""))
        
        summary_data = [
            ["Status:", resolution_status],
            ["Total Issues Detected:", str(result.get("total_failures_detected", 0))],
            ["Total Fixes Applied:", str(result.get("total_fixes_applied", 0))],
            ["Iterations:", str(summary.get("total_iterations", 1))],
            ["Total Time:", f"{result.get('total_time_taken', 0):.2f}s"]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#edf2f7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2d3748')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Fixes Applied
        fixes = result.get("fixes", [])
        if fixes:
            story.append(Paragraph("Fixes Applied", heading_style))
            
            fix_data = [["File", "Line", "Type", "Status", "Description"]]
            for fix in fixes[:20]:  # Limit to 20 fixes
                fix_data.append([
                    fix.get("file_path", "")[:30],
                    str(fix.get("line_number", "")),
                    fix.get("bug_type", ""),
                    fix.get("status", ""),
                    (fix.get("commit_message", "") or "")[:40]
                ])
            
            fix_table = Table(fix_data, colWidths=[1.5*inch, 0.5*inch, 0.8*inch, 0.7*inch, 2.5*inch])
            fix_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')])
            ]))
            story.append(fix_table)
            
            if len(fixes) > 20:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"... and {len(fixes) - 20} more fixes", normal_style))
        
        story.append(Spacer(1, 20))
        
        # Test Results
        test_results = result.get("test_results", [])
        if test_results:
            story.append(Paragraph("Test Results", heading_style))
            
            test_data = [["Test Name", "Status", "Duration"]]
            for test in test_results[:15]:
                test_data.append([
                    test.get("test_name", "")[:50],
                    "PASSED" if test.get("passed") else "FAILED",
                    f"{test.get('duration', 0):.3f}s" if test.get('duration') else "N/A"
                ])
            
            test_table = Table(test_data, colWidths=[4*inch, 1*inch, 1*inch])
            test_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
            ]))
            story.append(test_table)
        
        # Generated Tests
        generated_tests = result.get("generated_tests", [])
        if generated_tests:
            story.append(PageBreak())
            story.append(Paragraph("AI-Generated Test Cases", heading_style))
            story.append(Paragraph(f"Total tests generated: {len(generated_tests)}", normal_style))
            story.append(Spacer(1, 10))
            
            for i, test in enumerate(generated_tests[:10], 1):
                story.append(Paragraph(f"<b>Test {i}:</b> {test.get('test_name', 'Unknown')}", normal_style))
                story.append(Paragraph(f"Target: {test.get('target_file', 'N/A')}", normal_style))
                story.append(Spacer(1, 5))
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph("─" * 60, normal_style))
        story.append(Paragraph(
            "Generated by AI Repository Analyser - Powered by LangChain + Groq LLaMA",
            ParagraphStyle('Footer', parent=normal_style, alignment=TA_CENTER, fontSize=8)
        ))
        
        # Build PDF
        doc.build(story)
        
        return buffer.getvalue()
    
    def _generate_simple_pdf(self, result: Dict[str, Any]) -> bytes:
        """Generate a simple text-based PDF if reportlab is not available"""
        # This is a fallback that creates a simple text representation
        content = f"""
AI Repository Analysis Report
============================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Repository Information
----------------------
URL: {result.get('repo_url', 'N/A')}
Team: {result.get('team_name', 'N/A')}
Leader: {result.get('team_leader_name', 'N/A')}
Branch: {result.get('branch_name', 'N/A')}

Analysis Summary
----------------
Status: {result.get('status', 'N/A')}
Issues Detected: {result.get('total_failures_detected', 0)}
Fixes Applied: {result.get('total_fixes_applied', 0)}
Time: {result.get('total_time_taken', 0):.2f}s

Fixes Applied
-------------
"""
        for fix in result.get('fixes', [])[:20]:
            content += f"- {fix.get('file_path', '')}:{fix.get('line_number', '')} [{fix.get('status', '')}] {fix.get('commit_message', '')}\n"
        
        content += "\n\nGenerated by AI Repository Analyser"
        
        return content.encode('utf-8')
    
    def save_pdf_report(self, result: Dict[str, Any], filename: str = None) -> str:
        """Save PDF report to file and return path"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            team_slug = result.get("team_name", "unknown").replace(" ", "_")
            filename = f"report_{team_slug}_{timestamp}.pdf"
        
        filepath = os.path.join(self.output_dir, filename)
        
        pdf_bytes = self.generate_pdf_report(result)
        
        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)
        
        return filepath
