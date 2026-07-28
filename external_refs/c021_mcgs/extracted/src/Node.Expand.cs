using System;
using System.Linq;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS
{
    partial class Node
    {
	    public bool HasChoices => Game.CurrentPlayer.Choice != null;
	    public bool IsDraw => Game.CurrentPlayer.NumCardsDrawnThisTurn > Parent.Game.CurrentPlayer.NumCardsDrawnThisTurn;


        public int TreePolicy()
        {
            // Uniform random selection
            int i = _rnd.Next(UntestedActionIndices.Count);
            int actionIndex = UntestedActionIndices[i];
            UntestedActionIndices.RemoveAt(i);

            return actionIndex;
        }

        public bool IsFullyExpanded(int numSampleTraversed)
        {
            if (!IsRandom)
	            return UntestedActionIndices.Count == 0;

            if (MCGS.NodeConfig.DoubleProgressiveWidening)
            {
                int threshold = DPWThreshold(NodeConfig.DPWConstants, VisitCount);

                if (MCGS.NodeConfig.DampedSampling)
                    threshold = ReduceFunction(threshold);

                return threshold <= OutgoingEdges.Sum(e => e.SampleCount);
            }

            if (MCGS.NodeConfig.DampedSampling)
            {
	            if (numSampleTraversed == 0)
                    return NodeConfig.SampleWidth <= OutgoingEdges.Sum(e => e.SampleCount);

                int reduced = ReduceFunction(NodeConfig.SampleWidth);
                if (reduced == 0) reduced = 1;
                return reduced <= OutgoingEdges.Sum(e => e.SampleCount);
            }

            return VisitCount <= OutgoingEdges.Sum(e => e.SampleCount);

            int ReduceFunction(int sampleWidth)
            {
	            return Convert.ToInt32(sampleWidth / Math.Pow(NodeConfig.DampingParameter, numSampleTraversed));
            }
        }

        // Returns true if we need to loop the tree phase once again.
        public bool Expand(out Node newNode, int actionIndex = -1)
        {
            // Create a new sample node
            if (IsRandom)
            {
                PrepareChanceNode();

                newNode = new Node(this, ChanceAction , 0, ActionAbstraction);

  
                if (!newNode.IsOpponent)
                    newNode._informationSet = null;
            }
            // Create a new child node
            else
            {
	            PlayerTask selectedAction;
                if (actionIndex >= 0)
                {
                    selectedAction = LegalActions[actionIndex];
                    if (!UntestedActionIndices.Remove(actionIndex))
                        throw new Exception();
                }
                else
                {
                    // Select action from the untested actions.
                    // Remove selected action from the untested actions.
                    // ExpandEndNodeLastly option.
                    actionIndex = TreePolicy();

                    selectedAction = LegalActions[actionIndex];
                }

                if (selectedAction.PlayerTaskType == PlayerTaskType.END_TURN && 
                    !NodeConfig.PIMC)
                {   // Generate determinization for end turn nodes
                    if (!IsOpponent) // Root player => Opponent
                        SabberUtils.Determinize(Game, _rnd);
                    else             // Opponent => Root Player
                    {
	                    Node opponentEndTurnNode = new Node(this, selectedAction, actionIndex, 
                            new ActionAbstraction(selectedAction, true), true)
                        {
                            RandomActionType = RandomActionType.ENDTURN_OPPONENT
                        };

                        return opponentEndTurnNode.RestoreNodes(out newNode);
                    }
                }

                // Expand new child with the selected action.
                var child = new Node(this, selectedAction, actionIndex/*, addChild: false*/);

                // Check if an expanded node is random
                CheckRandom(ref child, selectedAction, actionIndex);

                newNode = child;
            }

            // Memory management
            if (IsFullyExpanded(0))
            {
                ReleaseGameResources();
            }

            // Check Transposition
            if (MCGS.NodeConfig.Transposition && MonteCarloGraphSearch.TranspositionCheck(ref newNode))
            {
	            return true;
            }

            if (newNode.IsSample)
            {   // Expansion from a chance node.
	            // Set opponent node as the opponent's information set
                // or restore nodes with the stored private information
                if (newNode.StateAbstraction.Complete)
                {
                    return GetInformationSet(ref newNode);
                }
            }
            else if (newNode.IsRandom)
            {   // A new chance node just have been created.
                Node firstSample = newNode.OutgoingEdges[0].Successor;

                bool flag = false;
                // Set opponent node as the opponent's information set
                if (newNode.ActionAbstraction.IsEndTurnAction && !newNode.IsOpponent)
	                flag = GetInformationSet(ref firstSample);

                newNode = firstSample;

                return flag;
            }

            return false;
        }

        private void CheckRandom(ref Node child, PlayerTask selectedAction, int actionIndex)
        {
            RandomActionType type = RandomActionType.FALSE;

            if (NodeConfig.PIMC)
            {
                if (child.IsRandomHappened)
                {
                    CreateChanceNode(selectedAction, actionIndex, child.ActionAbstraction,
                        RandomActionType.RANDOMEFFECT, ref child);
                    return;
                }

                return;
            }

            if (child.HasChoices)
                type = selectedAction.HasSource && selectedAction.Source.Card.AssetId == 1047
                    ? RandomActionType.TRACKING
                    : RandomActionType.CHOICES;
            else if (child.IsRandomHappened)
                type = child.IsDraw ? RandomActionType.DRAW : RandomActionType.RANDOMEFFECT;
            else if (child.IsEndTurn)
	            type = child.IsOpponent ? RandomActionType.ENDTURN : RandomActionType.ENDTURN_OPPONENT;
            else if (child.IsDraw)
                type = RandomActionType.DRAW;
            else
            {
                int id = selectedAction.Source?.Card.AssetId ?? 0;
                switch (selectedAction.PlayerTaskType)
                {
                    case PlayerTaskType.PLAY_CARD when id == 42784:
                        type = RandomActionType.RANDOMEFFECT;
                        break;
                    case PlayerTaskType.PLAY_CARD
                        when CardCategory.RevealTopDeckCards.Contains(id):
                        type = RandomActionType.DRAW;
                        break;
                }
            }

            if (type == RandomActionType.FALSE)
                return;

            CreateChanceNode(selectedAction, actionIndex, child.ActionAbstraction, type, ref child);
        }

        private void CreateChanceNode(PlayerTask a, int actionIndex, ActionAbstraction aa, RandomActionType type, ref Node child)
        {
            var chanceNode = new Node(this, a, actionIndex, aa, random: true, addChild: false)
            {
                RandomActionType = type
            };

            // Change the destination of the last traversed edge to the new chance node.
            child.LastTraversedEdge.ChangeSuccessor(chanceNode, true);

            if (type == RandomActionType.DRAW)
            {
                // Discard the first sample.
                // The first sample contains the undeterminized information.
                child.ReleaseAllManagedResources();
                child.ReleaseGameResources();

                chanceNode.Game.CurrentPlayer.DeckZone.Shuffle();
                var newSample = new Node(chanceNode, a, 0, aa);
            }
            else
            {
                // Move the newly expanded child to the new chance node.
                Edge.Connect(chanceNode, child, a, actionIndex);

                // Make the first sample's abstraction complete
                if (type == RandomActionType.TRACKING)
                {
                    chanceNode.ConsiderDeckAbstraction = true;
                    child.ConsiderDeckAbstraction = true;
                    child.StateAbstraction.AddDeckAbstraction(child.Game.CurrentPlayer);
                }
            }

            child = chanceNode;
        }

        /// <summary>
        /// Modifies state of this node to a create new sample node.
        /// </summary>
        private void PrepareChanceNode()
        {
            if (_games != null)
            {   // Choose a random games from the merged games
                Game = _games[_rnd.Next(_games.Count)];
            }

            switch (RandomActionType)
            {
                case RandomActionType.DRAW:
                    Game.CurrentPlayer.DeckZone.Shuffle();
                    break;
                case RandomActionType.ENDTURN:
                    if (!IsDeterminized)
                        SabberUtils.Determinize(Game, _rnd);
                    else
                        Game.CurrentOpponent.DeckZone.Shuffle();
                    //NumSamplesTraversed++;
                    break;
                case RandomActionType.ENDTURN_OPPONENT:
                    Game.CurrentOpponent.DeckZone.Shuffle();
                    break;
                case RandomActionType.TRACKING:
                    Game.CurrentPlayer.DeckZone.Shuffle();
                    break;
                case RandomActionType.RANDOMEFFECT:
                    if (ActionAbstraction.IsEndTurnAction)
                        goto case RandomActionType.ENDTURN;
                    if (!NodeConfig.PIMC && ChanceAction is PlayCardTask && CardCategory.RandomOpponentHand.Contains(ChanceAction.Source.Card.AssetId))
                        SabberUtils.Determinize(Game, _rnd);
                    break;
            }
        }

        private void ReleaseGameResources()
        {
            if (IsRandom && MCGS.NodeConfig.DoubleProgressiveWidening)
                return;

            Game = null;
            LegalActions = null;
            Options = null;
            ChanceAction = null;
        }
    }
}
