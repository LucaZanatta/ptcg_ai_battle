import os

# Check what else is in the competition data folder
base = "/home/luca/kaggle/ptcg_ai_battle"
for root, dirs, files in os.walk(base):
    for f in files:
        print(os.path.join(root, f))