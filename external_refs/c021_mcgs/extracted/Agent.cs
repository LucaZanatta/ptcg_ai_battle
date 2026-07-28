using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using SabberStoneCore.Model;
using SabberStoneCore.Tasks.PlayerTasks;
using SabberStoneCoreAi.Agent;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCoreAi.MCGS.SabberHelper;
using static SabberStoneCoreAi.MCGS.AgentUtils;
using SabberStoneCoreAi.Meta;
using SabberStoneCore.Enums;

namespace SabberStoneCoreAi.MCGS
{
	class MCGSAgent : AbstractAgent
	{
		const bool PRESERVE = true;
		const bool ANALYSE = false;


		private Node previousNode;
		private SearchConfig searchConfig;
		private SearchConfig opConfig;
		private bool _initialised;
		 
		#region fields
		private int selectionCount = 0;
		private Node[] determinizations;

		#endregion

		public MCGSAgent()
		{
			preferedDeck = PremadeDeck.OddPaladin;
			preferedHero = CardClass.PALADIN;
		}

		private static bool InitialiseRoot(POGame.POGame poGame, Node previousNode, SearchConfig searchConfig, SearchConfig opConfig, out Node root)
		{
			searchConfig.NodeConfig.PlayerEntityId = poGame.CurrentPlayer.Id;

			if (previousNode == null)
			{
				root =  new Node(GenerateGameForSimulation(poGame), searchConfig.NodeConfig, opConfig.NodeConfig);
				return true;
			}

			if (previousNode.IsRandom)
			{
				Game game = poGame.CurrentPlayer.Game;
				var gameAbstraction = new StateAbstraction(game, NodeConfig.SimpleAbstraction);
				foreach (Edge sampleEdge in previousNode.OutgoingEdges)
				{
					if (sampleEdge.Successor.StateAbstraction != gameAbstraction) continue;
					sampleEdge.Successor.LastTraversedEdge = sampleEdge;

					root = sampleEdge.Successor;
					return false;
				}

				root =  new Node(previousNode, null, 0, previousNode.ActionAbstraction, false, true,
					GenerateGameForSimulation(poGame));
				return true;
			}

			var tempGameAbstraction = new StateAbstraction(poGame.CurrentPlayer.Game,
				NodeConfig.SimpleAbstraction, false,
				previousNode.ConsiderDeckAbstraction);
			if (!tempGameAbstraction.Equals(previousNode.StateAbstraction))
			{
				root =  new Node(previousNode.Parent, null, 0, previousNode.ActionAbstraction, false, true,
					GenerateGameForSimulation(poGame));
				return true;
			}

			root =  previousNode;
			return false;
		}

		private void CheckInitialised(POGame.POGame poGame)
		{
			if (_initialised) return;
			_initialised = true;

			(searchConfig, opConfig) = GetConfig(poGame);
			searchConfig.NodeConfig.PlayerEntityId = poGame.CurrentPlayer.Id;
			opConfig.NodeConfig.PlayerEntityId = poGame.CurrentPlayer.Id;
		}

		#region Overrides of AbstractAgent

		public override void InitializeAgent()
		{
			RuntimeHelpers.RunClassConstructor(typeof(CardCategory).TypeHandle);
		}

		public override void InitializeGame()
		{
			
		}

		public override PlayerTask GetMove(POGame.POGame poGame)
		{
			var timer = Stopwatch.StartNew();

			while (true)
			{
				try
				{
					CheckInitialised(poGame);

					SearchStatistics oneTurnStatistics = ANALYSE ? new SearchStatistics() : null;
					bool pimc = searchConfig.NodeConfig.PIMC;
					double searchDuration;

					if (InitialiseRoot(poGame, previousNode, searchConfig, opConfig, out Node root))
						searchDuration = SearchConfig.FirstMoveDurationSeconds;
					else
						searchDuration = SearchConfig.ContinuousMoveDurationSeconds;

					if (pimc && previousNode != null)
						MonteCarloGraphSearch.AggregateDeterminizations(root, determinizations);

					if (root.LegalActions?.Count == 1 && root.LegalActions[0] is EndTurnTask ett)
					{
						previousNode = null;
						return ett;
					}

					// Traverse immediately to the next node when there's only 1 edge.
					bool skip = pimc && determinizations[0].OutgoingEdges.Count(p => !p.IsDummy) == 1 ||
					       root.OutgoingEdges.Count(p => !p.IsDummy) == 1;

					if (pimc)
						Parallel.ForEach(determinizations, d => d.AsRoot(PRESERVE));
					else
						root.AsRoot(PRESERVE);

					if (!skip)
					{
						var innerTimer = Stopwatch.StartNew();
						if (pimc)
						{
							while (innerTimer.Elapsed < TimeSpan.FromSeconds(searchDuration))
							{
								Node determinization = determinizations[_rnd.Next(determinizations.Length)];
								MonteCarloGraphSearch.Search(ref determinization, searchConfig, oneTurnStatistics);
								determinization.IsInUse = false;
							}
						}
						else
						{
							while (innerTimer.Elapsed < TimeSpan.FromSeconds(searchDuration))
							{
								MonteCarloGraphSearch.Search(ref root, searchConfig, oneTurnStatistics);
							}
						}
						innerTimer.Stop();

						selectionCount++;
					}

					MonteCarloGraphSearch.Select(ref root, searchConfig, skip ? null : oneTurnStatistics);

					previousNode = root.IsEndTurn ? null : root;

					if (ANALYSE)
					{
						//oneTurnStatistics.SearchDurationPerTurn.Add(timer.ElapsedMilliseconds / 1000.0);
						if (!root.IsTerminal)
						{
							var ratio = (float)root.VisitCount / oneTurnStatistics.SearchCount;
							if (ratio <= 1)
								oneTurnStatistics.SequenceVisitCountRatios.Add(ratio);
						}

						Console.WriteLine(oneTurnStatistics.ToString());

						searchConfig.EpisodeStatistics?.Update(oneTurnStatistics);
						searchConfig.EpisodeStatistics?.SearchCountPerTurn.Add(oneTurnStatistics.SearchCount);
					}

					return SabberUtils.SendOption(poGame.CurrentPlayer.Game, root.ActionAbstraction);
				}
				catch
				{
					if (timer.Elapsed > TimeSpan.FromSeconds(60))
						continue;
					else
					{
						var options = poGame.CurrentPlayer.Options();
						return options[MonteCarloGraphSearch.ThreadStaticRandom.Next(options.Count)];
					}

				}
			}
		}

		public override void FinalizeGame()
		{
			previousNode = null;
			determinizations = null;
			Console.WriteLine(searchConfig.EpisodeStatistics);
		}

		public override void FinalizeAgent()
		{
			previousNode = null;
			determinizations = null;
		}

		#endregion
	}
}
