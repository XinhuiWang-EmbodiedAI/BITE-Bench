"""Local terminal questionnaire for synthetic demonstration only."""

import json
from pathlib import Path

import typer

from bitebench.core.schemas import DayPlan, TastePair
from bitebench.core.validation import load_foods
from bitebench.labeling.protocol import read, verify_foods
from bitebench.labeling.questionnaire import (
    AnchorRating,
    MenuChoice,
    read_questionnaire,
)
from bitebench.labeling.storage import now
from bitebench.labeling.survey_storage import VISIBLE, SurveyStore
from bitebench.nutrition.calculator import calculate_day


class PauseSurvey(Exception):
    pass


def ask(text: str) -> str:
    value = typer.prompt(text).strip()
    if value.lower() == "exit":
        raise PauseSurvey
    return value


def choice() -> str:
    while True:
        value = ask("选择 left / right / tie / skip；exit 保存退出").lower()
        if value in {"left", "right", "tie", "skip"}:
            return value
        typer.echo("请选择上述四个值。")


def tried(side: str) -> bool | None:
    while True:
        value = ask(f"是否吃过{side}食物 yes / no / unknown").lower()
        if value in {"yes", "no", "unknown"}:
            return {"yes": True, "no": False, "unknown": None}[value]


def rating() -> float:
    while True:
        try:
            value = float(ask("预期美味评分 0–10；exit 保存退出"))
            if 0 <= value <= 10:
                return value
        except ValueError:
            pass
        typer.echo("请输入 0–10 的有限数值。")


def hunger() -> float | None:
    while True:
        raw = ask("自愿填写饥饿程度 0–10，或 unknown")
        if raw == "unknown":
            return None
        try:
            value = float(raw)
            if 0 <= value <= 10:
                return value
        except ValueError:
            pass
        typer.echo("请输入 0–10，或 unknown。")


def run(
    protocol_path: Path,
    questionnaire_path: Path,
    foods_path: Path,
    database: Path,
    mode: str = "synthetic_only",
    group: str = "planned",
) -> None:
    if mode != "synthetic_only":
        raise ValueError("human collection disabled")
    protocol = read(protocol_path)
    verify_foods(protocol, foods_path)
    manifest = read_questionnaire(questionnaire_path, protocol)
    foods = load_foods(foods_path, True)
    menus = {m["menu_id"]: DayPlan.model_validate(m) for m in manifest["menus"]}
    typer.echo("SYNTHETIC DEMO · 合成工程问卷，非真人研究采集。")
    typer.echo("食物和营养均为虚构夹具；回答一律标记 synthetic，不用于真人结论。")
    typer.echo("正式问卷需成年、自愿、匿名、可撤回；此演示不收集姓名或身体信息。")
    typer.echo("说明版本 synthetic_notice_v1；数据仅存本地合成目录，不自动公开。")
    if ask("输入 DEMO 确认仅测试合成流程；exit 退出") != "DEMO":
        typer.echo("未确认，未创建用户。")
        return
    store = SurveyStore(database, protocol, manifest, mode)
    try:
        action = ask("输入 new 新建 / resume 恢复 / withdraw 撤回")
        if action == "new":
            if group not in {"planned", "random", "active"}:
                raise ValueError("invalid synthetic assignment group")
            if protocol.get("assignment_order") and group != "planned":
                raise ValueError("sized fixture requires planned group assignment")
            user, token = (
                store.register_planned()
                if group == "planned"
                else store.register(group)
            )
            store.acknowledge_demo(user)
            typer.echo(f"恢复/撤回 token（请自行保存）：{token}")
        elif action in {"resume", "withdraw"}:
            token = typer.prompt("恢复/撤回 token", hide_input=True).strip()
            user = store.resume(token)
            if action == "withdraw":
                store.withdraw(token)
                typer.echo("数据库内记录已撤回。此前导出副本不会自动回收。")
                return
        else:
            typer.echo("未知操作，未创建用户。")
            return
        while True:
            task = store.next_task(user)
            typer.echo(json.dumps(store.summary(user), ensure_ascii=False))
            if task["kind"] == "complete":
                typer.echo("合成演示完成。可用已保存 token 恢复查看或撤回。")
                return
            if task["kind"] == "taste":
                pair = task["pair"]
                display = store.taste_display(user, pair["pair_id"])
                typer.echo("只考虑预期好吃程度，不考虑热量、价格或健康。")
                for side, key in [("左", "left_food_id"), ("右", "right_food_id")]:
                    food = foods[display[key]]
                    typer.echo(
                        f"{side}：{food.name_zh}，标准份量 {food.serving_g:g} g；{food.recipe_variant}"
                    )
                answer = choice()
                seen_left, seen_right = tried("左"), tried("右")
                hunger_value = hunger()
                store.record(
                    TastePair(
                        user_id=user,
                        pair_id=pair["pair_id"],
                        **display,
                        choice=answer,
                        assignment_group=store.assignment_group(user),
                        query_policy=task["query_policy"],
                        split=pair["split"],
                        seen_left=seen_left,
                        seen_right=seen_right,
                        self_reported_hunger=hunger_value,
                        timestamp=now(),
                        is_synthetic=True,
                    )
                )
            elif task["kind"] == "anchor":
                food = foods[task["food_id"]]
                typer.echo(
                    f"训练锚点：{food.name_zh}；标准份量 {food.serving_g:g} g。评分表示预期美味，非真实试吃体验。"
                )
                store.record_anchor(
                    AnchorRating(
                        user_id=user,
                        food_id=food.food_id,
                        rating_0_10=rating(),
                        timestamp=now(),
                    )
                )
            else:
                pair, stage = task["pair"], task["stage"]
                display = store.menu_display(user, pair["menu_pair_id"], stage)
                visible = stage == VISIBLE
                typer.echo("菜单阶段：" + ("显示合成营养" if visible else "隐藏营养"))
                for side, key in [("左", "menu_a_id"), ("右", "menu_b_id")]:
                    menu = menus[display[key]]
                    typer.echo(f"{side}菜单：")
                    for meal in menu.meals:
                        items = [
                            f"{foods[i.food_id].name_zh} {foods[i.food_id].serving_g * i.servings:g} g"
                            for i in meal.items
                        ]
                        typer.echo(f"  {meal.slot}：" + "、".join(items))
                    if visible:
                        totals = calculate_day(menu, foods, True)
                        typer.echo(
                            "SYNTHETIC 营养（kcal/g/mg，非已审核数据库值）："
                            + json.dumps(totals["totals"])
                        )
                typer.echo("选择更愿意采用的一日菜单。")
                store.record_menu(
                    MenuChoice(
                        user_id=user,
                        menu_pair_id=pair["menu_pair_id"],
                        **display,
                        stage=stage,
                        displayed_nutrition=visible,
                        choice=choice(),
                        timestamp=now(),
                    )
                )
    except PauseSurvey:
        typer.echo("已保存先前完成的记录；使用 token 可恢复。当前未提交问题不会写入。")
    finally:
        store.close()
