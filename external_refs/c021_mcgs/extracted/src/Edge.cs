using System;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS
{
    class Edge
    {
        private bool _dummy;
        public readonly int ActionIndex;

        public Node Predecessor { get; private set; }
        public Node Successor { get; private set; }
        public ActionAbstraction ActionAbstraction { get; private set; }
        public int VisitCount { get; set; }
        public int SampleCount { get; set; } = 1;

        public bool IsDummy
        {
            get => _dummy;
            set
            {
                if (value)
                {
                    _dummy = true;
                    VisitCount = int.MaxValue;
                }
                else
                {
                    _dummy = false;
                    VisitCount = 0;
                }
            }
        }

        private Edge(Node predecessor, Node successor, PlayerTask action, int index, ActionAbstraction aa = null)
        {
            if (index < 0)
                throw new Exception();

            Predecessor = predecessor;
            Successor = successor;
            //Action = action;
            ActionAbstraction = aa ?? new ActionAbstraction(action, predecessor.StateAbstraction.HashDic, NodeConfig.SimpleAbstraction);
            ActionIndex = index;
        }

        public double Value(double c)
        {
            double x = Successor.Value(0);

            if (c == 0)
                return x;

            double bonus;

            if (NodeConfig.SelectionStrategy == SelectionStrategy.UCD)
                bonus = c * Math.Sqrt(2 * Math.Log(Predecessor.TotalVisit) / VisitCount);
            else
                bonus = c * Math.Sqrt(2 * Math.Log(Predecessor.VisitCount) / VisitCount);

            //if (Successor.IsRandom && !Successor.IsEndTurn && Successor.NodeConfig.ChanceNodeExplorationBonus)
            //    bonus += NodeConfig.ChanceNodeExplorationConstant * Successor.GetExplorationBonus();

            return x + bonus;
        }

        public override string ToString()
        {
            return $"[N:{VisitCount}]{ActionAbstraction}{(SampleCount > 1 ? SampleCount.ToString() : "")}";
        }

        public int Disconnect()
        {
            if (!Predecessor.OutgoingEdges.Remove(this))
                throw new Exception();

            if (!Successor.IncomingEdges.Remove(this))
                throw new Exception();

            if (Successor.LastTraversedEdge == this)
                Successor.LastTraversedEdge = null;

            Clear();

            return ActionIndex;
        }

        public void Clear()
        {
            Predecessor = null;
            Successor = null;
            ActionAbstraction = null;
        }

        public void ChangeSuccessor(Node successor, bool traverse = false)
        {
            if (!Successor.IncomingEdges.Remove(this))
                throw new Exception();
            if (Successor.LastTraversedEdge == this)
                Successor.LastTraversedEdge = null;

            Successor = successor;

            successor.IncomingEdges.Add(this);

            if (traverse)
                successor.LastTraversedEdge = this;
        }

        public void ChangePredecessor(Node predecessor)
        {
            if (!Predecessor.OutgoingEdges.Remove(this))
                throw new Exception();

            Predecessor = predecessor;
            predecessor.OutgoingEdges.Add(this);
        }

        public Node Traverse()
        {
            Successor.LastTraversedEdge = this;
            return Successor;
        }

        public static Edge Connect(Node predecessor, Node successor, PlayerTask action, int actionIndex, bool traverse = true, ActionAbstraction aa = null)
        {
            var edge = new Edge(predecessor, successor, action, actionIndex, aa);

            predecessor.OutgoingEdges.Add(edge);
            successor.IncomingEdges.Add(edge);

            if (predecessor.IsRandom)
                successor.IsSample = true;

            if (traverse)
                successor.LastTraversedEdge = edge;

            return edge;
        }

        #region UCD

#if DEBUG
        public double Rewards { get; set; }
#endif

        public void RecursiveUpdate(double reward, int d1, int d2)
        {
            if (IsDummy)
                return;

            bool f1 = d1 > 1;
            bool f2 = d2 > 0;

            if (!f1 && !f2)
                return;

            var p = Predecessor;

            if (f1)
            {
                p.Update(reward);
            }

            if (f2)
            {
                VisitCount++;
                p.TotalVisit++;
            }

            for (int i = 0; i < p.IncomingEdges.Count; i++)
                p.IncomingEdges[i].RecursiveUpdate(reward, d1 - 1, d2 - 1);
        }


        #endregion
    }
}
