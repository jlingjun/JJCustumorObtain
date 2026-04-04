"""
Apple 联系页面信息提取脚本
从 https://www.apple.com/contact/ 提取联系方式
"""

import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "cobtainflow" / "src"))

# 直接导入工具模块
from cobtainflow.tools.contact_discovery_tools import SpiderSinglePageContactTool


def extract_apple_contacts():
    """提取 Apple 联系页面信息"""

    print("=" * 80)
    print("Apple 联系页面信息提取")
    print("=" * 80)
    print()

    # 初始化工具
    spider_tool = SpiderSinglePageContactTool()

    # 目标 URL
    url = "https://www.apple.com/contact/"

    print(f"正在抓取页面: {url}")
    print()

    # 执行抓取
    result_json = spider_tool._run(
        url=url,
        company_name="Apple",
        extract_contacts=True,
        include_html=False,
        include_text=True,
        max_text_chars=15000
    )

    # 解析结果
    result = json.loads(result_json)

    # 打印结果摘要
    print("-" * 80)
    print("提取结果摘要")
    print("-" * 80)
    print(f"状态: {result['status']}")
    print(f"请求URL: {result['requested_url']}")
    print(f"解析URL: {result.get('resolved_url', 'N/A')}")
    print(f"找到的联系方式数量: {len(result['contacts'])}")
    print(f"页面证据数量: {len(result['page_evidence'])}")
    print()

    # 分类显示联系方式
    if result['contacts']:
        print("-" * 80)
        print("联系方式详情")
        print("-" * 80)

        # 按类型分组
        contacts_by_type = {}
        for contact in result['contacts']:
            contact_type = contact['type']
            if contact_type not in contacts_by_type:
                contacts_by_type[contact_type] = []
            contacts_by_type[contact_type].append(contact)

        for contact_type, contacts in contacts_by_type.items():
            print(f"\n【{contact_type.upper()}】")
            for i, contact in enumerate(contacts, 1):
                print(f"  {i}. {contact['normalized'] or contact['value']}")
                print(f"     置信度: {contact['confidence']:.2f}")
                if contact.get('source_context'):
                    context = contact['source_context'][:100]
                    print(f"     上下文: {context}...")
                print()

    # 显示缺失信息提示
    if result.get('missing_hints'):
        print()
        print("-" * 80)
        print("缺失信息提示")
        print("-" * 80)
        for hint in result['missing_hints']:
            print(f"  - {hint}")

    # 显示页面证据
    if result['page_evidence']:
        print()
        print("-" * 80)
        print("页面证据")
        print("-" * 80)
        for evidence in result['page_evidence']:
            print(f"\n页面: {evidence['page_url']}")
            if evidence.get('page_title'):
                print(f"标题: {evidence['page_title']}")
            if evidence.get('summary'):
                print(f"摘要: {evidence['summary']}")
            print(f"找到联系方式: {evidence['contacts_found']} 个")
            print(f"找到链接: {evidence['links_found']} 个")
            if evidence.get('supports_fields'):
                print(f"支持字段: {', '.join(evidence['supports_fields'])}")

    # 保存完整结果
    output_dir = Path(__file__).parent
    output_file = output_dir / "apple_contact_extraction.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 80)
    print(f"完整结果已保存到: {output_file}")
    print("=" * 80)

    return result


def generate_report(result):
    """生成 Markdown 格式的报告"""

    report_lines = []
    report_lines.append("# Apple 联系方式搜索报告")
    report_lines.append("")
    report_lines.append(f"**搜索时间**: 2026-04-01")
    report_lines.append(f"**目标页面**: {result['requested_url']}")
    report_lines.append(f"**搜索状态**: {result['status']}")
    report_lines.append("")

    # 搜索摘要
    report_lines.append("## 搜索摘要")
    report_lines.append("")
    report_lines.append(f"- 找到的联系方式数量: **{len(result['contacts'])}**")
    report_lines.append(f"- 分析的页面数量: **{len(result['page_evidence'])}**")
    report_lines.append("")

    # 联系方式详情
    if result['contacts']:
        report_lines.append("## 联系方式详情")
        report_lines.append("")

        contacts_by_type = {}
        for contact in result['contacts']:
            contact_type = contact['type']
            if contact_type not in contacts_by_type:
                contacts_by_type[contact_type] = []
            contacts_by_type[contact_type].append(contact)

        for contact_type, contacts in contacts_by_type.items():
            report_lines.append(f"### {contact_type.upper()}")
            report_lines.append("")
            for i, contact in enumerate(contacts, 1):
                report_lines.append(f"{i}. **{contact['normalized'] or contact['value']}**")
                report_lines.append(f"   - 置信度: {contact['confidence']:.2f}")
                report_lines.append(f"   - 来源: {contact['source_url']}")
                if contact.get('source_context'):
                    context = contact['source_context'][:150].replace('\n', ' ')
                    report_lines.append(f"   - 上下文: {context}")
                report_lines.append("")

    # 缺失信息
    if result.get('missing_hints'):
        report_lines.append("## 缺失信息提示")
        report_lines.append("")
        for hint in result['missing_hints']:
            report_lines.append(f"- {hint}")
        report_lines.append("")

    # 页面证据
    if result['page_evidence']:
        report_lines.append("## 页面分析证据")
        report_lines.append("")
        for evidence in result['page_evidence']:
            report_lines.append(f"### {evidence['page_url']}")
            report_lines.append("")
            if evidence.get('page_title'):
                report_lines.append(f"**页面标题**: {evidence['page_title']}")
                report_lines.append("")
            if evidence.get('summary'):
                report_lines.append(f"**页面摘要**: {evidence['summary']}")
                report_lines.append("")
            report_lines.append(f"- 找到联系方式: {evidence['contacts_found']} 个")
            report_lines.append(f"- 找到链接: {evidence['links_found']} 个")
            if evidence.get('supports_fields'):
                report_lines.append(f"- 支持字段: {', '.join(evidence['supports_fields'])}")
            report_lines.append("")

    # 保存报告
    output_dir = Path(__file__).parent
    report_file = output_dir / "Apple联系方式搜索报告.md"

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"Markdown 报告已保存到: {report_file}")

    return '\n'.join(report_lines)


if __name__ == "__main__":
    # 提取联系方式
    result = extract_apple_contacts()

    # 生成报告
    report = generate_report(result)

    print("\n" + "=" * 80)
    print("报告预览")
    print("=" * 80)
    print(report[:1000])
    if len(report) > 1000:
        print("\n... (报告已截断，完整内容请查看文件)")
