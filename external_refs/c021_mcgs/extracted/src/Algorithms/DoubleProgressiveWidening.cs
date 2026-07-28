using System;

namespace SabberStoneCoreAi.MCGS
{
	using Algorithms;
	public partial class NodeConfig
	{
		public const bool DoubleProgressiveWidening = true;
		public DPWConstants DPWConstants = new DPWConstants(0.7, 0.6);
	}

	partial class Node
	{
		private static int DPWThreshold(DPWConstants constants, int visitCount)
		{
			return (int)Math.Ceiling(constants.C * Math.Pow(visitCount, constants.Alpha));
		}
	}
}

namespace SabberStoneCoreAi.MCGS.Algorithms
{
	public readonly struct DPWConstants
	{
		public readonly double C;
		public readonly double Alpha;

		public DPWConstants(double c, double alpha)
		{
			C = c;
			Alpha = alpha;
		}

		public static implicit operator DPWConstants((double, double) valueTuple)
		{
			return new DPWConstants(valueTuple.Item1, valueTuple.Item2);
		}

		public override string ToString()
		{
			return $"{{C:{C}, Alpha:{Alpha}}}";
		}
	}
}
