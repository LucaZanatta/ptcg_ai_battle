using System;
using System.Collections.Generic;
using System.Linq;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCore.Model;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS.SabberHelper
{
    public partial class SabberUtils
    {
        //  added 06/09/2017 01:05
        /// <summary>
        /// Prevent potential errors from mismatched entity ids caused by a loose abstraction
        /// </summary>
        internal static PlayerTask SendOption(Game game, ActionAbstraction aa)
        {
	        StateAbstraction abstraction = new StateAbstraction(game);
	        List<PlayerTask> options = game.CurrentPlayer.Options();

            PlayerTask matched = options.Find(p => new ActionAbstraction(p, abstraction.HashDic).Equals(aa));
            if (matched == null)
            {
	            var simpleAbstraction = new StateAbstraction(game, true);
                matched = options.Find(p => new ActionAbstraction(p, simpleAbstraction.HashDic, true).Equals(aa));
                if (matched == null)
                {
#if DEBUG
	                var debug = options.Select(p => new ActionAbstraction(p, abstraction.HashDic)).ToList();
	                var sdebug = options.Select(p => new ActionAbstraction(p, simpleAbstraction.HashDic, true)).ToList();
#endif
	                throw new Exception();
                }
            }

			return matched;



            //var before = new StateAbstraction(game);
            //game.Process(matched);
            //var after = new StateAbstraction(game);
            //if (before.Equals(after))
            //    throw new Exception();

        }

        internal static void SendOption(Game game, PlayerTask option)
        {
            SendOption(game, new ActionAbstraction(option, false));
        }
    }
}
