using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCoreAi.MCGS.SabberHelper.Option;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.DefaultPolicy
{
    public class UniformRandomRollout : Policy
    {
        private Options Options;

        internal UniformRandomRollout(in OptionsFilter[] filters) : base(in filters) { }

        internal override void Play(Game g)
        {
	        Controller c = g.CurrentPlayer;

            if (c.Choice != null)
            {
                g.Process(ChooseTask.Pick(c, c.Choice.Choices.Random(Random)));
                return;
            }

            Options options = c.GetOptions(Options);
            Options = options;

			OptionsFilter[] filters = _filters;
			for (int i = 0; i < filters.Length; i++)
				filters[i](g, options);


			g.Process(options.GetRandom(c, Random));
        }
    }
}
