"""Regularized BT query model fitted exclusively to synthetic training choices.

This model supports query selection only. It is not calibrated TasteNet or a
formal human-preference performance result.
"""

import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from bitebench.core.hashing import content_hash
from bitebench.core.schemas import TastePair
from bitebench.labeling.protocol import audit


class QueryModel:
    version = "synthetic_bt_query_v1"

    def fit(self, protocol: dict, rows: list[dict]) -> dict:
        audit(protocol)
        ids = sorted(set(protocol["food_ids"]) - set(protocol["heldout_food_ids"]))
        index = {food_id: n for n, food_id in enumerate(ids)}
        allowed = {p["pair_id"]: p for p in protocol["pairs"] if p["split"] == "train"}
        labels, canonical, seen, users = [], [], set(), set()
        for raw in rows:
            row = TastePair.model_validate(raw)
            if (
                not row.is_synthetic
                or row.split != "train"
                or row.pair_id not in allowed
            ):
                raise ValueError(
                    "query fit accepts frozen synthetic training records only"
                )
            pair = allowed[row.pair_id]
            if {row.left_food_id, row.right_food_id} != {
                pair["left_food_id"],
                pair["right_food_id"],
            }:
                raise ValueError("training pair foods mismatch")
            if row.left_food_id not in index or row.right_food_id not in index:
                raise ValueError("heldout food cannot enter query fit")
            if row.pair_id in seen:
                raise ValueError("duplicate training pair")
            seen.add(row.pair_id)
            users.add(row.user_id)
            left, right = sorted([row.left_food_id, row.right_food_id])
            selected = (
                row.left_food_id
                if row.choice == "left"
                else row.right_food_id
                if row.choice == "right"
                else row.choice
            )
            canonical.append(
                dict(
                    pair_id=row.pair_id,
                    left_food_id=left,
                    right_food_id=right,
                    selected=selected,
                )
            )
            if row.choice in {"left", "right"}:
                labels.append((index[left], index[right], float(selected == left)))
        if len(users) > 1:
            raise ValueError("query model is scoped to one synthetic session")
        regularization = 1.0

        def objective(utility):
            loss = 0.5 * regularization * np.dot(utility, utility)
            gradient = regularization * utility.copy()
            for a, b, label in labels:
                logit = utility[a] - utility[b]
                loss += np.logaddexp(0.0, logit) - label * logit
                residual = expit(logit) - label
                gradient[a] += residual
                gradient[b] -= residual
            return float(loss), gradient

        if labels:
            result = minimize(
                objective,
                np.zeros(len(ids)),
                jac=True,
                method="L-BFGS-B",
                options={"maxiter": 200, "ftol": 1e-12, "gtol": 1e-8},
            )
            if not result.success or not np.all(np.isfinite(result.x)):
                raise ValueError("query model optimizer failed")
            utility = result.x - np.mean(result.x)
        else:
            utility = np.zeros(len(ids))
        self.utility = dict(zip(ids, map(float, utility)))
        state = dict(
            version=self.version,
            regularization=regularization,
            food_ids=ids,
            utilities=[self.utility[f] for f in ids],
            split_sha256=protocol["sha256"],
            training_data_sha256=content_hash(
                sorted(canonical, key=lambda r: r["pair_id"])
            ),
            training_records=len(rows),
            fitted_binary_records=len(labels),
            excluded_tie_skip=len(rows) - len(labels),
            is_synthetic=True,
        )
        return state | {"sha256": content_hash(state)}

    def probability(self, left: str, right: str) -> float:
        if left not in self.utility or right not in self.utility:
            raise ValueError("unknown/heldout query food")
        value = float(expit(self.utility[left] - self.utility[right]))
        if not math.isfinite(value):
            raise ValueError("invalid query probability")
        return value
