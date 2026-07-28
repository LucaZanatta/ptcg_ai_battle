using System.Text;

namespace SabberStoneCoreAi.MCGS
{
    public partial class NodeConfig
    {
	    public const bool SimpleAbstraction = true;
	    public const bool Transposition = true;
	    public const bool StoreVisitsAtEdges = true;
	    public const SelectionStrategy SelectionStrategy = (SelectionStrategy) 2;

	    public int SampleWidth = 24;

	    public bool PIMC = false;
	    public bool FixedNumberOfDeterminizations = false;
	    public int NumFixedDeterminizations;

        public int PlayerEntityId { get; set; }
        public int StartRound { get; set; }
        public int RootDepth { get; set; }

        public NodeConfig Clone()
        {
            return (NodeConfig) MemberwiseClone();
        }

        public override string ToString()
        {
            var sb = new StringBuilder();
            sb.AppendLine($"PlayerEntityId: {PlayerEntityId}");
            sb.AppendLine($"Simple Abstarction: {SimpleAbstraction}");

            sb.AppendLine(DoubleProgressiveWidening
                ? $"Double Progressive Widening: {DPWConstants}"
                : $"SampleNumber: {SampleWidth}");

            if (DampedSampling)
            {
                sb.AppendLine($"Damped Sampling: {DampedSampling}");
                sb.AppendLine($"Damping Parameter: {DampingParameter}");
                sb.AppendLine($"Removed additional reducing for endnodes");
            }
            else
                sb.AppendLine($"Damped Sampling: FALSE");

            sb.AppendLine($"SelectionStrategy: {SelectionStrategy}");

            if (SelectionStrategy == SelectionStrategy.UCD && Transposition)
	            sb.AppendLine($"UCD Constants: d1: {UCDParams.d1}, d2: {UCDParams.d2}");

            if (FixedNumberOfDeterminizations)
                sb.AppendLine($"Fixed Number of Determinzations: {NumFixedDeterminizations}");

            if (!Transposition)
                sb.AppendLine("Not using transposition table.");

            return sb.ToString();
        }
    }
}
