using System.Collections.Generic;
using System.Text;
//using MathNet.Numerics;
using SabberStoneCoreAi.MCGS.DefaultPolicy;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCore.Tasks.PlayerTasks;

namespace SabberStoneCoreAi.MCGS
{
	public class SearchConfig
	{
		public const double FirstMoveDurationSeconds = 15;
		public const double ContinuousMoveDurationSeconds = 10;
		public const bool DoNotRemoveUnselectedNodes = true;
		public const FinalMoveSelection FinalMoveSelection = 0;

		public double UCTConstant = 0.285;

		//public SearchDurationControlOption SearchDurationControlOption =
		//	SearchDurationControlOption.DURATION_EXPONENTIAL;
		//public double MaxSearchDurationSeconds = 15;
		//public double PrudenceDepth = 3;
		public ImperfectInformationAlgorithm IIAlgorithm;
		public int DeterminizationNumber = 200;

		public NodeConfig NodeConfig = new NodeConfig();

		public Policy RolloutPolicy => _policy ?? (_policy = new UniformRandomRollout(in DefaultPolicyFilters));

		private UniformRandomRollout _policy;

		internal OptionsFilter[] DefaultPolicyFilters =
		{
			Filters.CategoryBasedFilter,
			Filters.RemoveVoidAction,
			Filters.CompulsiveHeroPowerWhenAvailable,
			Filters.CompulsiveAttackWhenAvailable,
		};

		public SearchStatistics EpisodeStatistics;

		public readonly List<PlayerTask> Archive = new List<PlayerTask>();

		//public void SetDurationModifier(double modifier)
		//{
		//	FirstMoveDurationSeconds *= modifier;
		//	MaxSearchDurationSeconds *= modifier;
		//	LastResortSearchDurationSeconds *= modifier;
		//}

		//public double GetSearchDuration(int selectionCount)
		//{
		//	return FirstMoveDurationSeconds * Math.Pow(GetDurationControlParameter(), selectionCount);
		//}

		//private double GetDurationControlParameter()
		//{
		//	const double DefaultDCP = 3;

		//	MaxSearchDurationSeconds *= SearchDurationModifier;
		//	FirstMoveDurationSeconds *= SearchDurationModifier;
		//	LastResortSearchDurationSeconds *= SearchDurationModifier;

		//	if (dcpGlobal > 0)
		//	{
		//		return dcpGlobal;
		//	}

		//	var count = 0;
		//	int msd = (int) MaxSearchDurationSeconds;
		//	int fmd = (int) FirstMoveDurationSeconds;
		//	int pd = (int) PrudenceDepth;
		//	const int range = 4;
		//	const int pdRange = 2;
		//	var range1 = Enumerable.Range(Math.Max(0, msd - range / 2), range).ToArray();
		//	var range2 = Enumerable.Range(Math.Max(0, fmd - range / 2), range).ToArray();
		//	var range3 = Enumerable.Range(Math.Max(0, pd - pdRange / 2), pdRange).ToArray();
		//	var rnd = new Random();

		//	double dcp;

		//	while (true)
		//	{
		//		if (count > 400)
		//			throw new Exception();
		//		try
		//		{
		//			dcp = FindRoots.OfFunction(
		//				r => CommonUtils.GeometricSeries(r, (int) PrudenceDepth, MaxSearchDurationSeconds,
		//					FirstMoveDurationSeconds), 0.0, 0.999, maxIterations: 10000);
		//		}
		//		catch (Exception)
		//		{
		//			MaxSearchDurationSeconds = range1.Random(rnd);
		//			FirstMoveDurationSeconds = range2.Random(rnd);
		//			PrudenceDepth = range3.Random(rnd);
		//			//MaxSearchDurationSeconds = range1[count];
		//			//FirstMoveDurationSeconds = range2[count];
		//			count++;
		//			continue;
		//		}

		//		if (dcp >= 1 || dcp < 0.0)
		//		{
		//			MaxSearchDurationSeconds = range1.Random(rnd);
		//			FirstMoveDurationSeconds = range2.Random(rnd);
		//			PrudenceDepth = range3.Random(rnd);
		//			count++;
		//			continue;
		//		}

		//		break;
		//	}

		//	Console.WriteLine($"MSD: {MaxSearchDurationSeconds}, FMD: {FirstMoveDurationSeconds}, PD: {PrudenceDepth}");

		//	dcpGlobal = dcp;

		//	return dcp < 0 ? DefaultDCP : dcp;
		//}

		//	private double dcpGlobal = -1;

		public SearchConfig Clone()
		{
			var clone = (SearchConfig) MemberwiseClone();
			clone.NodeConfig = NodeConfig.Clone();

			return clone;
		}

		public override string ToString()
		{
			var sb = new StringBuilder();
			sb.AppendLine($"UCTConstant: {UCTConstant}");

			if (IIAlgorithm == ImperfectInformationAlgorithm.PIMC)
			{
				sb.AppendLine($"Perfect Information Monte Carlo. # determinizations: {DeterminizationNumber}");
			}

			sb.AppendLine($"DefaultPolicyFilters: ");
			foreach (var filter in DefaultPolicyFilters)
			{
				sb.AppendLine($"\t[{filter.Method.Name}] ");
			}

			sb.Append("\n");
			sb.AppendLine($"FirstMoveDurationSeconds: {FirstMoveDurationSeconds}");
			sb.AppendLine($"ContinuousMoveDurationSeconds: {ContinuousMoveDurationSeconds}");


			if (DoNotRemoveUnselectedNodes)
				sb.AppendLine("Preserving unselected part of the whole tree.");

			sb.Append(NodeConfig);

			return sb.ToString();
		}

		internal static SearchConfig BaseConfig => new SearchConfig
		{
			UCTConstant = 0.3,

			NodeConfig = new NodeConfig
			{
				DampingParameter = 2,
				UCDParams = (3, 1),
				DPWConstants = new Algorithms.DPWConstants(0.15, 0.5),
			},
		};

		internal static SearchConfig ShamanConfig
		{
			get
			{
				var baseConfig = BaseConfig;
				baseConfig.NodeConfig.DPWConstants = (0.6, 0.3);
				return baseConfig;
			}
		}
		internal static SearchConfig WarriorConfig
		{
			get
			{
				var baseConfig = BaseConfig;
				baseConfig.UCTConstant = 0.225;
				baseConfig.NodeConfig.DPWConstants = (0.15, 0.5);
				return baseConfig;
			}
		}

		internal static SearchConfig MageConfig
		{
			get
			{
				var baseConfig = BaseConfig;
				baseConfig.UCTConstant = 0.4;
				baseConfig.NodeConfig.UCDParams = (3, 2);
				baseConfig.NodeConfig.DPWConstants = (0.3, 0.5);
				return baseConfig;
			}
		}

		internal static SearchConfig PaladinConfig
		{
			get
			{
				var baseConfig = BaseConfig;
				baseConfig.UCTConstant = 0.8;
				baseConfig.NodeConfig.UCDParams = (2, 2);
				baseConfig.NodeConfig.DPWConstants = (0.5, 0.6);
				return baseConfig;
			}
		}
	}
}
