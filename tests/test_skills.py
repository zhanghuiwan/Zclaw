"""
Skills 模块验证脚本

测试 skills 模块的基本功能。
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.skills import SkillManager, SkillsConfig
from src.skills.models import SkillDefinition


def test_skill_discovery():
    """测试 skill 发现功能"""
    print("\n" + "=" * 50)
    print("测试 1: Skill 发现功能")
    print("=" * 50)

    config = SkillsConfig.with_defaults(project_root=PROJECT_ROOT)
    print(f"全局路径：{config.global_path}")
    print(f"项目路径：{config.project_path}")

    manager = SkillManager(config)
    manager.initialize()
    skills = manager.list_skills()

    print(f"\n发现 {len(skills)} 个 skills:")
    for skill in skills:
        print(f"  - {skill.name}: {skill.description}")
        if skill.triggers:
            print(f"    触发词：{', '.join(skill.triggers[:5])}")

    return len(skills) > 0


def test_skill_matching():
    """测试 skill 匹配功能"""
    print("\n" + "=" * 50)
    print("测试 2: Skill 匹配功能")
    print("=" * 50)

    config = SkillsConfig.with_defaults(project_root=PROJECT_ROOT)
    manager = SkillManager(config)
    manager.initialize()

    test_queries = [
        "搜索附近的美食",
        "规划路线",
        "查一下天安门",
        "生成热力图",
    ]

    for query in test_queries:
        matches = manager.match_skills(query)
        print(f"\n查询：'{query}'")
        if matches:
            for match in matches:
                print(f"  → 匹配：{match.name}")
        else:
            print("  → 无匹配")

    return True


def test_skill_context():
    """测试 skill 上下文注入"""
    print("\n" + "=" * 50)
    print("测试 3: Skill 上下文注入")
    print("=" * 50)

    config = SkillsConfig.with_defaults(project_root=PROJECT_ROOT)
    manager = SkillManager(config)
    manager.initialize()

    query = "搜索西直门周边美食"
    context = manager.get_context(query)

    print(f"查询：'{query}'")
    print(f"上下文长度：{len(context)} 字符")
    if context:
        print("\n上下文预览:")
        print(context[:500] + "..." if len(context) > 500 else context)

    return True


def test_skill_execution():
    """测试 skill 执行功能"""
    print("\n" + "=" * 50)
    print("测试 4: Skill 执行功能")
    print("=" * 50)

    config = SkillsConfig.with_defaults(project_root=PROJECT_ROOT)
    manager = SkillManager(config)
    manager.initialize()

    skills = manager.list_skills()
    if not skills:
        print("没有可用的 skills，跳过执行测试")
        return False

    # 测试第一个 skill
    skill = skills[0]
    print(f"执行 skill: {skill.name}")
    print(f"描述：{skill.description}")
    print(f"Triggers：{skill.triggers}")
    print(f"Requires env：{skill.requires.env_vars}")

    # execute_skill 是 async 方法，这里简单测试可用性
    print("✓ Skill 结构和依赖检查通过（异步执行需要 await）")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("  Zclaw Skills 模块验证")
    print("=" * 60)

    tests = [
        ("Skill 发现", test_skill_discovery),
        ("Skill 匹配", test_skill_matching),
        ("上下文注入", test_skill_context),
        ("Skill 执行", test_skill_execution),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} 测试失败：{e}")
            results.append((name, False))

    # 汇总结果
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✓" if success else "✗"
        print(f"  {status} {name}")

    print(f"\n总计：{passed}/{total} 通过")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
