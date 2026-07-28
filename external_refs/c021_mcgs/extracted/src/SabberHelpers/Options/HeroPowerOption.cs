using System;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.SabberHelper.Option
{
    public readonly struct HeroPowerOption
    {
        //public readonly Controller Controller;
        public readonly ICharacter[] Targets;
        public readonly bool ChooseOne;

        public readonly int Count;
        //public int Count => Targets?.Length ?? 1;

        public HeroPowerOption(bool chooseOne)
        {
            //Controller = controller;
            Targets = null;
            ChooseOne = chooseOne;
            Count = 1;
        }

        public HeroPowerOption(/*Controller controller, */ICharacter[] targets)
        {
            //Controller = controller;
            Targets = targets;
            ChooseOne = false;
            Count = targets?.Length ?? 1;
        }

        public HeroPowerOption ChangeTargets(ICharacter[] newTargets)
        {
            return new HeroPowerOption(/*Controller, */newTargets);
        }

        public HeroPowerTask[] Translate(Controller controller)
        {
            if (Targets == null)
                return new HeroPowerTask[] { HeroPowerTask.Any(controller, skipPrePhase: true) };

            if (ChooseOne)
            {
                return new HeroPowerTask[]
                {
                    HeroPowerTask.Any(controller, null, 1, true),
                    HeroPowerTask.Any(controller, null, 2, true)
                };
            }

            var targets = Targets;
            var result = new HeroPowerTask[targets.Length];
            for (int i = 0; i < targets.Length; i++)
                result[i] = HeroPowerTask.Any(controller, targets[i], skipPrePhase: true);
            return result;
        }

        public void Translate(Controller controller, in Span<PlayerTask> result)
        {
            if (Targets == null)
                result[0] = HeroPowerTask.Any(controller, skipPrePhase: true);
            else if (ChooseOne)
            {
                result[0] = HeroPowerTask.Any(controller, null, 1, true);
                result[1] = HeroPowerTask.Any(controller, null, 2, true);
            }
            else
            {
                var targets = Targets;
                for (int i = 0; i < targets.Length; i++)
                    result[i] = HeroPowerTask.Any(controller, targets[i], skipPrePhase: true);
            }
        }

        public HeroPowerTask GetRandom(Controller controller, Random rnd)
        {
            return Targets == null ? HeroPowerTask.Any(controller, skipPrePhase: true) :
                ChooseOne ? HeroPowerTask.Any(controller, null, rnd.Next(1, 3), true) :
                HeroPowerTask.Any(controller, Targets.Random(rnd), skipPrePhase: true);
        }
    }
}
