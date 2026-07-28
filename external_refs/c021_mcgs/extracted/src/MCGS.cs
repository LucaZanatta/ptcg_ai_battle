using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using SabberStoneCoreAi.MCGS.DefaultPolicy;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Enums;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;

namespace SabberStoneCoreAi.MCGS
{
    public static class MonteCarloGraphSearch
    {
        [ThreadStatic] private static Random _threadStaticRandom;

        public static Random ThreadStaticRandom =>
            _threadStaticRandom ?? (_threadStaticRandom = new Random(Guid.NewGuid().GetHashCode()));

        //  final move selection
	    internal static void Select(ref Node root, SearchConfig searchConfig, SearchStatistics oneTurnStatistics = null)
        {
            Node parent = root;

            // MaxChild principle
            if (NodeConfig.StoreVisitsAtEdges)
            {
                Edge selectedEdge;

                switch (SearchConfig.FinalMoveSelection)
                {
                    // The edge that has the highest value.
                    case FinalMoveSelection.MaxChild:
                        selectedEdge = root.OutgoingEdges.ArgMax(e => e.Value(0));
                        break;
                    // The edge that has the highest visit count.
                    case FinalMoveSelection.RobustChild:
                        selectedEdge = root.OutgoingEdges.ArgMax(e => e.Successor.VisitCount);
                        break;
                    case FinalMoveSelection.RobustMaxChild:
                        throw new NotImplementedException();
                    case FinalMoveSelection.SecureChild:
                        throw new NotImplementedException();
                    default:
                        throw new ArgumentOutOfRangeException();
                }

                root = selectedEdge.Successor;
                root.LastTraversedEdge = selectedEdge;
                oneTurnStatistics?.UpdateDecisionStatistics(root.Rewards / root.VisitCount, root.VisitCount,
                    parent.OutgoingEdges.Count, parent.OutgoingEdges.Select(p => p.Successor.VisitCount).ToArray());
            }
            else
            {
	            root = root.OutgoingEdges.ArgMax(e => e.Successor.Value(0)).Traverse();
                oneTurnStatistics?.UpdateDecisionStatistics(root.Rewards / root.VisitCount, (int)root.VisitCount,
                    root.Parent.OutgoingEdges.Count, root.Parent.OutgoingEdges.Select(p => p.Successor.VisitCount).ToArray());
            }
        }


        public static int RootDepth;

        internal static void Search(ref Node root, SearchConfig searchConfig, SearchStatistics statistics = null)
        {
	        var tpTimer = Stopwatch.StartNew();

			TreePolicy(ref root, searchConfig.UCTConstant);

			tpTimer.Stop();

            var rpTimer = Stopwatch.StartNew();
            var reward = SingleThreadRollout(root, searchConfig);
            rpTimer.Stop();

            if (statistics != null && !root.IsTerminal)
            {
                statistics.TreePolicyElapsed.Add((int)tpTimer.ElapsedMilliseconds);
                statistics.SimulationElapsed.Add((int)rpTimer.ElapsedMilliseconds);
                statistics.Depths.Add(root.Depth);
                statistics.SearchCount++;
            }

            Backup(ref root, reward);
        }

        //private static int stackCount;

        //private static List<Node> Determinizations;

        //private static void InformationSetSearch(DecisionSet infoSet, SearchConfig searchConfig,
        //    SearchStatistics statistics = null)
        //{
        //    var tpTimer = Stopwatch.StartNew();

        //    // Pick a determinization.
        //    var determinization = infoSet.Determinizations.Random(ThreadStaticRandom);

        //    int numChanceTraversed = 0;

        //    Node leaf = InformationSet.InformationSetTreePolicy(infoSet, determinization, searchConfig.UCTConstant,
        //        ref numChanceTraversed);
        //    //stackCount = 0;

        //    tpTimer.Stop();

        //    var rpTimer = Stopwatch.StartNew();
        //    var reward = TaskParallelRollout(leaf, searchConfig);
        //    rpTimer.Stop();

        //    if (statistics != null && !leaf.IsTerminal)
        //    {
        //        statistics.TreePolicyElapsed.Add((int)tpTimer.ElapsedMilliseconds);
        //        statistics.SimulationElapsed.Add((int)rpTimer.ElapsedMilliseconds);
        //        statistics.Depths.Add(leaf.Depth);
        //        statistics.SearchCount++;
        //    }

        //    Backup(ref leaf, reward);
        //}

        private static void TreePolicy(ref Node root, double c)
        {
            int chanceNodeTraversedCount = 0;

            while (true)
            {
	            if (root.IsTerminal)
                    return;
                if (!root.IsFullyExpanded(chanceNodeTraversedCount))
                {
                    if (root.Expand(out root))
                        continue;

                    return;
                }

                if (!root.BestChild(out root, c, ref chanceNodeTraversedCount))
                    return;
            }
        }

	    internal static bool TranspositionCheck(ref Node node)
        {
            // Search the table for the matching abstraction
            if (!node.TranspositionTable.TryGetValue(node.StateAbstraction, out Node matching))
	        {
		        node.TranspositionTable.Add(node.StateAbstraction, node);   // Add if not present

                // Just expanded chance node carries its first child and it should be checked too.
                if (node.IsRandom)
                {
                    Node firstChild = node.OutgoingEdges[0].Successor;

	                if (!node.TranspositionTable.TryGetValue(firstChild.StateAbstraction, out matching))
	                {
	                    node.TranspositionTable.Add(firstChild.StateAbstraction, firstChild);

                        return false;
	                }

	                node = firstChild;
	            }
	            else
	                return false;
            }


            // Merge the matched subtree into the main tree.
            if (matching.IsNotInTheMainTree)
            {
                // Stashing method.
                // Stash incoming edges from the side tree and
                // Reconnect when the predecessor of a stashed edge 
                // is merged into the main tree.
                matching.StashedEdges = new List<Edge>();
                for (int i = matching.IncomingEdges.Count - 1; i >= 0; i--)
                {
                    if (matching.IncomingEdges[i].Predecessor.IsNotInTheMainTree)
                    {
                        matching.StashedEdges.Add(matching.IncomingEdges[i]);
                        matching.IncomingEdges.RemoveAt(i);
                    }
                }

                matching.MergeSeparatedSubtree();
            }

            matching.IsTransposition = true;

            Node parent = node.LastTraversedEdge.Predecessor;

            // Chance Node Transposition
            Node sample = null;
            if (node.IsRandom)
            {
                if (node.IsEndTurn) 
                    matching.AddGame(node.Game); // Should we check uniqueness here?

                // Try merging samples:
                // Move the first sample (child) of the new chance node
                // to the matching chance node.
                Node firstChild = node.OutgoingEdges[0].Successor;
                if (!node.TranspositionTable.TryGetValue(firstChild.StateAbstraction, out Node matchingSample))
                {
                    // The sample is new one.
                    node.TranspositionTable.Add(firstChild.StateAbstraction, firstChild);

                    firstChild.LastTraversedEdge.ChangePredecessor(matching);

                    sample = firstChild;
                }
                else
                {

                    sample = matchingSample;
                    Edge connection = matchingSample.IncomingEdges.Find(e => e.Predecessor == matching);
                    if (connection != null) // The new sample is already inherits from the matching chance node.
                        sample.LastTraversedEdge = connection;
                    else
	                    Edge.Connect(matching, sample, matching.ChanceAction, 0, true, sample.ActionAbstraction);

                    sample.IsTransposition = true;
                }
            }

            Edge commonEdge = matching.IncomingEdges.Find(e => e.Predecessor == parent);

            // If a connection between the predecessor of 
            // the recently expanded node and the matched node
            // exists already, we don't need to connect them.
            if (commonEdge != null)
            {
                // Creates dummy edge for decision nodes.
                if (!parent.IsRandom)
                {
                    node.LastTraversedEdge.IsDummy = true;
                    node.LastTraversedEdge.ChangeSuccessor(matching);

                    // Return to the parent
                    node = parent;
                    return true;
                }
                else
                {
                    // Increase sample count of the common edge
                    // for chance nodes.
                    commonEdge.SampleCount++;
                }

                node.LastTraversedEdge.Disconnect();

                matching.LastTraversedEdge = commonEdge;
                node = matching;

                return true;
            }

            Edge edge = node.LastTraversedEdge;
            edge.ChangeSuccessor(matching);
            matching.LastTraversedEdge = edge;

            // Continues current search with the found transposition.
            if (sample != null)
            {
                node = sample;
                return node.IsTransposition;
            }

            node = matching;

	        return true;
        }

	    private static double SingleThreadRollout(Node leaf, SearchConfig searchConfig)
	    {
		    const int NumMaxTry = 5;
		    int count = 0;
		    double value;
		    do
		    {
			    var game = leaf.Game.Clone(true);
			    if (searchConfig.IIAlgorithm != ImperfectInformationAlgorithm.PIMC)
				    SabberUtils.Determinize(game, ThreadStaticRandom, true);
			    value = PlayUntilTerminal(game, searchConfig);
		    } while (value < 0 && count++ < NumMaxTry);

			return value;
	    }

	    private static double PlayUntilTerminal(Game game, SearchConfig searchConfig)
        {
			int startTurn = ((game.Turn + 1) / 2);
	        int count = 0;
            Policy policy = searchConfig.RolloutPolicy;
            while (true)
            {
	            if (count > 1000)
		            return -1;

		        if ((game.Turn + 1) / 2 == 45)
					return 0.0;

				if (game.State == State.COMPLETE)
                {
	                Controller agent = game.CurrentPlayer.Id == searchConfig.NodeConfig.PlayerEntityId
						? game.CurrentPlayer
						: game.CurrentOpponent;
					bool isWinner = agent.PlayState == PlayState.WON;

					double reward = isWinner ? 1.0 : 0.0;
					
	                return reward;
                }

				try
				{
					policy.Play(game);
				}
				catch
				{
					return -1;
				}

				count++;
			}
        }

	    private static void Backup(ref Node node, double reward)
        {
	        //  Check Lethal Sequence
            if (node.IsTerminal)
            {
                if (node.PlayState == PlayState.WON && node.Game.Turn == node.StartTurn)
                    reward *= 10;
            }

            if (NodeConfig.SelectionStrategy == SelectionStrategy.UCD)
            {
                BackupUCD(ref node, reward);
                return;
            }

		    if (NodeConfig.StoreVisitsAtEdges)
		    {
			    BackupEdges(ref node, reward);
			    return;
		    }

            while (true)
            {
                node.Update(reward/*, visitIncrement*/);

                if (node.IsTransposition)
                {
                    if (node.IncomingEdges.Count == 1)
                        node.IsTransposition = false;
                    else
                    {
	                    foreach (Edge edge in node.IncomingEdges)
                        {
                            if (ReferenceEquals(edge, node.LastTraversedEdge)) continue;
                            var parent = edge.Predecessor;

                            Backup(ref parent, reward);
                        }
                    }
                }
                if (node.LastTraversedEdge == null)
                    break;

                node = node.Parent;
            }
        }
				
		private static void BackupEdges(ref Node node, double reward)
		{

            bool terminal =
                node.IsTerminal &&
                !node.IsFinalised &&
                !node.ActionAbstraction.IsEndTurnAction &&
                node.Game.CurrentPlayer.PlayState == PlayState.WON;

            while (true)
		    {
			    node.Update(reward);

                if (terminal)
                    terminal = node.Finalise();

                Edge lastTraverseEdge = node.LastTraversedEdge;

                if (lastTraverseEdge == null)
                    break;
		        lastTraverseEdge.VisitCount += 1;
		        node = lastTraverseEdge.Predecessor;
		    }

        }

        private static void BackupUCD(ref Node node, double reward)
        {

            bool terminal =
                node.IsTerminal &&
                !node.IsFinalised &&
                !node.ActionAbstraction.IsEndTurnAction &&
                node.Game.CurrentPlayer.PlayState == PlayState.WON;

            int d1, d2;
            d1 = node.NodeConfig.UCDParams.d1;
            d2 = node.NodeConfig.UCDParams.d2;

            while (true)
            {
	            node.UCDUpdate(reward, d1, d2);

                if (terminal)
                    terminal = node.Finalise();

                Edge lastTraverseEdge = node.LastTraversedEdge;

                if (lastTraverseEdge == null)
                    break;
                lastTraverseEdge.VisitCount += 1;

                node = lastTraverseEdge.Predecessor;
            }
        }

        private static readonly object _locker = new object();

        private static Node PickDeterminization(Node[] determinizations)
        {
            Node result;
            lock (_locker)
            {
                do
                {
                    result = determinizations[ThreadStaticRandom.Next(determinizations.Length)];
                } while (result.IsInUse);

                result.IsInUse = true;

                return result;
            }
        }

        internal static void AggregateDeterminizations(Node root, Node[] determinizations)
        {
            foreach (Node determinization in determinizations)
            {
                foreach (Edge edge in determinization.OutgoingEdges)
                {
                    bool flag = false;
                    foreach (Edge rootEdge in root.OutgoingEdges)
                    {
                        if (rootEdge.ActionIndex == edge.ActionIndex)
                        {
                            rootEdge.Successor.VisitCount += edge.Successor.VisitCount;
                            rootEdge.Successor.Rewards += edge.Successor.Rewards;

                            flag = true;
                            break;
                        }
                    }

                    if (flag) continue;

                    Node rootChild = edge.Successor.Clone();
                    Edge.Connect(root, rootChild, null, edge.ActionIndex, true, edge.ActionAbstraction);
                }
            }

            root.VisitCount = root.OutgoingEdges.Sum(p => p.Successor.VisitCount);
            root.Rewards = root.OutgoingEdges.Sum(p => p.Successor.Rewards);
        }

        private static int CleanUpDeterminizations(Node root, Node[] determinizations, Game game)
        {
            int count = 0;

            for (int i = 0; i < determinizations.Length; i++)
            {
                bool foundMatched = false;

                foreach (Edge e in determinizations[i].OutgoingEdges)
                {
                    if (e.Successor.StateAbstraction != root.StateAbstraction)
                        continue;

                    determinizations[i] = e.Successor;
                    foundMatched = true;
                    break;
                }

                if (foundMatched)
                    continue;

                count++;

                // TODO: remove duplicates
                var newDtm = game.Clone();
                SabberUtils.Determinize(newDtm, ThreadStaticRandom, true);
                var newNode = new Node(newDtm, root.NodeConfig, root.OpConfig);
                determinizations[i] = newNode;
            }

            return count;
        }
    }
}


