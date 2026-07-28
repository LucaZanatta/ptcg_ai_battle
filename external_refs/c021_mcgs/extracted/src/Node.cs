using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCoreAi.MCGS.SabberHelper.Option;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Enums;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Zones;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS
{
	partial class Node
	{
		#region Properties and Fields
        private readonly Random _rnd = MonteCarloGraphSearch.ThreadStaticRandom;

        public readonly bool IsEndTurn;
        public readonly bool IsTerminal;
        public readonly PlayState PlayState;
        public readonly bool IdMatched;

        public List<Edge> IncomingEdges = new List<Edge>();
        public List<Edge> OutgoingEdges = new List<Edge>();

        public NodeConfig MyConfig { get; set; }
		public NodeConfig OpConfig { get; set; }

		public NodeConfig NodeConfig => IsOpponent ? OpConfig : MyConfig;
        public Game Game { get; private set; }
        public PlayerTask ChanceAction { get; private set; }
        public Options Options { get; set; }
        public IReadOnlyList<PlayerTask> LegalActions;
        public List<int> UntestedActionIndices;
        public StateAbstraction StateAbstraction { get; set; }
        //  TODO: transpositions
        public ActionAbstraction ActionAbstraction => LastTraversedEdge?.ActionAbstraction;
        public Dictionary<StateAbstraction, Node> TranspositionTable { get; set; }
        public Node Parent => LastTraversedEdge?.Predecessor;
        public Edge LastTraversedEdge { get; set; }
        //public SampleCount SampleCountRef { get; set; }
        //public List<SampleCount> SampleCounts { get; set; }
        public int VisitCount { get; set; }
        public double Rewards { get; set; }
        public int Depth { get; set; }
        public int StartTurn { get; private set; }
        public bool IsOpponent => !IdMatched;
        public bool IsRandomHappened { get; private set; }
        public bool IsRandom { get; private set; }
        public bool IsSample { get; set; }
        public bool IsTransposition { get; set; }
        private bool IsDeterminized { get; set; }
        public bool ConsiderDeckAbstraction { get; private set; }
        public bool IsNotInTheMainTree { get; private set; }
        public List<Edge> StashedEdges { get; set; }
        public bool IsFinalised { get; private set; }
        public bool Removed { get; private set; }
        public RandomActionType RandomActionType { get; private set; }
        public bool IsInUse { get; set; }
        #endregion

        private void RandomHappened(object sender, bool isHappened)
        {
            IsRandomHappened = isHappened;
        }

        public Node(Node parent, PlayerTask action, int actionIndex,
	        ActionAbstraction actionAbstraction = null,
	        bool random = false,
	        bool addChild = true,
	        Game game = null)
        {
            #region Inherit properties
            //Parent = parent;
            if (addChild)
            {
                //Parent.Children.Add(this);
                Edge.Connect(parent, this, action, actionIndex, true, actionAbstraction);
            }

            MyConfig = parent.MyConfig;
			OpConfig = parent.OpConfig;
            IsRandom = random;

            TranspositionTable = parent.TranspositionTable;
            //_informationSetTable = parent._informationSetTable;
            //OpInfoSetTable = parent.OpInfoSetTable;
            //InformationSets = parent.InformationSets;
            Depth = parent.IsRandom ? parent.Depth : parent.Depth + 1;
            StartTurn = parent.StartTurn;
            IsDeterminized = parent.IsDeterminized;
            //NumSamplesTraversed = parent.NumSamplesTraversed;
            ConsiderDeckAbstraction = parent.ConsiderDeckAbstraction;

            if (parent.RandomActionType == RandomActionType.ENDTURN)
	            IsDeterminized = true;

            #endregion

            #region Assign Game, Action and Abstractions
            if (game != null)
            {
                Game = game;
                //Action = action;
                IdMatched = game.CurrentPlayer.Id == NodeConfig.PlayerEntityId;
                StateAbstraction = new StateAbstraction(game, MCGS.NodeConfig.SimpleAbstraction, false, ConsiderDeckAbstraction);
                //ActionAbstraction = new ActionAbstraction(action, parent.StateAbstraction.HashDic, NodeConfig.SimpleAbstraction);
            }
            else if (random)
            {
                Game = parent.Game;
                IdMatched = parent.IdMatched;
                //ActionAbstraction = new ActionAbstraction(action, parent.StateAbstraction.HashDic, NodeConfig.SimpleAbstraction);
                StateAbstraction = new StateAbstraction(parent.StateAbstraction, actionAbstraction ?? ActionAbstraction);
                ChanceAction = action;
            }
            else
            {
	            var g = parent.Game.Clone();
                Game = g;
                g.RandomHappenedEvent += RandomHappened;
                g.Process(action);
                g.RandomHappenedEvent -= RandomHappened;
                IdMatched = g.CurrentPlayer.Id == NodeConfig.PlayerEntityId;
                //action.Game = parent.Game;

                // Generates abstraction from the raw game state.
                // Abstraction of an op node also possesses private information of the RP;
                // i.e. it has perfect information.
                bool createCompleteAbstraction = IsOpponent && !parent.IsInformationSet;
                StateAbstraction = new StateAbstraction(g, 
                    MCGS.NodeConfig.SimpleAbstraction, createCompleteAbstraction, ConsiderDeckAbstraction);
                //ActionAbstraction = new ActionAbstraction(action, parent.StateAbstraction.HashDic, NodeConfig.SimpleAbstraction);
                
                if (StateAbstraction.Equals(parent.StateAbstraction))
                    throw new Exception("Abnormal state transition detected");
            }
            #endregion

            IsTerminal = Game.State == State.COMPLETE;
            PlayState = Game.CurrentPlayer.PlayState;
            if (action?.PlayerTaskType == PlayerTaskType.END_TURN || (actionAbstraction?.IsEndTurnAction ?? false))
                IsEndTurn = true;
            _informationSet = parent._informationSet;


            #region Get legal actions and pruning
            if (!random)
            {
                Options options = Game.CurrentPlayer.GetOptions();
                Options = options;
                PlayerTask[] legalActions = GetPrunedAction_modified(Game, options, MCGS.NodeConfig.SimpleAbstraction, StateAbstraction.HashDic);
                LegalActions = legalActions;
                UntestedActionIndices = Enumerable.Range(0, LegalActions.Count).ToList();
            }
            else
            {
                Options = parent.Options;
            }
			#endregion
		}

		public Node(Game game, NodeConfig myConfig, NodeConfig opConfig, bool deckAbstraction = false)
        {
            //Game = game.getCopy();
            Game = game.Clone();
            MyConfig = myConfig ?? new NodeConfig();
            OpConfig = opConfig ?? new NodeConfig();
            TranspositionTable = new Dictionary<StateAbstraction, Node>();
            //_informationSetTable = new Dictionary<StateAbstraction, Node>();
            //OpInfoSetTable = new Dictionary<StateAbstraction, OpInfoSet>();
            //if (NodeConfig.InformationSet)
            //    InformationSets = new HashSet<InformationSet>();

            StateAbstraction = new StateAbstraction(Game, MCGS.NodeConfig.SimpleAbstraction, IsOpponent, deckAbstraction);
            var options = Game.CurrentPlayer.GetOptions();
            Options = options;
            //UntestedActions = new List<PlayerTask>(GetPrunedAction_modified(options, NodeConfig.SimpleAbstraction));
            LegalActions = GetPrunedAction_modified(game, options, MCGS.NodeConfig.SimpleAbstraction, StateAbstraction.HashDic);
            UntestedActionIndices = Enumerable.Range(0, LegalActions.Count).ToList();
            StartTurn = game.Turn;

            IsTerminal = game.State == State.COMPLETE;
            IdMatched = game.CurrentPlayer.Id == NodeConfig.PlayerEntityId;

            ConsiderDeckAbstraction = deckAbstraction;
        }

        // The copy constructor.
        private Node(Node node)
        {
            IsRandom = node.IsRandom;
            MyConfig = node.MyConfig;
			OpConfig = node.OpConfig;

            StateAbstraction = node.StateAbstraction;
            if (node.UntestedActionIndices != null)
                UntestedActionIndices = new List<int>(node.UntestedActionIndices);

            Depth = node.Depth;
            StartTurn = node.StartTurn;
            IsDeterminized = node.IsDeterminized;

            IsTerminal = node.IsTerminal;
            PlayState = node.PlayState;
            IsEndTurn = node.IsEndTurn;
            IdMatched = node.IdMatched;

            VisitCount = node.VisitCount;
            Rewards = node.Rewards;
            ConsiderDeckAbstraction = node.ConsiderDeckAbstraction;
        }
#if DEBUG
        public Node _lastBackUpFrom { get; set; }
        Node _lastInheritFrom { get; set; }
        HandZone _currentHand => Game.CurrentPlayer.HandZone;
        //public bool _lethal { get; set; }
#endif

        #region Methods
        /// <summary>
        /// Prunes the graph/tree and makes this node the new root node.
        /// </summary>
        public void AsRoot(bool preserve = false)
        {
            //NumSamplesTraversed = 0;
            //Depth = 0;
            //Edges.Clear();

            if (preserve)
            {
                //Parent = null;
                LastTraversedEdge = null;
                //IncomingEdges.Clear();
                return;
            }

            if (Parent == null) return;

            for (int j = 0; j < IncomingEdges.Count; j++)
            {
                if (IncomingEdges[j].IsDummy)
                {
                    IncomingEdges[j].Clear();
                    continue;
                }

                Node predecessor = IncomingEdges[j].Predecessor;

                if (predecessor.IsRandom)
                    predecessor.AsRoot();


                IEnumerable<Node> siblings = predecessor.OutgoingEdges.Select(p => p.Successor);

                foreach (Node sibling in siblings)
                {
	                // TODO: fix this
                    if (sibling == null)
                        continue;

                    if (sibling == this) continue;  // Only consider siblings

                    if (sibling.IsTransposition && sibling.IncomingEdges.Count > 1)
                    {
                        Edge edgeToBeRemoved = sibling.IncomingEdges.Find(e => e.Predecessor == predecessor);
                        edgeToBeRemoved.Disconnect();
                    }
                    else
                        ClearNode(sibling);
                }

                predecessor.ReleaseAllManagedResources();
            }

            IncomingEdges.Clear();

            //Parent = null;
            LastTraversedEdge = null;

            void ClearNode(Node n)
            {
	            if (n?.StateAbstraction == null)
                    return;

                //n.IsRemoved = true;

                //n.Parent = null;
                n.LastTraversedEdge = null;

                // Completely remove stashed edges;
                n.StashedEdges?.ForEach(e => e.Predecessor.OutgoingEdges?.Remove(e));
                
                n.TranspositionTable.Remove(n.StateAbstraction);


                foreach (Edge e in n.OutgoingEdges)
                {
                    Node s = e.Successor;

                    s.IncomingEdges.Remove(e);
                    if (s.LastTraversedEdge == e)
                        s.LastTraversedEdge = null;
                    e.Clear();

                    if (s.IncomingEdges.Count == 0)
                        ClearNode(s);
                }
                
                n.ReleaseAllManagedResources();
            }
        }

        public void MarkAsSeparatedTree()
        {
            IsNotInTheMainTree = true;
            //Children.ForEach(n => n.MarkAsSeparatedTree());
            OutgoingEdges.ForEach(e => e.Successor.MarkAsSeparatedTree());
        }

        public void MergeSeparatedSubtree()
        {
            IsNotInTheMainTree = false;
            //foreach (Node n in Children)
            //{
            //    // Already founded nodes
            //    if (!n.IsNotInTheMainTree)
            //    {
            //        // Search stashed edges
            //        Edge stashed = n.StashedEdges?.Find(e => e.Predecessor == this) ?? default;
            //        if (stashed?.Predecessor != null)
            //            n.IncomingEdges.Add(stashed);
            //    }

            //    n.MergeSeparatedSubtree();
            //}

            for (int i = 0; i < OutgoingEdges.Count; i++)
            {
                Edge e = OutgoingEdges[i];
                Node n = e.Successor;
                if (!n.IsNotInTheMainTree && 
                    (n.StashedEdges?.Remove(e) ?? false))
                    n.IncomingEdges.Add(e);

                n.MergeSeparatedSubtree();
            }
        }

        public double Value(double c)
        {
	        double x;

            if (IsTerminal)
            {
                switch (PlayState)
                {
                    case PlayState.WON:
                        x = 10;
                        break;
                    case PlayState.LOST:
                        x = -10;
                        break;
                    default:
                        x = 0;
                        break;
                }
            }
            else
            {
                x = Rewards / VisitCount;
            }

            if (c == 0)
                return x;

            return x + c * Math.Sqrt(2 * Math.Log(Parent.VisitCount) / VisitCount);
        }

        public void Update(double reward)
        {
	        if (IsOpponent)
                reward *= -1;

            if (IsEndTurn && NodeConfig.PIMC)
                reward *= -1;

            VisitCount += 1;

            Rewards += reward;
        }

        public bool Finalise()
        {
            if (NodeConfig.PIMC)
                return false;

            IsFinalised = true;

            Node parent = LastTraversedEdge?.Predecessor;
            if (parent == null)
                return false;

            if (parent.IsRandom) return false;

            parent.OutgoingEdges.Clear();
            parent.OutgoingEdges.Add(LastTraversedEdge);
            parent.UntestedActionIndices.Clear();
            //parent.ActionAbstractions = new[] {LastTraversedEdge.ActionAbstraction};
            return true;

        }

        public bool BestChild(out Node bestChild, double c, ref int chanceNodeTraversed)
        {
	        if (IsRandom)
            {
                SampleChild(out bestChild);
                if (OutgoingEdges.Count > 5)
                    chanceNodeTraversed++;
            }
            else
            {
	            Edge bestEdge = MCGS.NodeConfig.StoreVisitsAtEdges
                    ? OutgoingEdges.ArgMax(edge => edge.Value(c))
                    : OutgoingEdges.ArgMax(edge => edge.Successor.Value(c));


                bestChild = bestEdge.Traverse();
            }

#if DEBUG
            //  for debugging
            bestChild._lastInheritFrom = this;
#endif
            return true;
        }

        private void SampleChild(out Node sampleChild)
        {
            //Edge sampleEdge = NodeConfig.SampleTranspositionTest 
            //    ? OutgoingEdges.GetWeightedRandom(p => p.Successor.SampleCountRef, _rnd, SampleCountRef) 
            //    : OutgoingEdges.GetWeightedRandom(p => p.Successor.SampleCounts.Sum(q => q), _rnd, SampleCountRef);
            Edge sampleEdge = OutgoingEdges.GetWeightedRandom(p => p.SampleCount, _rnd);

            if (sampleEdge == null)
                throw new Exception();

            sampleChild = sampleEdge.Traverse();
        }

        public Node Clone()
        {
            return new Node(this);
        }

        private void ReleaseAllManagedResources()
        {
            return;

            Game = null;
            //Action = null;
            //PrunedActions = null;
            //UntestedActions = null;
            Options = null;
            LegalActions = null;
            UntestedActionIndices = null;
            //ActionAbstraction = null;
            StateAbstraction = null;
            IncomingEdges = null;
            OutgoingEdges = null;
            LastTraversedEdge = null;
            StashedEdges = null;
            //Children = null;

            //Group = null;
            //InformationSet = null;

#if DEBUG
            _lastBackUpFrom = null;
            _lastInheritFrom = null;
#endif
        }

        public override string ToString()
        {
            var sb = new StringBuilder();
            if (IsFinalised)
                sb.Append("[F]");
            if (IsOpponent)
                sb.Append("[O]");
            if (IsRandom)
                sb.Append("[C]");
            if (IsTransposition)
                sb.Append("[T]");
            if (IsFullyExpanded(0))
                sb.Append("[FE]");
            sb.Append("[D:");
            sb.Append(Depth.ToString());
            sb.Append("]");
            if (ActionAbstraction != null)
            {
                sb.Append("[A:");
                sb.Append(ActionAbstraction);
                sb.Append("]");
            }

            sb.Append(IsTerminal
                ? "[Terminal]"
                : $"[V:{Math.Round(Value(0), 2)}][R:{Math.Round(Rewards, 2)}][N:{VisitCount}]");
            return sb.ToString();
        }

        public string PrintScore()
        {
	        return $"Value: {Math.Round(Value(0), 3)}({Math.Round(Rewards, 2)}/{VisitCount})";
        }
		#endregion
	}
}
