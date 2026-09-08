# Residual Contexts (AC-07)

Admitted (<=3): **['dragapult_damage_counter']**

Admission is a valid+safe intervention point; it is separate from whether an improvement exists there (AC-08 found none).

**Criterion 5 (counterfactual stable)** means a counterfactual A/B was run in the context AND its *conclusion* reproduced across two independent 400-game batches. For damage-counter that reproduced conclusion is 'no variant improvement' — the verdict is stable even though the point estimates are noise-dominated. It does NOT mean a variant is stably better. Contexts with no counterfactual A/B cannot satisfy c5.

| context | total | non-forced | 2-meaningful | ECE | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | admitted |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| search_card_target | 9293 | 8995 | 8583 | 0.083 | Y | Y | Y | Y | N | Y | Y | Y | no |
| dragapult_damage_counter | 9150 | 8394 | 8394 | 0.014 | Y | Y | Y | Y | Y | Y | Y | Y | YES |
| promotion_to_active | 1915 | 1425 | 1425 | 0.015 | Y | Y | Y | Y | N | Y | Y | Y | no |
| energy_attachment_target | 1452 | 1422 | 1232 | 0.027 | Y | Y | Y | Y | N | Y | Y | Y | no |
| retreat_switch | 1214 | 1149 | 1149 | 0.073 | Y | Y | Y | Y | N | Y | Y | Y | no |
| evolution_target | 346 | 181 | 181 | 0.018 | Y | N | Y | Y | N | Y | Y | Y | no |
