using System;

namespace SabberStoneCoreAi.MCGS
{
	public readonly struct UCDParams
	{
		public readonly int d1;
		public readonly int d2;

		public UCDParams(int d1, int d2)
		{
			if (d1 < 1)
				throw new Exception("d1 of UCD parameter must be larger than 1.");

			this.d1 = d1;
			this.d2 = d2;
		}

		public static implicit operator UCDParams((int, int) valueTuple)
		{
			(int item1, int item2) = valueTuple;
			return new UCDParams(item1, item2);
		}
	}

	public partial class NodeConfig
	{
		public UCDParams UCDParams = new UCDParams(1, 0);
	}

	partial class Node
	{
		public int TotalVisit;

		public void UCDUpdate(double reward, int d1, int d2)
		{
			Update(reward);
			TotalVisit++;

			var incoming = IncomingEdges;
			if (incoming.Count > 1)
			{
				for (int i = 0; i < incoming.Count; i++)
				{
					var edge = incoming[i];

					if (edge == LastTraversedEdge || edge.IsDummy)
						continue;

					edge.RecursiveUpdate(reward, d1, d2);
				}
			}
		}
	}
}
