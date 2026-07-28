using System;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.SabberHelper.Option
{
    public readonly struct AttackOption
    {
        //public readonly Controller Controller;
        public readonly ICharacter Source;
        public readonly Minion[] Targets;
        public readonly bool IsHeroValidTarget;

        //public int Count => Targets.Length + (IsHeroValidTarget ? 1 : 0);
        public readonly int Count;

        public AttackOption(ICharacter source, Minion[] targets, bool isHeroValidTarget)
        {
            //Controller = controller;
            Source = source;
            Targets = targets;
            IsHeroValidTarget = isHeroValidTarget;
            Count = targets.Length + (isHeroValidTarget ? 1 : 0);
        }

        // HeroAttackTask
        // Source == null
        public AttackOption(Minion[] targets, bool isHeroValidTarget)
        {
            //Controller = controller;
            Source = null;
            Targets = targets;
            IsHeroValidTarget = isHeroValidTarget;
            Count = targets.Length + (isHeroValidTarget ? 1 : 0);
        }

        public AttackOption ChangeTargets(Minion[] newTargets)
        {
            return new AttackOption(Source, newTargets, IsHeroValidTarget);
        }

        public PlayerTask[] Translate(Controller controller)
        {
            var result = new PlayerTask[Count];
            // MinionAttackTasks
            if (Source != null)
            {
                if (Targets != null)
                {
                    for (int i = 0; i < Targets.Length; i++)
                        result[i] = MinionAttackTask.Any(controller, Source, Targets[i], true);
                }

                if (IsHeroValidTarget)
                    result[result.Length - 1] = MinionAttackTask.Any(controller, Source, controller.Opponent.Hero, true);
            }
            else
            {
                for (int i = 0; i < Targets.Length; i++)
                    result[i] = HeroAttackTask.Any(controller, Targets[i], true);

                if (IsHeroValidTarget)
                    result[result.Length - 1] = HeroAttackTask.Any(controller, controller.Opponent.Hero, true);
            }

            return result;
        }

        public void Translate(Controller controller, in Span<PlayerTask> result)
        {
            if (Source != null)
            {
                if (Targets != null)
                {
                    for (int i = 0; i < Targets.Length; i++)
                        result[i] = MinionAttackTask.Any(controller, Source, Targets[i], true);
                }

                if (IsHeroValidTarget)
                    result[result.Length - 1] = MinionAttackTask.Any(controller, Source, controller.Opponent.Hero, true);
            }
            else
            {
                for (int i = 0; i < Targets.Length; i++)
                    result[i] = HeroAttackTask.Any(controller, Targets[i], true);

                if (IsHeroValidTarget)
                    result[result.Length - 1] = HeroAttackTask.Any(controller, controller.Opponent.Hero, true);
            }
        }

        public PlayerTask GetRandom(Controller controller, Random rnd)
        {
            int roll = rnd.Next(Count);
            if (Source != null)
            {
                if (IsHeroValidTarget)
                {
                    if (roll == Count - 1)
                        return MinionAttackTask.Any(controller, Source, controller.Opponent.Hero, true);
                    else
                        return MinionAttackTask.Any(controller, Source, Targets[roll], true);
                }

                return MinionAttackTask.Any(controller, Source, Targets[roll], true);
            }
            else
            {
                if (IsHeroValidTarget && roll == Count - 1)
                    return HeroAttackTask.Any(controller, controller.Opponent.Hero, true);

                return HeroAttackTask.Any(controller, Targets[roll], true);
            }
        }

        public static bool Equals(in AttackOption a, in AttackOption b)
        {
            return
                a.Count == b.Count &&
                a.Source?.Card.AssetId == b.Source?.Card.AssetId &&
                a.IsHeroValidTarget == b.IsHeroValidTarget &&
                a.Targets?.Length == b.Targets?.Length;
        }

        public override int GetHashCode()
        {
            var hashCode = Count;

            hashCode = (hashCode * 17) ^ (Source?.Card.AssetId ?? 0);
            hashCode = (hashCode * 17) ^ IsHeroValidTarget.GetHashCode();
            hashCode = (hashCode * 17) ^ (Targets?.Length ?? 0);

            return hashCode;
        }
    }
}
