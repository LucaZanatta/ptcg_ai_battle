using System.Collections.Generic;
using System.Linq;
using System.Text;
using MathNet.Numerics.Statistics;

namespace SabberStoneCoreAi.MCGS
{
    public class SearchStatistics
    {
        public readonly List<int> TreePolicyElapsed = new List<int>();
        public readonly List<int> SimulationElapsed = new List<int>();
        public int SearchCount;
        public readonly List<int> Depths = new List<int>();
        //public List<double> Breadths = new List<double>();
        public int SelectionCount;
        public readonly List<int> SelectionCounts = new List<int>();
        public readonly List<double> Values = new List<double>();
        public readonly List<int> VisitCounts = new List<int>();
        public readonly List<double> VisitCountStdDevs = new List<double>();
        public readonly List<int> SearchCountPerTurn = new List<int>();
        public List<double> SearchDurationPerTurn { get; set; } = new List<double>();

        public double AverageSearchDurationPerTurn => SearchDurationPerTurn.Count > 0 ? SearchDurationPerTurn.Average() : 0;
        public double SearchFrequency => SearchCount / SearchDurationPerTurn.Sum();
        public double AverageSelectionCountPerTurn => SelectionCounts.Count > 0 ? SelectionCounts.Average() : SelectionCount;

        public readonly List<float> SequenceVisitCountRatios = new List<float>();


        public void Update(SearchStatistics searchStatistics)
        {
            TreePolicyElapsed.AddRange(searchStatistics.TreePolicyElapsed);
            SimulationElapsed.AddRange(searchStatistics.SimulationElapsed);
            Depths.AddRange(searchStatistics.Depths);
            //Breadths.AddRange(searchStatistics.Breadths);
            SearchCount += searchStatistics.SearchCount;
            if (searchStatistics.SelectionCount > 0)
                SelectionCounts.Add(searchStatistics.SelectionCount);
            SelectionCounts.AddRange(searchStatistics.SelectionCounts);
            Values.AddRange(searchStatistics.Values);
            VisitCounts.AddRange(searchStatistics.VisitCounts);
            //DurationsSeconds.AddRange(searchStatistics.DurationsSeconds);
            VisitCountStdDevs.AddRange(searchStatistics.VisitCountStdDevs);
            SearchCountPerTurn.AddRange(searchStatistics.SearchCountPerTurn);
            SearchDurationPerTurn.AddRange(searchStatistics.SearchDurationPerTurn);
            SequenceVisitCountRatios.AddRange(searchStatistics.SequenceVisitCountRatios);
        }

        public void UpdateDecisionStatistics(double value, int visitCount, int breadth, int[] visitCounts)
        {
            if (value > 1) return;

            SelectionCount++;
            Values.Add(value);
            VisitCounts.Add(visitCount);
            //Breadths.Add(breadth);
            //DurationsSeconds.Add(duration);
            var std = ArrayStatistics.PopulationStandardDeviation(visitCounts);

            VisitCountStdDevs.Add(std);

            //double sum = 0.0;
            //for (int i = 0; i < visitCounts.Length; i++)
            //    sum += visitCounts[i];

            //var ratio = value / sum;
        }


        public override string ToString()
        {
            if (SearchCount < 1)
                return "";
            var sb = new StringBuilder();
            sb.AppendLine("-----------------------------------------------");
            sb.AppendLine($"Search Count: {SearchCount} ");
            sb.AppendLine($"Search Frequency: {SearchFrequency} Hz");
            sb.AppendLine($"Average search duration per turn: {AverageSearchDurationPerTurn} s");
            sb.AppendLine($"Average Search Depth: {Depths.Average()} ");
            sb.AppendLine($"Maximum Search Depth: {Depths.Max()} ");
            if (SequenceVisitCountRatios.Any())
                sb.AppendLine($"Average Ratio of Visit Count of selected sequences and total search count per turn: {SequenceVisitCountRatios.Average()}");
            //sb.Append($"Search Breadth: [");
            //Breadths.ForEach(i =>
            //{
            //    sb.Append(" ");
            //    sb.Append(i.ToString());
            //});
            //sb.Append($" ]\n");
            //if (Breadths.Any())
            //{
            //    sb.AppendLine($"Average Search Breadth: {Breadths.Average()} ");
            //    //sb.AppendLine($"Search Breadth StdDev: {Breadths.PopulationStandardDeviation()}");
            //    sb.AppendLine($"Maximum Search Breadth: {Breadths.Max()} ");
            //}
            if (TreePolicyElapsed.Any())
                sb.AppendLine($"Average Tree duration: {TreePolicyElapsed.Average()} ms ");
            if (SimulationElapsed.Any())
                sb.AppendLine($"Average Simulation duration: {SimulationElapsed.Average()} ms ");
            if (Values.Any())
                sb.AppendLine($"Average values of selected actions: {Values.Average()}");
            if (VisitCounts.Any())
            {
                sb.AppendLine($"Average number of visit to selected actions: {VisitCounts.Average()}");
                sb.AppendLine($"Average Standard deviation of visit counts of children when select: {VisitCountStdDevs.Average()}");
            }
            if (SearchCountPerTurn.Any())
                sb.AppendLine($"Average search count per turn: {SearchCountPerTurn.Average()}");
            sb.AppendLine($"Average selection count per turn: {AverageSelectionCountPerTurn}");
            sb.AppendLine("-----------------------------------------------");
            return sb.ToString();
        }
    }
}