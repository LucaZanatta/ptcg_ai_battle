using System;
using System.Collections.Generic;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCore.Model;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.DefaultPolicy
{
    public abstract class Policy
    {
        [ThreadStatic] private static Random _rnd;
        private protected static Random Random => _rnd ?? (_rnd = new Random(Guid.NewGuid().GetHashCode()));
        private protected OptionsFilter[] _filters;

#if TRACE
        private protected List<PlayerTask> _playedOptions = new List<PlayerTask>();
#endif

        private protected Policy() { }

        private protected Policy(in OptionsFilter[] filters)
        {
	        _filters = filters;
        }

        private protected void ExecuteLethalSequence(Game g, PlayerTask[] actionSequence)
        {
            for (int i = 0; i < actionSequence.Length; i++)
                g.Process(actionSequence[i]);
        }

        public int _playedCount;

        internal abstract void Play(Game g);

        internal void SetFilters(in OptionsFilter[] filters)
        {
            _filters = filters;
        }
    }
}
