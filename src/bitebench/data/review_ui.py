"""Offline review cards; exports only decisions explicitly entered in the UI."""

import html
import json
from pathlib import Path

from pydantic import ValidationError

from bitebench.core.hashing import content_hash
from bitebench.core.schemas import FoodVariant
from bitebench.data.reviews import food_hash


def render_review_cards(cards_path: Path, out: Path):
    cards = json.loads(cards_path.read_text())
    rows, hashes = [], {}
    for card in cards:
        food = card["proposed_food"]
        food_id = food["food_id"]
        valid = False
        try:
            parsed = FoodVariant.model_validate(food)
            hashes[food_id] = food_hash(parsed)
            valid = not card["missing_fields"] and food["data_quality"] != "unknown"
        except ValidationError:
            hashes[food_id] = content_hash(food)
        text = html.escape(json.dumps(card, ensure_ascii=False, indent=2))
        rows.append(f'''<article id="{html.escape(food_id)}"><h2>{html.escape(food_id)} · {html.escape(food["name_zh"])}</h2>
<p>风险：{html.escape(card["risk_level"])} · 状态：needs_review</p>
<details><summary>来源、份量、营养、原始单位与证据</summary><pre>{text}</pre></details>
<label>决定说明 <input data-note="{html.escape(food_id)}" aria-label="{html.escape(food_id)} 决定说明"></label>
<div><button data-id="{html.escape(food_id)}" data-decision="approved" {"disabled" if not valid else ""}>批准</button>
<button data-id="{html.escape(food_id)}" data-decision="needs_review">要求修改</button>
<button data-id="{html.escape(food_id)}" data-decision="rejected">拒绝</button></div>
<p class="result"></p></article>''')
    payload = json.dumps(
        {"cards": cards, "hashes": hashes}, ensure_ascii=False
    ).replace("<", "\\u003c")
    document = (
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BITE 食品审核</title><style>body{font-family:system-ui;max-width:960px;margin:32px auto;padding:0 20px;background:#f7f8fa;color:#202930}article{background:white;padding:20px;margin:16px 0;border:1px solid #ddd;border-radius:10px}button,input{padding:9px;margin:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere}label{display:block}button:disabled{opacity:.45}.result{color:#246544}</style>
<h1>BITE 食品审核</h1><p>当前为待审核提案。缺少标准份量或关键营养时，“批准”不可用。所有按钮仅登记您输入的决定；本页不会自动创建审批，也不会修改正式数据库。</p>
<label>审核者匿名 ID <input id="reviewer" autocomplete="off"></label><button id="export">导出本次决定 JSON</button><p id="summary">尚无决定</p>
"""
        + "\n".join(rows)
        + """<script>
const payload=PAYLOAD, decisions=new Map();
document.querySelectorAll('button[data-decision]').forEach(button=>button.addEventListener('click',()=>{
 const id=button.dataset.id, reviewer=document.querySelector('#reviewer').value.trim();
 const note=button.closest('article').querySelector('input[data-note]').value.trim();
 if(!reviewer || !note){alert('请填写匿名审核者 ID 和决定说明。');return;}
 const card=payload.cards.find(c=>c.proposed_food.food_id===id), food=card.proposed_food;
 decisions.set(id,{food_id:id,food_data_sha256:payload.hashes[id],review_status:button.dataset.decision,
  risk_level:card.risk_level,reviewer_id:reviewer,reviewed_at:new Date().toISOString(),
  evidence_ref:`${food.source_system}:${food.source_record_id}`,decision_note:note,actor_type:'human',is_synthetic:food.is_synthetic});
 button.closest('article').querySelector('.result').textContent=`已登记：${button.textContent}`;
 document.querySelector('#summary').textContent=`本次登记 ${decisions.size} 项；尚未导入正式数据库。`;
}));
document.querySelector('#export').addEventListener('click',()=>{
 if(!decisions.size){alert('没有可导出的人工决定。');return;}
 const blob=new Blob([JSON.stringify([...decisions.values()],null,2)],{type:'application/json'});
 const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='food_review_receipts.json';link.click();URL.revokeObjectURL(link.href);
});</script></html>"""
    )
    document = document.replace("PAYLOAD", payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document)
