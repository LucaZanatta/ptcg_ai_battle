"""Mutation test: break the code in ways the tests SHOULD catch, and count which survive.

A surviving mutant is a defect the suite cannot see. This is the only way to find out whether
97 passing tests mean anything.
"""
import subprocess, shutil, os, sys, tempfile
REPO='/home/luca/kaggle/ptcg_ai_battle'
MUTANTS = [
  ("mcgs_graph", "starter_kit/c021_mcgs_graph.py",
   'return x + c * math.sqrt(2.0 * math.log(n) / self.visit_count)',
   'return x + c * math.sqrt(1.0 * math.log(n) / self.visit_count)', "UCB1 constant 2->1"),
  ("mcgs_graph", "starter_kit/c021_mcgs_graph.py",
   'n = self.predecessor.total_visit if ucd else self.predecessor.visit_count',
   'n = self.predecessor.visit_count', "UCD divisor -> visit_count"),
  ("mcgs_graph", "starter_kit/c021_mcgs_graph.py",
   'return int(round(sample_width / (dp ** num_sample_traversed)))',
   'return int(round(sample_width / (dp ** max(0, num_sample_traversed - 1))))', "damping off-by-one"),
  ("mcgs_graph", "starter_kit/c021_mcgs_graph.py",
   'if self.is_opponent:\n            reward *= -1.0',
   'if False:\n            reward *= -1.0', "opponent sign flip removed"),
  ("learn", "starter_kit/c021_byterl_learn.py",
   'clipped_rho = torch.clamp(rho, max=rho_bar)',
   'clipped_rho = rho', "V-trace rho clipping removed"),
  ("learn", "starter_kit/c021_byterl_learn.py",
   'nxt = torch.where(q_tp1[t] >= vals_tp1[t], g, vals_tp1[t])',
   'nxt = g', "UPGO never cuts to baseline"),
  ("learn", "starter_kit/c021_byterl_learn.py",
   'self.G.clear()\n        self.C.clear()',
   'pass', "OSFP period reset removed"),
  ("model", "starter_kit/c021_byterl_model.py",
   'logits = logits.masked_fill(mask <= 0, NEG_INF)',
   'logits = logits', "action masking removed"),
  ("deck", "starter_kit/c021_byterl_deck.py",
   '"ace_spec": aces, "ace_spec_ok": aces <= ACE_SPEC_LIMIT,',
   '"ace_spec": aces, "ace_spec_ok": True,', "ACE SPEC limit disabled"),
  ("deck", "starter_kit/c021_byterl_deck.py",
   'if int(getattr(cd, "cardType", -1) or -1) != CARD_TYPE_ENERGY:\n        return False',
   'if False:\n        return False', "energy cap -> everything uncapped"),
  ("mcgs", "starter_kit/c021_mcgs.py",
   'v = getattr(st, "yourIndex", None)\n        return default if v is None else int(v)',
   'return default', "yourIndex always default"),
]
env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
survived, killed = [], []
for tag, rel, old, new, desc in MUTANTS:
    p = os.path.join(REPO, rel); orig = open(p).read()
    if old not in orig:
        print(f"  SKIP (pattern not found): {desc}"); continue
    open(p,'w').write(orig.replace(old, new, 1))
    try:
        r = subprocess.run([os.path.join(REPO,'.venv/bin/python'),'-m','pytest','tests/','-q',
                            '-p','no:cacheprovider','-k','c021','-x','--no-header'],
                           cwd=REPO, capture_output=True, text=True, timeout=900, env=env)
        if r.returncode == 0: survived.append(desc)
        else: killed.append(desc)
    finally:
        open(p,'w').write(orig)
    print(f"  {'SURVIVED *** ' if desc in survived else 'killed      '} {desc}")
print()
print(f"killed {len(killed)}/{len(killed)+len(survived)}   survived {len(survived)}")
for s in survived: print("  SURVIVING MUTANT:", s)
