"""Does one gradient step move probability mass TOWARD the higher-reward action?

pg_loss = -(advantage * target_logp).mean(), minimised by the optimiser, so a positive
advantage must INCREASE target_logp. If the sign is inverted, every downstream number is noise
and the ladder measures nothing.
"""
import sys; sys.path.insert(0, '/home/luca/kaggle/ptcg_ai_battle')
import torch; torch.set_num_threads(1)
from cg import c021_byterl_learn as L

torch.manual_seed(0)
# one state, two actions; the agent took action 0 and WON (terminal reward 1.0)
logits = torch.zeros(1, 2, requires_grad=True)
value  = torch.zeros(1, requires_grad=True)
opt = torch.optim.SGD([logits, value], lr=1.0)

def step(action, reward):
    lp = torch.log_softmax(logits, -1)
    target_logp = lp[:, action]
    entropy = -(lp.exp() * lp).sum(-1)
    behaviour = target_logp.detach()          # on-policy: mu == pi
    rewards = torch.tensor([float(reward)])
    total, st = L.byterl_losses(target_logp, behaviour, entropy, value, rewards,
                               torch.zeros(()), torch.ones(1),
                               L.LossConfig(entropy_coef=0.0, value_coef=0.0))
    opt.zero_grad(); total.backward(); opt.step()
    return st

p0 = torch.softmax(logits, -1)[0].tolist()
st = step(action=0, reward=1.0)
p1 = torch.softmax(logits, -1)[0].tolist()
print(f"took action 0, reward 1.0")
print(f"  P(action0) before -> after : {p0[0]:.4f} -> {p1[0]:.4f}")
print(f"  pg_loss {st['pg_loss']:+.5f}   advantage-driven")
moved_toward = p1[0] > p0[0]
print(f"  moved TOWARD the rewarded action: {moved_toward}")

# and the converse: a losing action must lose mass
torch.manual_seed(0)
logits2 = torch.zeros(1, 2, requires_grad=True); value2 = torch.zeros(1, requires_grad=True)
opt = torch.optim.SGD([logits2, value2], lr=1.0)
lp = torch.log_softmax(logits2, -1); tlp = lp[:, 0]
ent = -(lp.exp()*lp).sum(-1)
total, _ = L.byterl_losses(tlp, tlp.detach(), ent, value2, torch.tensor([0.0]),
                          torch.zeros(()), torch.ones(1),
                          L.LossConfig(entropy_coef=0.0, value_coef=0.0))
opt.zero_grad(); total.backward(); opt.step()
q = torch.softmax(logits2, -1)[0].tolist()
print(f"took action 0, reward 0.0")
print(f"  P(action0) 0.5000 -> {q[0]:.4f}   (should not increase)")
print()
print("VERDICT:", "SIGN CORRECT" if moved_toward and q[0] <= 0.5 + 1e-9 else "*** SIGN INVERTED ***")
